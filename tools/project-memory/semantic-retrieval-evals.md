# Semantic Retrieval Evals

Use this file to verify that semantic retrieval improves context selection
without replacing exact keyword search.

## Cases

| Query | Mode | Expected Sources | Why It Matters | False Positives To Avoid |
| --- | --- | --- | --- | --- |
| Where is the rule about not loading the whole repo at startup? | hybrid | `AGENTS.md`, `patterns/RAG_STARTUP_FLOW.md` | Startup retrieval must stay token-conscious. | Broad project scans, old summaries. |
| How should we add semantic search without locking into one vector database? | semantic | `patterns/RAG_SYSTEM_STRUCTURE.md`, `patterns/SEMANTIC_RAG_RETRIEVAL.md` | Vector stores must stay behind adapters. | Treating Chroma/Qdrant as the whole RAG system. |
| What should be indexed for embeddings? | hybrid | `patterns/SEMANTIC_RAG_RETRIEVAL.md`, `tools/project-memory/README.md` | Chunks and metadata should be embedded, not whole repos. | Secrets, generated artifacts, app telemetry. |
| How can another agent rebuild this feature on a new framework? | semantic | `tools/project-memory/specs/features/`, `patterns/PROJECT_MEMORY_SPECIFICATIONS.md` | Feature specs should describe portable behavior, business rules, states, failures, verification, and implementation maps. | Only current source files or handoff summaries. |

## Review Notes

- Date:
- Embedding model reference:
- Vector store:
- Collection version:
- Result summary:
- Follow-up chunking or metadata changes:
