# Cortex-first lookup rule

The Cortex vault (`~/cortex-ai`) is this machine's persistent memory of projects,
code locations, systems, people, and past decisions. It often already knows where
things live — using it avoids wasted filesystem searches.

## Mandatory: search cortex before filesystem exploration

Before you do **either** of the following, you MUST first run a cortex search:

1. Spawning any subagent to explore the filesystem (the `task` tool with
   `explore`, `general`, or similar agents), **or**
2. Running broad filesystem searches intended to *locate* files or code
   (`glob`/`find` for unknown paths, `grep` for "where is X").

Run, at minimum:

```
cortex memory search "<topic>"
```

For a deeper answer use `cortex memory think "<topic>"` (full text + related
notes in one pass), and `cortex memory get <id>` to read a complete note.

### Use the dedicated tools

First-class `cortex_search` and `cortex_get` tools are available — prefer
calling them over a raw `bash cortex ...` call:
- `cortex_search` — list matching notes for a topic.
- `cortex_get` — return the full content of a note by id.

### Decision rule

- If cortex returns a relevant hit, use it and resolve the question from memory
  before touching the filesystem.
- Only fall back to filesystem exploration (subagent / glob / grep) when cortex
  has nothing useful for the question.
