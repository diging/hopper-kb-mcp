# Hopper Knowledge Base MCP

**Purpose**: A small knowledge base MPC backend that extracts content from websites and files, embeds text, and stores searchable chunks for retrieval.

**Ingestion**: Downloads websites, extracts titles, partitions content into markdown elements, cleans and groups paragraphs, and chunks content by title for meaningful units.

**Embeddings**: Uses `fastembed.TextEmbedding` to produce vector embeddings for each chunk.

**Storage**: Persists Document and DocumentChunk records to a backing Postgres database utilizing the PGVector extension (via the project's DB layer).

**Tech stack**: Python, httpx, unstructured (partitioning/cleaning), fastembed (embeddings), Postgres, Docker for local deployment.

**Deployment / quick run**: Make sure the folder `postgres_data` exists. Start the stack with Docker Compose:

```
docker compose up
```

**Who it's for**: Useful as a lightweight knowledge‑base ingestion pipeline for building vector search or RAG systems.