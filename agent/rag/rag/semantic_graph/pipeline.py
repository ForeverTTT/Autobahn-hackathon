from __future__ import annotations

import traceback
import asyncio
import inspect
import time
from dataclasses import asdict
from datetime import datetime, timezone
from typing import (
    Any,
    cast,
)
from rag.exceptions import PipelineCancelledException
from rag.utils import (
    compute_mdhash_id,
    get_content_summary,
    sanitize_text_for_encoding,
    generate_track_id,
    logger,
)
from rag.storage.shared_storage import (
    get_namespace_data,
    get_namespace_lock,
)
from rag.base import (
    DocProcessingStatus,
    DocStatus,
    StorageNameSpace,
)
from rag.operate import (
    extract_entities,
    merge_nodes_and_edges,
)


class RAGPipelineMixin:
    """Document pipeline processing methods (enqueue, validate, process)."""

    async def apipeline_enqueue_documents(
        self,
        input: str | list[str],
        ids: list[str] | None = None,
        file_paths: str | list[str] | None = None,
        track_id: str | None = None,
    ) -> str:
        """Pipeline for Processing Documents"""
        # Generate track_id if not provided
        if track_id is None or track_id.strip() == "":
            track_id = generate_track_id("enqueue")
        if isinstance(input, str):
            input = [input]
        if isinstance(ids, str):
            ids = [ids]
        if isinstance(file_paths, str):
            file_paths = [file_paths]

        # If file_paths is provided, ensure it matches the number of documents
        if file_paths is not None:
            if isinstance(file_paths, str):
                file_paths = [file_paths]
            if len(file_paths) != len(input):
                raise ValueError(
                    "Number of file paths must match the number of documents"
                )
        else:
            # If no file paths provided, use placeholder
            file_paths = ["unknown_source"] * len(input)

        # 1. Validate ids if provided or generate MD5 hash IDs and remove duplicate contents
        if ids is not None:
            # Check if the number of IDs matches the number of documents
            if len(ids) != len(input):
                raise ValueError("Number of IDs must match the number of documents")

            # Check if IDs are unique
            if len(ids) != len(set(ids)):
                raise ValueError("IDs must be unique")

            # Generate contents dict and remove duplicates in one pass
            unique_contents = {}
            for id_, doc, path in zip(ids, input, file_paths):
                cleaned_content = sanitize_text_for_encoding(doc)
                if cleaned_content not in unique_contents:
                    unique_contents[cleaned_content] = (id_, path)

            # Reconstruct contents with unique content
            contents = {
                id_: {"content": content, "file_path": file_path}
                for content, (id_, file_path) in unique_contents.items()
            }
        else:
            # Clean input text and remove duplicates in one pass
            unique_content_with_paths = {}
            for doc, path in zip(input, file_paths):
                cleaned_content = sanitize_text_for_encoding(doc)
                if cleaned_content not in unique_content_with_paths:
                    unique_content_with_paths[cleaned_content] = path

            # Generate contents dict of MD5 hash IDs and documents with paths
            contents = {
                compute_mdhash_id(content, prefix="doc-"): {
                    "content": content,
                    "file_path": path,
                }
                for content, path in unique_content_with_paths.items()
            }

        # 2. Generate document initial status (without content)
        new_docs: dict[str, Any] = {
            id_: {
                "status": DocStatus.PENDING,
                "content_summary": get_content_summary(content_data["content"]),
                "content_length": len(content_data["content"]),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "file_path": content_data["file_path"],
                "track_id": track_id,
            }
            for id_, content_data in contents.items()
        }

        # 3. Filter out already processed documents
        all_new_doc_ids = set(new_docs.keys())
        unique_new_doc_ids = await self.doc_status.filter_keys(all_new_doc_ids)

        # Handle duplicate documents
        ignored_ids = list(all_new_doc_ids - unique_new_doc_ids)
        if ignored_ids:
            duplicate_docs: dict[str, Any] = {}
            for doc_id in ignored_ids:
                file_path = new_docs.get(doc_id, {}).get("file_path", "unknown_source")
                logger.warning(f"Duplicate document detected: {doc_id} ({file_path})")

                existing_doc = await self.doc_status.get_by_id(doc_id)
                existing_status = (
                    existing_doc.get("status", "unknown") if existing_doc else "unknown"
                )
                existing_track_id = (
                    existing_doc.get("track_id", "") if existing_doc else ""
                )

                dup_record_id = compute_mdhash_id(f"{doc_id}-{track_id}", prefix="dup-")
                duplicate_docs[dup_record_id] = {
                    "status": DocStatus.FAILED,
                    "content_summary": f"[DUPLICATE] Original document: {doc_id}",
                    "content_length": new_docs.get(doc_id, {}).get("content_length", 0),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "file_path": file_path,
                    "track_id": track_id,
                    "error_msg": f"Content already exists. Original doc_id: {doc_id}, Status: {existing_status}",
                    "metadata": {
                        "is_duplicate": True,
                        "original_doc_id": doc_id,
                        "original_track_id": existing_track_id,
                    },
                }

            if duplicate_docs:
                await self.doc_status.upsert(duplicate_docs)
                logger.info(
                    f"Created {len(duplicate_docs)} duplicate document records with track_id: {track_id}"
                )

        # Filter new_docs to only include documents with unique IDs
        new_docs = {
            doc_id: new_docs[doc_id]
            for doc_id in unique_new_doc_ids
            if doc_id in new_docs
        }

        if not new_docs:
            logger.warning("No new unique documents were found.")
            return

        # 4. Store document content in full_docs and status in doc_status
        full_docs_data = {
            doc_id: {
                "content": contents[doc_id]["content"],
                "file_path": contents[doc_id]["file_path"],
            }
            for doc_id in new_docs.keys()
        }
        await self.full_docs.upsert(full_docs_data)
        await self.full_docs.index_done_callback()

        await self.doc_status.upsert(new_docs)
        logger.debug(f"Stored {len(new_docs)} new unique documents")

        return track_id

    async def apipeline_enqueue_error_documents(
        self,
        error_files: list[dict[str, Any]],
        track_id: str | None = None,
    ) -> None:
        """Record file extraction errors in doc_status storage."""
        if not error_files:
            logger.debug("No error files to record")
            return

        if track_id is None or track_id.strip() == "":
            track_id = generate_track_id("error")

        error_docs: dict[str, Any] = {}
        current_time = datetime.now(timezone.utc).isoformat()

        for error_file in error_files:
            file_path = error_file.get("file_path", "unknown_file")
            error_description = error_file.get(
                "error_description", "File extraction failed"
            )
            original_error = error_file.get("original_error", "Unknown error")
            file_size = error_file.get("file_size", 0)

            doc_id_content = f"{file_path}-{error_description}"
            doc_id = compute_mdhash_id(doc_id_content, prefix="error-")

            error_docs[doc_id] = {
                "status": DocStatus.FAILED,
                "content_summary": error_description,
                "content_length": file_size,
                "error_msg": original_error,
                "chunks_count": 0,
                "created_at": current_time,
                "updated_at": current_time,
                "file_path": file_path,
                "track_id": track_id,
                "metadata": {
                    "error_type": "file_extraction_error",
                },
            }

        if error_docs:
            await self.doc_status.upsert(error_docs)
            for doc_id, error_doc in error_docs.items():
                logger.error(
                    f"File processing error: - ID: {doc_id} {error_doc['file_path']}"
                )

    async def _validate_and_fix_document_consistency(
        self,
        to_process_docs: dict[str, DocProcessingStatus],
        pipeline_status: dict,
        pipeline_status_lock: asyncio.Lock,
    ) -> dict[str, DocProcessingStatus]:
        """Validate and fix document data consistency by deleting inconsistent entries, but preserve failed documents"""
        inconsistent_docs = []
        failed_docs_to_preserve = []

        for doc_id, status_doc in to_process_docs.items():
            content_data = await self.full_docs.get_by_id(doc_id)
            if not content_data:
                if (
                    hasattr(status_doc, "status")
                    and status_doc.status == DocStatus.FAILED
                ):
                    failed_docs_to_preserve.append(doc_id)
                else:
                    inconsistent_docs.append(doc_id)

        if failed_docs_to_preserve:
            async with pipeline_status_lock:
                preserve_message = f"Preserving {len(failed_docs_to_preserve)} failed document entries for manual review"
                logger.info(preserve_message)
                pipeline_status["latest_message"] = preserve_message
                pipeline_status["history_messages"].append(preserve_message)

            for doc_id in failed_docs_to_preserve:
                to_process_docs.pop(doc_id, None)

        if inconsistent_docs:
            async with pipeline_status_lock:
                summary_message = (
                    f"Inconsistent document entries found: {len(inconsistent_docs)}"
                )
                logger.info(summary_message)
                pipeline_status["latest_message"] = summary_message
                pipeline_status["history_messages"].append(summary_message)

            for doc_id in inconsistent_docs:
                try:
                    status_doc = to_process_docs[doc_id]
                    file_path = getattr(status_doc, "file_path", "unknown_source")
                    await self.doc_status.delete([doc_id])

                    async with pipeline_status_lock:
                        log_message = (
                            f"Deleted inconsistent entry: {doc_id} ({file_path})"
                        )
                        logger.info(log_message)
                        pipeline_status["latest_message"] = log_message
                        pipeline_status["history_messages"].append(log_message)

                    to_process_docs.pop(doc_id, None)

                except Exception as e:
                    async with pipeline_status_lock:
                        error_message = f"Failed to delete entry: {doc_id} - {str(e)}"
                        logger.error(error_message)
                        pipeline_status["latest_message"] = error_message
                        pipeline_status["history_messages"].append(error_message)

        # Reset PROCESSING and FAILED documents that pass consistency checks to PENDING status
        docs_to_reset = {}
        reset_count = 0

        for doc_id, status_doc in to_process_docs.items():
            content_data = await self.full_docs.get_by_id(doc_id)
            if content_data:
                if hasattr(status_doc, "status") and status_doc.status in [
                    DocStatus.PROCESSING,
                    DocStatus.FAILED,
                ]:
                    docs_to_reset[doc_id] = {
                        "status": DocStatus.PENDING,
                        "content_summary": status_doc.content_summary,
                        "content_length": status_doc.content_length,
                        "created_at": status_doc.created_at,
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                        "file_path": getattr(status_doc, "file_path", "unknown_source"),
                        "track_id": getattr(status_doc, "track_id", ""),
                        "error_msg": "",
                        "metadata": {},
                    }
                    status_doc.status = DocStatus.PENDING
                    reset_count += 1

        if docs_to_reset:
            await self.doc_status.upsert(docs_to_reset)
            async with pipeline_status_lock:
                reset_message = f"Reset {reset_count} documents from PROCESSING/FAILED to PENDING status"
                logger.info(reset_message)
                pipeline_status["latest_message"] = reset_message
                pipeline_status["history_messages"].append(reset_message)

        return to_process_docs

    async def apipeline_process_enqueue_documents(
        self,
        split_by_character: str | None = None,
        split_by_character_only: bool = False,
    ) -> None:
        """Process pending documents by splitting them into chunks, processing"""

        pipeline_status = await get_namespace_data(
            "pipeline_status", workspace=self.workspace
        )
        pipeline_status_lock = get_namespace_lock(
            "pipeline_status", workspace=self.workspace
        )

        # Check if another process is already processing the queue
        async with pipeline_status_lock:
            if not pipeline_status.get("busy", False):
                processing_docs, failed_docs, pending_docs = await asyncio.gather(
                    self.doc_status.get_docs_by_status(DocStatus.PROCESSING),
                    self.doc_status.get_docs_by_status(DocStatus.FAILED),
                    self.doc_status.get_docs_by_status(DocStatus.PENDING),
                )

                to_process_docs: dict[str, DocProcessingStatus] = {}
                to_process_docs.update(processing_docs)
                to_process_docs.update(failed_docs)
                to_process_docs.update(pending_docs)

                if not to_process_docs:
                    logger.info("No documents to process")
                    return

                pipeline_status.update(
                    {
                        "busy": True,
                        "job_name": "Default Job",
                        "job_start": datetime.now(timezone.utc).isoformat(),
                        "docs": 0,
                        "batchs": 0,
                        "cur_batch": 0,
                        "request_pending": False,
                        "cancellation_requested": False,
                        "latest_message": "",
                    }
                )
                del pipeline_status["history_messages"][:]
            else:
                pipeline_status["request_pending"] = True
                logger.info(
                    "Another process is already processing the document queue. Request queued."
                )
                return

        try:
            while True:
                # Check for cancellation
                async with pipeline_status_lock:
                    if pipeline_status.get("cancellation_requested", False):
                        pipeline_status["request_pending"] = False
                        pipeline_status["cancellation_requested"] = False
                        log_message = "Pipeline cancelled by user"
                        logger.info(log_message)
                        pipeline_status["latest_message"] = log_message
                        pipeline_status["history_messages"].append(log_message)
                        return

                if not to_process_docs:
                    log_message = "All enqueued documents have been processed"
                    logger.info(log_message)
                    pipeline_status["latest_message"] = log_message
                    pipeline_status["history_messages"].append(log_message)
                    break

                to_process_docs = await self._validate_and_fix_document_consistency(
                    to_process_docs, pipeline_status, pipeline_status_lock
                )

                if not to_process_docs:
                    log_message = (
                        "No valid documents to process after consistency check"
                    )
                    logger.info(log_message)
                    pipeline_status["latest_message"] = log_message
                    pipeline_status["history_messages"].append(log_message)
                    break

                log_message = f"Processing {len(to_process_docs)} document(s)"
                logger.info(log_message)

                pipeline_status["docs"] = len(to_process_docs)
                pipeline_status["batchs"] = len(to_process_docs)
                pipeline_status["cur_batch"] = 0
                pipeline_status["latest_message"] = log_message
                pipeline_status["history_messages"].append(log_message)

                first_doc_id, first_doc = next(iter(to_process_docs.items()))
                first_doc_path = first_doc.file_path

                if first_doc_path:
                    path_prefix = first_doc_path[:20] + (
                        "..." if len(first_doc_path) > 20 else ""
                    )
                else:
                    path_prefix = "unknown_source"

                total_files = len(to_process_docs)
                job_name = f"{path_prefix}[{total_files} files]"
                pipeline_status["job_name"] = job_name

                processed_count = 0
                semaphore = asyncio.Semaphore(self.max_parallel_insert)

                async def process_document(
                    doc_id: str,
                    status_doc: DocProcessingStatus,
                    split_by_character: str | None,
                    split_by_character_only: bool,
                    pipeline_status: dict,
                    pipeline_status_lock: asyncio.Lock,
                    semaphore: asyncio.Semaphore,
                ) -> None:
                    """Process single document"""
                    file_path = "unknown_source"
                    current_file_number = 0
                    file_extraction_stage_ok = False
                    processing_start_time = int(time.time())
                    first_stage_tasks = []
                    entity_relation_task = None

                    async with semaphore:
                        nonlocal processed_count
                        first_stage_tasks = []
                        entity_relation_task = None
                        try:
                            async with pipeline_status_lock:
                                if pipeline_status.get("cancellation_requested", False):
                                    raise PipelineCancelledException("User cancelled")

                            file_path = getattr(
                                status_doc, "file_path", "unknown_source"
                            )

                            async with pipeline_status_lock:
                                processed_count += 1
                                current_file_number = processed_count
                                pipeline_status["cur_batch"] = processed_count

                                log_message = f"Extracting stage {current_file_number}/{total_files}: {file_path}"
                                logger.info(log_message)
                                pipeline_status["history_messages"].append(log_message)
                                log_message = f"Processing d-id: {doc_id}"
                                logger.info(log_message)
                                pipeline_status["latest_message"] = log_message
                                pipeline_status["history_messages"].append(log_message)

                                if len(pipeline_status["history_messages"]) > 10000:
                                    logger.info(
                                        f"Trimming pipeline history from {len(pipeline_status['history_messages'])} to 5000 messages"
                                    )
                                    pipeline_status["history_messages"] = (
                                        pipeline_status["history_messages"][-5000:]
                                    )

                            content_data = await self.full_docs.get_by_id(doc_id)
                            if not content_data:
                                raise Exception(
                                    f"Document content not found in full_docs for doc_id: {doc_id}"
                                )
                            content = content_data["content"]

                            chunking_result = self.chunking_func(
                                self.tokenizer,
                                content,
                                split_by_character,
                                split_by_character_only,
                                self.chunk_overlap_token_size,
                                self.chunk_token_size,
                            )

                            if inspect.isawaitable(chunking_result):
                                chunking_result = await chunking_result

                            if not isinstance(chunking_result, (list, tuple)):
                                raise TypeError(
                                    f"chunking_func must return a list or tuple of dicts, "
                                    f"got {type(chunking_result)}"
                                )

                            chunks: dict[str, Any] = {
                                compute_mdhash_id(dp["content"], prefix="chunk-"): {
                                    **dp,
                                    "full_doc_id": doc_id,
                                    "file_path": file_path,
                                    "llm_cache_list": [],
                                }
                                for dp in chunking_result
                            }

                            if not chunks:
                                logger.warning("No document chunks to process")

                            processing_start_time = int(time.time())

                            async with pipeline_status_lock:
                                if pipeline_status.get("cancellation_requested", False):
                                    raise PipelineCancelledException("User cancelled")

                            # Stage 1: Process text chunks and docs
                            doc_status_task = asyncio.create_task(
                                self.doc_status.upsert(
                                    {
                                        doc_id: {
                                            "status": DocStatus.PROCESSING,
                                            "chunks_count": len(chunks),
                                            "chunks_list": list(chunks.keys()),
                                            "content_summary": status_doc.content_summary,
                                            "content_length": status_doc.content_length,
                                            "created_at": status_doc.created_at,
                                            "updated_at": datetime.now(
                                                timezone.utc
                                            ).isoformat(),
                                            "file_path": file_path,
                                            "track_id": status_doc.track_id,
                                            "metadata": {
                                                "processing_start_time": processing_start_time
                                            },
                                        }
                                    }
                                )
                            )
                            chunks_vdb_task = asyncio.create_task(
                                self.chunks_vdb.upsert(chunks)
                            )
                            text_chunks_task = asyncio.create_task(
                                self.text_chunks.upsert(chunks)
                            )

                            first_stage_tasks = [
                                doc_status_task,
                                chunks_vdb_task,
                                text_chunks_task,
                            ]
                            entity_relation_task = None

                            await asyncio.gather(*first_stage_tasks)

                            # Stage 2: Extract entities and relations
                            entity_relation_task = asyncio.create_task(
                                self._process_extract_entities(
                                    chunks, pipeline_status, pipeline_status_lock
                                )
                            )
                            chunk_results = await entity_relation_task
                            file_extraction_stage_ok = True

                        except Exception as e:
                            if isinstance(e, PipelineCancelledException):
                                error_msg = f"User cancelled {current_file_number}/{total_files}: {file_path}"
                                logger.warning(error_msg)
                                async with pipeline_status_lock:
                                    pipeline_status["latest_message"] = error_msg
                                    pipeline_status["history_messages"].append(
                                        error_msg
                                    )
                            else:
                                logger.error(traceback.format_exc())
                                error_msg = f"Failed to extract document {current_file_number}/{total_files}: {file_path}"
                                logger.error(error_msg)
                                async with pipeline_status_lock:
                                    pipeline_status["latest_message"] = error_msg
                                    pipeline_status["history_messages"].append(
                                        traceback.format_exc()
                                    )
                                    pipeline_status["history_messages"].append(
                                        error_msg
                                    )

                            all_tasks = first_stage_tasks + (
                                [entity_relation_task] if entity_relation_task else []
                            )
                            for task in all_tasks:
                                if task and not task.done():
                                    task.cancel()

                            if self.llm_response_cache:
                                try:
                                    await self.llm_response_cache.index_done_callback()
                                except Exception as persist_error:
                                    logger.error(
                                        f"Failed to persist LLM cache: {persist_error}"
                                    )

                            processing_end_time = int(time.time())

                            await self.doc_status.upsert(
                                {
                                    doc_id: {
                                        "status": DocStatus.FAILED,
                                        "error_msg": str(e),
                                        "content_summary": status_doc.content_summary,
                                        "content_length": status_doc.content_length,
                                        "created_at": status_doc.created_at,
                                        "updated_at": datetime.now(
                                            timezone.utc
                                        ).isoformat(),
                                        "file_path": file_path,
                                        "track_id": status_doc.track_id,
                                        "metadata": {
                                            "processing_start_time": processing_start_time,
                                            "processing_end_time": processing_end_time,
                                        },
                                    }
                                }
                            )

                        # Merge stage
                        if file_extraction_stage_ok:
                            try:
                                async with pipeline_status_lock:
                                    if pipeline_status.get(
                                        "cancellation_requested", False
                                    ):
                                        raise PipelineCancelledException(
                                            "User cancelled"
                                        )

                                await merge_nodes_and_edges(
                                    chunk_results=chunk_results,
                                    knowledge_graph_inst=self.chunk_entity_relation_graph,
                                    entity_vdb=self.entities_vdb,
                                    relationships_vdb=self.relationships_vdb,
                                    global_config=asdict(self),
                                    full_entities_storage=self.full_entities,
                                    full_relations_storage=self.full_relations,
                                    doc_id=doc_id,
                                    pipeline_status=pipeline_status,
                                    pipeline_status_lock=pipeline_status_lock,
                                    llm_response_cache=self.llm_response_cache,
                                    entity_chunks_storage=self.entity_chunks,
                                    relation_chunks_storage=self.relation_chunks,
                                    current_file_number=current_file_number,
                                    total_files=total_files,
                                    file_path=file_path,
                                )

                                processing_end_time = int(time.time())

                                await self.doc_status.upsert(
                                    {
                                        doc_id: {
                                            "status": DocStatus.PROCESSED,
                                            "chunks_count": len(chunks),
                                            "chunks_list": list(chunks.keys()),
                                            "content_summary": status_doc.content_summary,
                                            "content_length": status_doc.content_length,
                                            "created_at": status_doc.created_at,
                                            "updated_at": datetime.now(
                                                timezone.utc
                                            ).isoformat(),
                                            "file_path": file_path,
                                            "track_id": status_doc.track_id,
                                            "metadata": {
                                                "processing_start_time": processing_start_time,
                                                "processing_end_time": processing_end_time,
                                            },
                                        }
                                    }
                                )

                                await self._insert_done()

                                async with pipeline_status_lock:
                                    log_message = f"Completed processing file {current_file_number}/{total_files}: {file_path}"
                                    logger.info(log_message)
                                    pipeline_status["latest_message"] = log_message
                                    pipeline_status["history_messages"].append(
                                        log_message
                                    )

                            except Exception as e:
                                if isinstance(e, PipelineCancelledException):
                                    error_msg = f"User cancelled during merge {current_file_number}/{total_files}: {file_path}"
                                    logger.warning(error_msg)
                                    async with pipeline_status_lock:
                                        pipeline_status["latest_message"] = error_msg
                                        pipeline_status["history_messages"].append(
                                            error_msg
                                        )
                                else:
                                    logger.error(traceback.format_exc())
                                    error_msg = f"Merging stage failed in document {current_file_number}/{total_files}: {file_path}"
                                    logger.error(error_msg)
                                    async with pipeline_status_lock:
                                        pipeline_status["latest_message"] = error_msg
                                        pipeline_status["history_messages"].append(
                                            traceback.format_exc()
                                        )
                                        pipeline_status["history_messages"].append(
                                            error_msg
                                        )

                                if self.llm_response_cache:
                                    try:
                                        await self.llm_response_cache.index_done_callback()
                                    except Exception as persist_error:
                                        logger.error(
                                            f"Failed to persist LLM cache: {persist_error}"
                                        )

                                processing_end_time = int(time.time())

                                await self.doc_status.upsert(
                                    {
                                        doc_id: {
                                            "status": DocStatus.FAILED,
                                            "error_msg": str(e),
                                            "content_summary": status_doc.content_summary,
                                            "content_length": status_doc.content_length,
                                            "created_at": status_doc.created_at,
                                            "updated_at": datetime.now().isoformat(),
                                            "file_path": file_path,
                                            "track_id": status_doc.track_id,
                                            "metadata": {
                                                "processing_start_time": processing_start_time,
                                                "processing_end_time": processing_end_time,
                                            },
                                        }
                                    }
                                )

                # Create processing tasks for all documents
                doc_tasks = []
                for doc_id, status_doc in to_process_docs.items():
                    doc_tasks.append(
                        process_document(
                            doc_id,
                            status_doc,
                            split_by_character,
                            split_by_character_only,
                            pipeline_status,
                            pipeline_status_lock,
                            semaphore,
                        )
                    )

                try:
                    await asyncio.gather(*doc_tasks)
                except PipelineCancelledException:
                    for task in doc_tasks:
                        if not task.done():
                            task.cancel()
                    await asyncio.wait(doc_tasks, return_when=asyncio.ALL_COMPLETED)
                    return

                # Check if there's a pending request
                has_pending_request = False
                async with pipeline_status_lock:
                    has_pending_request = pipeline_status.get("request_pending", False)
                    if has_pending_request:
                        pipeline_status["request_pending"] = False

                if not has_pending_request:
                    break

                log_message = "Processing additional documents due to pending request"
                logger.info(log_message)
                pipeline_status["latest_message"] = log_message
                pipeline_status["history_messages"].append(log_message)

                processing_docs, failed_docs, pending_docs = await asyncio.gather(
                    self.doc_status.get_docs_by_status(DocStatus.PROCESSING),
                    self.doc_status.get_docs_by_status(DocStatus.FAILED),
                    self.doc_status.get_docs_by_status(DocStatus.PENDING),
                )

                to_process_docs = {}
                to_process_docs.update(processing_docs)
                to_process_docs.update(failed_docs)
                to_process_docs.update(pending_docs)

        finally:
            log_message = "Enqueued document processing pipeline stopped"
            logger.info(log_message)
            async with pipeline_status_lock:
                pipeline_status["busy"] = False
                pipeline_status["cancellation_requested"] = False
                pipeline_status["latest_message"] = log_message
                pipeline_status["history_messages"].append(log_message)
