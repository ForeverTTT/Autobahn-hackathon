from __future__ import annotations

import traceback
import asyncio
import time
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any
from rag.constants import GRAPH_FIELD_SEP
from rag.utils import (
    always_get_an_event_loop,
    compute_mdhash_id,
    logger,
    subtract_source_ids,
    make_relation_chunk_key,
)
from rag.storage.shared_storage import (
    get_namespace_data,
    get_namespace_lock,
)
from rag.base import (
    DocStatus,
    DeletionResult,
)
from rag.operate import (
    rebuild_knowledge_from_chunks,
)


class RAGDeleteMixin:
    """Document and entity/relation deletion methods."""

    async def adelete_by_doc_id(
        self, doc_id: str, delete_llm_cache: bool = False
    ) -> DeletionResult:
        """Delete a document and all its related data, including chunks, graph elements."""
        pipeline_status = await get_namespace_data(
            "pipeline_status", workspace=self.workspace
        )
        pipeline_status_lock = get_namespace_lock(
            "pipeline_status", workspace=self.workspace
        )

        we_acquired_pipeline = False

        async with pipeline_status_lock:
            if not pipeline_status.get("busy", False):
                we_acquired_pipeline = True
                pipeline_status.update(
                    {
                        "busy": True,
                        "job_name": "Single document deletion",
                        "job_start": datetime.now(timezone.utc).isoformat(),
                        "docs": 1,
                        "batchs": 1,
                        "cur_batch": 0,
                        "request_pending": False,
                        "cancellation_requested": False,
                        "latest_message": f"Starting deletion for document: {doc_id}",
                    }
                )
                pipeline_status["history_messages"][:] = [
                    f"Starting deletion for document: {doc_id}"
                ]
            else:
                job_name = pipeline_status.get("job_name", "").lower()
                if not job_name.startswith("deleting") or "document" not in job_name:
                    return DeletionResult(
                        status="not_allowed",
                        doc_id=doc_id,
                        message=f"Deletion not allowed: current job '{pipeline_status.get('job_name')}' is not a document deletion job",
                        status_code=403,
                        file_path=None,
                    )

        deletion_operations_started = False
        original_exception = None
        doc_llm_cache_ids: list[str] = []

        async with pipeline_status_lock:
            log_message = f"Starting deletion process for document {doc_id}"
            logger.info(log_message)
            pipeline_status["latest_message"] = log_message
            pipeline_status["history_messages"].append(log_message)

        try:
            # 1. Get the document status
            doc_status_data = await self.doc_status.get_by_id(doc_id)
            file_path = doc_status_data.get("file_path") if doc_status_data else None
            if not doc_status_data:
                logger.warning(f"Document {doc_id} not found")
                return DeletionResult(
                    status="not_found",
                    doc_id=doc_id,
                    message=f"Document {doc_id} not found.",
                    status_code=404,
                    file_path="",
                )

            raw_status = doc_status_data.get("status")
            try:
                doc_status = DocStatus(raw_status)
            except ValueError:
                doc_status = raw_status

            if doc_status != DocStatus.PROCESSED:
                status_text = (
                    doc_status.value
                    if isinstance(doc_status, DocStatus)
                    else str(doc_status)
                )
                warning_msg = f"Deleting {doc_id} {file_path}(previous status: {status_text})"
                logger.info(warning_msg)
                async with pipeline_status_lock:
                    pipeline_status["latest_message"] = warning_msg
                    pipeline_status["history_messages"].append(warning_msg)

            # 2. Get chunk IDs
            chunk_ids = set(doc_status_data.get("chunks_list", []))

            if not chunk_ids:
                logger.warning(f"No chunks found for document {doc_id}")
                deletion_operations_started = True
                try:
                    await self.full_docs.delete([doc_id])
                    await self.doc_status.delete([doc_id])
                except Exception as e:
                    logger.error(
                        f"Failed to delete document {doc_id} with no chunks: {e}"
                    )
                    raise Exception(f"Failed to delete document entry: {e}") from e

                async with pipeline_status_lock:
                    log_message = (
                        f"Document deleted without associated chunks: {doc_id}"
                    )
                    logger.info(log_message)
                    pipeline_status["latest_message"] = log_message
                    pipeline_status["history_messages"].append(log_message)

                return DeletionResult(
                    status="success",
                    doc_id=doc_id,
                    message=log_message,
                    status_code=200,
                    file_path=file_path,
                )

            deletion_operations_started = True

            # 3. Collect LLM cache IDs if requested
            if delete_llm_cache and chunk_ids:
                if not self.llm_response_cache:
                    logger.info(
                        "Skipping LLM cache collection for document %s because cache storage is unavailable",
                        doc_id,
                    )
                elif not self.text_chunks:
                    logger.info(
                        "Skipping LLM cache collection for document %s because text chunk storage is unavailable",
                        doc_id,
                    )
                else:
                    try:
                        chunk_data_list = await self.text_chunks.get_by_ids(
                            list(chunk_ids)
                        )
                        seen_cache_ids: set[str] = set()
                        for chunk_data in chunk_data_list:
                            if not chunk_data or not isinstance(chunk_data, dict):
                                continue
                            cache_ids = chunk_data.get("llm_cache_list", [])
                            if not isinstance(cache_ids, list):
                                continue
                            for cache_id in cache_ids:
                                if (
                                    isinstance(cache_id, str)
                                    and cache_id
                                    and cache_id not in seen_cache_ids
                                ):
                                    doc_llm_cache_ids.append(cache_id)
                                    seen_cache_ids.add(cache_id)
                        if doc_llm_cache_ids:
                            logger.info(
                                "Collected %d LLM cache entries for document %s",
                                len(doc_llm_cache_ids),
                                doc_id,
                            )
                    except Exception as cache_collect_error:
                        logger.error(
                            "Failed to collect LLM cache ids for document %s: %s",
                            doc_id,
                            cache_collect_error,
                        )
                        raise Exception(
                            f"Failed to collect LLM cache ids for document {doc_id}: {cache_collect_error}"
                        ) from cache_collect_error

            # 4. Analyze affected entities and relationships
            entities_to_delete = set()
            entities_to_rebuild = {}
            relationships_to_delete = set()
            relationships_to_rebuild = {}
            entity_chunk_updates: dict[str, list[str]] = {}
            relation_chunk_updates: dict[tuple[str, str], list[str]] = {}

            try:
                doc_entities_data = await self.full_entities.get_by_id(doc_id)
                doc_relations_data = await self.full_relations.get_by_id(doc_id)

                affected_nodes = []
                affected_edges = []

                if doc_entities_data and "entity_names" in doc_entities_data:
                    entity_names = doc_entities_data["entity_names"]
                    nodes_dict = await self.chunk_entity_relation_graph.get_nodes_batch(
                        entity_names
                    )
                    for entity_name in entity_names:
                        node_data = nodes_dict.get(entity_name)
                        if node_data:
                            if "id" not in node_data:
                                node_data["id"] = entity_name
                            affected_nodes.append(node_data)

                if doc_relations_data and "relation_pairs" in doc_relations_data:
                    relation_pairs = doc_relations_data["relation_pairs"]
                    edge_pairs_dicts = [
                        {"src": pair[0], "tgt": pair[1]} for pair in relation_pairs
                    ]
                    edges_dict = await self.chunk_entity_relation_graph.get_edges_batch(
                        edge_pairs_dicts
                    )
                    for pair in relation_pairs:
                        src, tgt = pair[0], pair[1]
                        edge_data = edges_dict.get((src, tgt))
                        if edge_data:
                            if "source" not in edge_data:
                                edge_data["source"] = src
                            if "target" not in edge_data:
                                edge_data["target"] = tgt
                            affected_edges.append(edge_data)

            except Exception as e:
                logger.error(f"Failed to analyze affected graph elements: {e}")
                raise Exception(f"Failed to analyze graph dependencies: {e}") from e

            try:
                # Process entities
                for node_data in affected_nodes:
                    node_label = node_data.get("entity_id")
                    if not node_label:
                        continue

                    existing_sources: list[str] = []
                    if self.entity_chunks:
                        stored_chunks = await self.entity_chunks.get_by_id(node_label)
                        if stored_chunks and isinstance(stored_chunks, dict):
                            existing_sources = [
                                chunk_id
                                for chunk_id in stored_chunks.get("chunk_ids", [])
                                if chunk_id
                            ]

                    if not existing_sources and node_data.get("source_id"):
                        existing_sources = [
                            chunk_id
                            for chunk_id in node_data["source_id"].split(
                                GRAPH_FIELD_SEP
                            )
                            if chunk_id
                        ]

                    if not existing_sources:
                        entities_to_delete.add(node_label)
                        entity_chunk_updates[node_label] = []
                        continue

                    remaining_sources = subtract_source_ids(existing_sources, chunk_ids)

                    if not remaining_sources:
                        entities_to_delete.add(node_label)
                        entity_chunk_updates[node_label] = []
                    elif remaining_sources != existing_sources:
                        entities_to_rebuild[node_label] = remaining_sources
                        entity_chunk_updates[node_label] = remaining_sources

                async with pipeline_status_lock:
                    log_message = f"Found {len(entities_to_rebuild)} affected entities"
                    logger.info(log_message)
                    pipeline_status["latest_message"] = log_message
                    pipeline_status["history_messages"].append(log_message)

                # Process relationships
                for edge_data in affected_edges:
                    src = edge_data.get("source")
                    tgt = edge_data.get("target")

                    if not src or not tgt or "source_id" not in edge_data:
                        continue

                    edge_tuple = tuple(sorted((src, tgt)))
                    if (
                        edge_tuple in relationships_to_delete
                        or edge_tuple in relationships_to_rebuild
                    ):
                        continue

                    existing_sources: list[str] = []
                    if self.relation_chunks:
                        storage_key = make_relation_chunk_key(src, tgt)
                        stored_chunks = await self.relation_chunks.get_by_id(
                            storage_key
                        )
                        if stored_chunks and isinstance(stored_chunks, dict):
                            existing_sources = [
                                chunk_id
                                for chunk_id in stored_chunks.get("chunk_ids", [])
                                if chunk_id
                            ]

                    if not existing_sources:
                        existing_sources = [
                            chunk_id
                            for chunk_id in edge_data["source_id"].split(
                                GRAPH_FIELD_SEP
                            )
                            if chunk_id
                        ]

                    if not existing_sources:
                        relationships_to_delete.add(edge_tuple)
                        relation_chunk_updates[edge_tuple] = []
                        continue

                    remaining_sources = subtract_source_ids(existing_sources, chunk_ids)

                    if not remaining_sources:
                        relationships_to_delete.add(edge_tuple)
                        relation_chunk_updates[edge_tuple] = []
                    elif remaining_sources != existing_sources:
                        relationships_to_rebuild[edge_tuple] = remaining_sources
                        relation_chunk_updates[edge_tuple] = remaining_sources

                async with pipeline_status_lock:
                    log_message = (
                        f"Found {len(relationships_to_rebuild)} affected relations"
                    )
                    logger.info(log_message)
                    pipeline_status["latest_message"] = log_message
                    pipeline_status["history_messages"].append(log_message)

                current_time = int(time.time())

                if entity_chunk_updates and self.entity_chunks:
                    entity_upsert_payload = {}
                    for entity_name, remaining in entity_chunk_updates.items():
                        if not remaining:
                            continue
                        entity_upsert_payload[entity_name] = {
                            "chunk_ids": remaining,
                            "count": len(remaining),
                            "updated_at": current_time,
                        }
                    if entity_upsert_payload:
                        await self.entity_chunks.upsert(entity_upsert_payload)

                if relation_chunk_updates and self.relation_chunks:
                    relation_upsert_payload = {}
                    for edge_tuple, remaining in relation_chunk_updates.items():
                        if not remaining:
                            continue
                        storage_key = make_relation_chunk_key(*edge_tuple)
                        relation_upsert_payload[storage_key] = {
                            "chunk_ids": remaining,
                            "count": len(remaining),
                            "updated_at": current_time,
                        }
                    if relation_upsert_payload:
                        await self.relation_chunks.upsert(relation_upsert_payload)

            except Exception as e:
                logger.error(f"Failed to process graph analysis results: {e}")
                raise Exception(f"Failed to process graph dependencies: {e}") from e

            # 5. Delete chunks from storage
            if chunk_ids:
                try:
                    await self.chunks_vdb.delete(chunk_ids)
                    await self.text_chunks.delete(chunk_ids)

                    async with pipeline_status_lock:
                        log_message = (
                            f"Successfully deleted {len(chunk_ids)} chunks from storage"
                        )
                        logger.info(log_message)
                        pipeline_status["latest_message"] = log_message
                        pipeline_status["history_messages"].append(log_message)
                except Exception as e:
                    logger.error(f"Failed to delete chunks: {e}")
                    raise Exception(f"Failed to delete document chunks: {e}") from e

            # 6. Delete relationships with no remaining sources
            if relationships_to_delete:
                try:
                    rel_ids_to_delete = []
                    for src, tgt in relationships_to_delete:
                        rel_ids_to_delete.extend(
                            [
                                compute_mdhash_id(src + tgt, prefix="rel-"),
                                compute_mdhash_id(tgt + src, prefix="rel-"),
                            ]
                        )
                    await self.relationships_vdb.delete(rel_ids_to_delete)
                    await self.chunk_entity_relation_graph.remove_edges(
                        list(relationships_to_delete)
                    )

                    if self.relation_chunks:
                        relation_storage_keys = [
                            make_relation_chunk_key(src, tgt)
                            for src, tgt in relationships_to_delete
                        ]
                        await self.relation_chunks.delete(relation_storage_keys)

                    async with pipeline_status_lock:
                        log_message = f"Successfully deleted {len(relationships_to_delete)} relations"
                        logger.info(log_message)
                        pipeline_status["latest_message"] = log_message
                        pipeline_status["history_messages"].append(log_message)
                except Exception as e:
                    logger.error(f"Failed to delete relationships: {e}")
                    raise Exception(f"Failed to delete relationships: {e}") from e

            # 7. Delete entities with no remaining sources
            if entities_to_delete:
                try:
                    nodes_edges_dict = (
                        await self.chunk_entity_relation_graph.get_nodes_edges_batch(
                            list(entities_to_delete)
                        )
                    )

                    edges_to_delete = set()
                    for entity, edges in nodes_edges_dict.items():
                        if edges:
                            for src, tgt in edges:
                                edge_tuple = tuple(sorted((src, tgt)))
                                edges_to_delete.add(edge_tuple)

                    # Clean residual edges from VDB and storage
                    if edges_to_delete:
                        rel_ids_to_delete = []
                        for src, tgt in edges_to_delete:
                            rel_ids_to_delete.extend(
                                [
                                    compute_mdhash_id(src + tgt, prefix="rel-"),
                                    compute_mdhash_id(tgt + src, prefix="rel-"),
                                ]
                            )
                        await self.relationships_vdb.delete(rel_ids_to_delete)

                        if self.relation_chunks:
                            relation_storage_keys = [
                                make_relation_chunk_key(src, tgt)
                                for src, tgt in edges_to_delete
                            ]
                            await self.relation_chunks.delete(relation_storage_keys)

                        logger.info(
                            f"Cleaned {len(edges_to_delete)} residual edges from VDB and chunk-tracking storage"
                        )

                    await self.chunk_entity_relation_graph.remove_nodes(
                        list(entities_to_delete)
                    )

                    entity_vdb_ids = [
                        compute_mdhash_id(entity, prefix="ent-")
                        for entity in entities_to_delete
                    ]
                    await self.entities_vdb.delete(entity_vdb_ids)

                    if self.entity_chunks:
                        await self.entity_chunks.delete(list(entities_to_delete))

                    async with pipeline_status_lock:
                        log_message = (
                            f"Successfully deleted {len(entities_to_delete)} entities"
                        )
                        logger.info(log_message)
                        pipeline_status["latest_message"] = log_message
                        pipeline_status["history_messages"].append(log_message)
                except Exception as e:
                    logger.error(f"Failed to delete entities: {e}")
                    raise Exception(f"Failed to delete entities: {e}") from e

            await self._insert_done()

            # 8. Rebuild entities and relationships from remaining chunks
            if entities_to_rebuild or relationships_to_rebuild:
                try:
                    await rebuild_knowledge_from_chunks(
                        entities_to_rebuild=entities_to_rebuild,
                        relationships_to_rebuild=relationships_to_rebuild,
                        knowledge_graph_inst=self.chunk_entity_relation_graph,
                        entities_vdb=self.entities_vdb,
                        relationships_vdb=self.relationships_vdb,
                        text_chunks_storage=self.text_chunks,
                        llm_response_cache=self.llm_response_cache,
                        global_config=asdict(self),
                        pipeline_status=pipeline_status,
                        pipeline_status_lock=pipeline_status_lock,
                        entity_chunks_storage=self.entity_chunks,
                        relation_chunks_storage=self.relation_chunks,
                    )
                except Exception as e:
                    logger.error(f"Failed to rebuild knowledge from chunks: {e}")
                    raise Exception(f"Failed to rebuild knowledge graph: {e}") from e

            # 9. Delete from full_entities and full_relations
            try:
                await self.full_entities.delete([doc_id])
                await self.full_relations.delete([doc_id])
            except Exception as e:
                logger.error(f"Failed to delete from full_entities/full_relations: {e}")
                raise Exception(
                    f"Failed to delete from full_entities/full_relations: {e}"
                ) from e

            # 10. Delete original document and status
            try:
                await self.full_docs.delete([doc_id])
                await self.doc_status.delete([doc_id])
            except Exception as e:
                logger.error(f"Failed to delete document and status: {e}")
                raise Exception(f"Failed to delete document and status: {e}") from e

            if delete_llm_cache and doc_llm_cache_ids and self.llm_response_cache:
                try:
                    await self.llm_response_cache.delete(doc_llm_cache_ids)
                    log_message = f"Successfully deleted {len(doc_llm_cache_ids)} LLM cache entries for document {doc_id}"
                    logger.info(log_message)
                    async with pipeline_status_lock:
                        pipeline_status["latest_message"] = log_message
                        pipeline_status["history_messages"].append(log_message)
                except Exception as cache_delete_error:
                    log_message = f"Failed to delete LLM cache for document {doc_id}: {cache_delete_error}"
                    logger.error(log_message)
                    async with pipeline_status_lock:
                        pipeline_status["latest_message"] = log_message
                        pipeline_status["history_messages"].append(log_message)

            return DeletionResult(
                status="success",
                doc_id=doc_id,
                message=log_message,
                status_code=200,
                file_path=file_path,
            )

        except Exception as e:
            original_exception = e
            error_message = f"Error while deleting document {doc_id}: {e}"
            logger.error(error_message)
            logger.error(traceback.format_exc())
            return DeletionResult(
                status="fail",
                doc_id=doc_id,
                message=error_message,
                status_code=500,
                file_path=file_path,
            )

        finally:
            if deletion_operations_started:
                try:
                    await self._insert_done()
                except Exception as persistence_error:
                    persistence_error_msg = f"Failed to persist data after deletion attempt for {doc_id}: {persistence_error}"
                    logger.error(persistence_error_msg)
                    if original_exception is None:
                        return DeletionResult(
                            status="fail",
                            doc_id=doc_id,
                            message=f"Deletion completed but failed to persist changes: {persistence_error}",
                            status_code=500,
                            file_path=file_path,
                        )

            if we_acquired_pipeline:
                async with pipeline_status_lock:
                    pipeline_status["busy"] = False
                    pipeline_status["cancellation_requested"] = False
                    completion_msg = (
                        f"Deletion process completed for document: {doc_id}"
                    )
                    pipeline_status["latest_message"] = completion_msg
                    pipeline_status["history_messages"].append(completion_msg)
                    logger.info(completion_msg)

    async def adelete_by_entity(self, entity_name: str) -> DeletionResult:
        """Asynchronously delete an entity and all its relationships."""
        from rag.utils_graph import adelete_by_entity

        return await adelete_by_entity(
            self.chunk_entity_relation_graph,
            self.entities_vdb,
            self.relationships_vdb,
            entity_name,
        )

    def delete_by_entity(self, entity_name: str) -> DeletionResult:
        """Synchronously delete an entity and all its relationships."""
        loop = always_get_an_event_loop()
        return loop.run_until_complete(self.adelete_by_entity(entity_name))

    async def adelete_by_relation(
        self, source_entity: str, target_entity: str
    ) -> DeletionResult:
        """Asynchronously delete a relation between two entities."""
        from rag.utils_graph import adelete_by_relation

        return await adelete_by_relation(
            self.chunk_entity_relation_graph,
            self.relationships_vdb,
            source_entity,
            target_entity,
        )

    def delete_by_relation(
        self, source_entity: str, target_entity: str
    ) -> DeletionResult:
        """Synchronously delete a relation between two entities."""
        loop = always_get_an_event_loop()
        return loop.run_until_complete(
            self.adelete_by_relation(source_entity, target_entity)
        )
