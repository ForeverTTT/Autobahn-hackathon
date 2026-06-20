STORAGE_IMPLEMENTATIONS = {
    "KV_STORAGE": {
        "implementations": [
            "JsonKVStorage",
            "RedisKVStorage",
            "PGKVStorage",
            "MongoKVStorage",
        ],
        "required_methods": ["get_by_id", "upsert"],
    },
    "GRAPH_STORAGE": {
        "implementations": [
            "Neo4JStorage",
            "PGGraphStorage",
            "MongoGraphStorage",
            "MemgraphStorage",
        ],
        "required_methods": ["upsert_node", "upsert_edge"],
    },
    "VECTOR_STORAGE": {
        "implementations": [
            "NanoVectorDBStorage",
            "MilvusVectorDBStorage",
            "PGVectorStorage",
            "FaissVectorDBStorage",
            "QdrantVectorDBStorage",
            "MongoVectorDBStorage",
            # "ChromaVectorDBStorage",
        ],
        "required_methods": ["query", "upsert"],
    },
    "DOC_STATUS_STORAGE": {
        "implementations": [
            "JsonDocStatusStorage",
            "RedisDocStatusStorage",
            "PGDocStatusStorage",
            "MongoDocStatusStorage",
        ],
        "required_methods": ["get_docs_by_status"],
    },
}

# Storage implementation environment variable without default value
STORAGE_ENV_REQUIREMENTS: dict[str, list[str]] = {
    # KV Storage Implementations
    "JsonKVStorage": [],
    "MongoKVStorage": [
        "MONGO_URI",
        "MONGO_DATABASE",
    ],
    "RedisKVStorage": ["REDIS_URI"],
    "PGKVStorage": ["POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DATABASE"],
    # Graph Storage Implementations
    "Neo4JStorage": ["NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD"],
    "MongoGraphStorage": [
        "MONGO_URI",
        "MONGO_DATABASE",
    ],
    "MemgraphStorage": ["MEMGRAPH_URI"],
    "AGEStorage": [
        "AGE_POSTGRES_DB",
        "AGE_POSTGRES_USER",
        "AGE_POSTGRES_PASSWORD",
    ],
    "PGGraphStorage": [
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_DATABASE",
    ],
    # Vector Storage Implementations
    "NanoVectorDBStorage": [],
    "MilvusVectorDBStorage": [
        "MILVUS_URI",
        "MILVUS_DB_NAME",
    ],
    # "ChromaVectorDBStorage": [],
    "PGVectorStorage": ["POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DATABASE"],
    "FaissVectorDBStorage": [],
    "QdrantVectorDBStorage": ["QDRANT_URL"],  # QDRANT_API_KEY has default value None
    "MongoVectorDBStorage": [
        "MONGO_URI",
        "MONGO_DATABASE",
    ],
    # Document Status Storage Implementations
    "JsonDocStatusStorage": [],
    "RedisDocStatusStorage": ["REDIS_URI"],
    "PGDocStatusStorage": ["POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DATABASE"],
    "MongoDocStatusStorage": [
        "MONGO_URI",
        "MONGO_DATABASE",
    ],
}

# Storage implementation module mapping
STORAGES = {
    "JsonKVStorage": ".storage.json_storage",
    "NanoVectorDBStorage": ".storage.nano_vector_db",
    "JsonDocStatusStorage": ".storage.json_storage",
    "Neo4JStorage": ".storage.neo4j",
    "MilvusVectorDBStorage": ".storage.milvus_impl",
    "MongoKVStorage": ".storage.mongo_impl",
    "MongoDocStatusStorage": ".storage.mongo_impl",
    "MongoGraphStorage": ".storage.mongo_impl",
    "MongoVectorDBStorage": ".storage.mongo_impl",
    "RedisKVStorage": ".storage.redis_impl",
    "RedisDocStatusStorage": ".storage.redis_impl",
    "ChromaVectorDBStorage": ".storage.chroma_impl",
    "PGKVStorage": ".storage.postgres_impl",
    "PGVectorStorage": ".storage.postgres_impl",
    "AGEStorage": ".storage.age_impl",
    "PGGraphStorage": ".storage.postgres_impl",
    "PGDocStatusStorage": ".storage.postgres_impl",
    "FaissVectorDBStorage": ".storage.faiss_impl",
    "QdrantVectorDBStorage": ".storage.qdrant_impl",
    "MemgraphStorage": ".storage.memgraph_impl",
}


def verify_storage_implementation(storage_type: str, storage_name: str) -> None:
    """Verify if storage implementation is compatible with specified storage type

    Args:
        storage_type: Storage type (KV_STORAGE, GRAPH_STORAGE etc.)
        storage_name: Storage implementation name

    Raises:
        ValueError: If storage implementation is incompatible or missing required methods
    """
    if storage_type not in STORAGE_IMPLEMENTATIONS:
        raise ValueError(f"Unknown storage type: {storage_type}")

    storage_info = STORAGE_IMPLEMENTATIONS[storage_type]
    if storage_name not in storage_info["implementations"]:
        raise ValueError(
            f"Storage implementation '{storage_name}' is not compatible with {storage_type}. "
            f"Compatible implementations are: {', '.join(storage_info['implementations'])}"
        )
