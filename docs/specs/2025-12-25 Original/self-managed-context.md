# Self-Managed Context

Migrated from `.specs/00 Bootstrap/Self Managed Context.md`.

## Idea
Let the agent actively manage its own context (summarize, prune, archive) rather than passively consuming a sliding window.

## Enables
- Infinite-horizon tasks via summarization/archival
- Fast topic switching with explicit state saves
- Cost/latency control by trimming noisy logs
- Reduced hallucination via noise removal

## Tooling primitives
- **Scratchpad**: `update_scratchpad(content)` (pinned summary)
- **Archivist**: `archive_memory(key, content)` + `recall_memory(query)`
- **Garbage collector**: `summarize_and_clear_history(keep_last_n)`

## Implementation sketch
Modify the message list *before* the next model call:
1) Agent calls tool
2) System updates the conversation buffer
3) System confirms action in a short system message
