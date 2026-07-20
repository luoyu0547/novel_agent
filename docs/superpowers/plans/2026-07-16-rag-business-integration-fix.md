# RAG Business Integration Fix Implementation Plan

**Goal:** Make retrieval a real backend writing dependency while keeping raw retrieval mechanics out of the frontend and preserving safe, immutable source snapshots.

**Architecture:** Build one process-local production retrieval provider from the configured Model Studio and Qdrant adapters, inject it into writing and planning services, and keep database-backed structured anchors as the fallback. Context packages will contain safe writer signals and guard constraints, while Prompt builders receive explicit writer/guard sections and Studio receives only the frozen six-field source projection.

**Verification:** Add focused backend regression tests first, run them red, implement in small slices, then run the affected backend suites and frontend type/unit checks.

## Scope

- Wire `RetrievalService` into production API services; test mode continues using fake adapters unless explicitly injected.
- Load `plot_facts` and safe foreshadowing signals on the legacy context path.
- Remove full locked-chapter bodies from generated context packages; retain recent summaries and retrieve relevant scenes.
- Give writer-visible retrieved items usable text while keeping `source_items` free of raw text and scores.
- Generate non-spoiler guard constraints and pass them to writing, review, and quality-gate prompts.
- Reuse the frozen context package during draft review.
- Sanitize context-package API output so frontend clients do not receive retrieval diagnostics or guard payloads.

## Out Of Scope

- Adding a user-facing raw retrieval/search endpoint.
- Showing Qdrant, embedding, rerank, tenant, or diagnostic data in the frontend.
- Starting the separate retrieval worker inside the FastAPI process.
