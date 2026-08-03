# 0001 — Postgres + Link Graph for the Hub Vault

The cortex hub vault uses Postgres with a link graph (FTS + recursive CTEs) as its storage and retrieval engine, not a dedicated graph database, vector database, or search engine.

**Context.** The hub is a shared knowledge store for agents across teams. Users push local Obsidian notes to the hub; the hub parses, links, and indexes them. Agents query the hub by traversing the link graph from a starting point. We need full-text search, link traversal, and eventual semantic search — all without adding a second storage system.

**Considered options:**

- **SQLite + FTS5** — correct at personal scale, but concurrent writes from many agents serialize. At company scale with row-level security needs, it doesn't fit without a wrapper that would effectively reimplement Postgres.
- **Neo4j** — purpose-built for graph traversal, but introduces a new server, new query language (Cypher), and doesn't natively do full-text or vector search. We'd need to pair it with something else.
- **Dedicated vector DB (Pinecone/Qdrant)** — excellent at embedding search, poor at link traversal. Would need a second store for the graph.
- **Elasticsearch** — full-text powerhouse, but no link graph support without external traversal logic. Two systems to operate.
- **Postgres + pgvector** — one system. Link graph via recursive CTEs. Full-text via `tsvector`/`tsquery`. Semantic search via `pgvector`. Row-level security. Every team already knows how to operate it. No new infrastructure.

**Chosen.** Postgres.

**Consequences.** Ingestion pipeline must extract `[[wikilinks]]` and tags and materialize them into `notes` and `links` tables. Link traversal queries use recursive CTEs, which are less expressive than a graph DB's traversal language — but for a vault's link structure (notes pointing to notes, no weighted edges or complex path predicates), they're sufficient. pgvector adds embedding support when we need it, with no schema migration beyond a column.
