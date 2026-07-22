# Extending Cortex

How to add new targets, output formats, and integrations.

## Architecture Overview

The encoder follows a simple flow:

```
scan_vault() 
  → list of VaultNote objects
    ├─ sync_core_context()      (eager file)
    ├─ sync_skill_embeds()      (lazy skill reference.md)
    ├─ sync_projects()          (lazy per-project files)
    ├─ sync_python_agents()     (structured JSON)
    └─ your_custom_sync()       (new target)
```

## Adding a New Target

Example: export notes as **Markdown for a different LLM framework**.

### 1. Add Config Section

In `cortex.yaml.example`:

```yaml
targets:
  my-framework:
    enabled: true
    type: flat-files
    output_dir: "/path/to/my-framework/knowledge"
    include_tiers:
      - core
      - skill:*
      - project
    metadata_format: json  # or yaml, or none
```

### 2. Write the Sync Function

In `cortex/encoder/core.py`, add a new function:

```python
def sync_my_framework(notes, cfg, strip_links, dry):
    """Export notes in my-framework format."""
    out_dir = Path(cfg["output_dir"])
    
    # Filter notes by tier (example)
    include_tiers = cfg.get("include_tiers", ["core"])
    matching = [n for n in notes if n.tier in include_tiers]
    
    print(f"\n--- my-framework: {len(matching)} notes ---")
    
    if not dry:
        out_dir.mkdir(parents=True, exist_ok=True)
    
    for n in sorted(matching, key=lambda n: n.name):
        # Your custom formatting here
        content = f"""
# {n.title()}

**Metadata:**
- id: {n.name}
- type: {n.note_type}
- tier: {n.tier}

## Content

{n.clean_body(strip_links)}
""".strip() + "\n"
        
        write_file(out_dir / f"{n.name}.md", content, dry)
```

### 3. Wire It Into Main

In `main()`, add:

```python
mf = targets.get("my-framework", {})
if mf.get("enabled"):
    sync_my_framework(notes, mf, strip_links, dry)
```

### 4. Test

```bash
cortex encode --dry-run
```

You should see:
```
--- my-framework: 12 notes ---
  [DRY] write /path/to/my-framework/knowledge/note-1.md
  ...
```

Run for real:

```bash
cortex encode
```

## Filtering Patterns

### By Tier

```python
# Get only core + jira notes
eager = [n for n in notes if n.tier in ["core", "jira"]]

# Get all skill notes
skills = [n for n in notes if n.tier.startswith("skill:")]

# Get all projects
projects = [n for n in notes if n.tier == "project"]
```

### By Type

```python
# Get all knowledge/entity notes (for a searchable index)
indexable = [n for n in notes if n.note_type in ["knowledge", "entity"]]

# Get feedback notes (standing preferences)
preferences = [n for n in notes if n.note_type == "feedback"]
```

### By Tags

```python
# Get notes with a specific tag
jira_related = [n for n in notes if "jira" in n.tags]

# Get notes without a tag
not_draft = [n for n in notes if "draft" not in n.tags]
```

### Combined

```python
# Vault-only research notes
research = [
    n for n in notes
    if n.tier == "vault-only" and "research" in n.tags
]
```

## Output Formats

### Markdown (with metadata blocks)

```python
def sync_example_markdown(notes, cfg, strip_links, dry):
    # Output each note as standalone .md
    for n in notes:
        meta_block = f"""---
id: {n.name}
type: {n.note_type}
tier: {n.tier}
tags: {json.dumps(n.tags)}
---

{n.clean_body(strip_links)}
"""
        write_file(Path(...) / f"{n.name}.md", meta_block, dry)
```

### JSON (structured)

```python
def sync_example_json(notes, cfg, dry):
    # Output as a searchable index
    index = {
        "notes": {
            n.name: {
                "title": n.title(),
                "type": n.note_type,
                "tier": n.tier,
                "tags": n.tags,
                "body": n.clean_body(),
            }
            for n in notes
        }
    }
    write_file(Path(cfg["output_file"]), json.dumps(index), dry)
```

### HTML

```python
def sync_example_html(notes, cfg, dry):
    # Convert markdown to HTML
    import html
    lines = ["<html><body>"]
    for n in notes:
        lines.append(f"<h2>{html.escape(n.title())}</h2>")
        # Simple markdown→HTML (no lib; just basic <p> tags)
        for para in n.body.split("\n\n"):
            lines.append(f"<p>{html.escape(para)}</p>")
    lines.append("</body></html>")
    
    write_file(Path(cfg["output_file"]), "\n".join(lines), dry)
```

### YAML

```python
def sync_example_yaml(notes, cfg, dry):
    data = {
        "notes": [n.to_dict() for n in notes]
    }
    write_file(
        Path(cfg["output_file"]),
        yaml.dump(data, default_flow_style=False),
        dry
    )
```

## Advanced: Custom Filtering

If you need complex filtering logic, extend the config:

```yaml
targets:
  my-framework:
    enabled: true
    output_dir: "/path/..."
    only_tiers:
      - core
      - skill:jira
      - skill:clarity
    only_types:
      - knowledge
      - entity
    exclude_tags:
      - draft
      - internal
```

Then in your sync function:

```python
def sync_my_framework(notes, cfg, strip_links, dry):
    only_tiers = cfg.get("only_tiers", [])
    only_types = cfg.get("only_types", [])
    exclude_tags = cfg.get("exclude_tags", [])
    
    matching = [
        n for n in notes
        if (not only_tiers or n.tier in only_tiers)
        and (not only_types or n.note_type in only_types)
        and not any(t in n.tags for t in exclude_tags)
    ]
```

## Idempotency & Dry Runs

Always respect the `dry` flag:

```python
# Good
write_file(path, content, dry)  # helper handles --dry-run

# Bad
if not dry:
    path.write_text(...)
else:
    print("[DRY]...")
```

The `write_file()` helper:
- Checks `dry` flag
- Prints what _would_ happen
- Only writes if `dry=False`
- Creates parent directories

## State Tracking

The encoder saves `_sync/last-sync.json` after each run. Use it for:

- Detecting changed notes (compare hashes)
- Incremental syncs
- Debugging what was encoded

```python
# Example: read last sync state
state_file = vault_path / "_sync" / "last-sync.json"
if state_file.exists():
    last_state = json.loads(state_file.read_text())
    # Compare last_state["notes"] with current notes
```

## Testing Your Target

Create a minimal vault for testing:

```bash
mkdir test-vault
cd test-vault
mkdir -p _sync knowledge feedback
```

Add a few notes with frontmatter, then:

```bash
# Copy config
cp /path/to/cortex.yaml.example _sync/cortex.yaml

# Edit cortex.yaml:
vault_path: "."
targets:
  my-framework:
    enabled: true
    output_dir: "./encoded"

# Test
cortex encode --config _sync/cortex.yaml --dry-run
cortex encode --config _sync/cortex.yaml
```

## Common Extensions

### 1. Slack Export

Encode notes into Slack messages:

```python
def sync_slack(notes, cfg, strip_links, dry):
    # Post to Slack channel per skill
    for skill, ns in by_skill.items():
        message = f"*{skill}*\n" + "\n".join(n.clean_body() for n in ns)
        # Call Slack API (mock here)
        if not dry:
            slack_post(cfg["webhook_url"], message)
```

### 2. PDF Generation

Export as a PDF manual:

```python
def sync_pdf(notes, cfg, strip_links, dry):
    from reportlab.pdfgen import canvas
    # Build PDF from notes
    if not dry:
        c = canvas.Canvas(cfg["output_file"])
        for n in notes:
            c.drawString(100, 750, n.title())
            # ... etc
        c.save()
```

### 3. Wiki/Docusaurus Export

For static site generators:

```python
def sync_docusaurus(notes, cfg, strip_links, dry):
    # Output with Docusaurus frontmatter
    for n in notes:
        doc = f"""---
id: {n.name}
title: {n.title()}
sidebar_label: {n.title()}
---

{n.clean_body(strip_links)}
"""
        write_file(out_dir / f"{n.name}.md", doc, dry)
```

### 4. Elasticsearch Indexing

Index notes for full-text search:

```python
def sync_elasticsearch(notes, cfg, strip_links, dry):
    from elasticsearch import Elasticsearch
    es = Elasticsearch([cfg["es_host"]])
    for n in notes:
        es.index(index="cortex", doc_type="note", id=n.name, body={
            "title": n.title(),
            "type": n.note_type,
            "content": n.clean_body(strip_links),
        })
```

## Questions?

Check:
- `cortex/encoder/core.py` — the reference implementation
- `cortex.yaml.example` — all target types
