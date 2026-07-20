# Migration Guide

## How Cortex Versioning Works

Cortex tracks two independent numbers:

| Number | File | What it means |
|--------|------|---------------|
| Release version | `VERSION` | SemVer — the human-facing release number |
| Schema version | `SCHEMA_VERSION` | Integer — the on-disk data contract |

The schema version only changes when the on-disk format changes (note
frontmatter, `memory.json` structure, config keys). A routine PATCH or MINOR
release never bumps the schema.

## Automatic Migration

On every run, the encoder compares the code's schema version against the
one stamped in the vault's `memory.json`:

- **Equal** — proceed normally.
- **Code newer** — auto-backup `_sync/`, run registered migrations, proceed.
- **Code older** — refuse to run (no silent downgrades).

Migration is automatic and idempotent. It only touches Cortex's own working
files — never your notes.

## Manual Migration

Automated migration is a future phase. For now, manual schema changes
require these steps:

### Step 1: Back up your vault

```bash
cp -r /path/to/your/vault /path/to/your/vault.bak
```

### Step 2: Check current state

```bash
cortex encode --check
```

This reports the code schema version and the vault schema version.

### Step 3: Review the changelog

Check [CHANGELOG.md](../CHANGELOG.md) for what changed between schema
versions and whether any note frontmatter adjustments are needed.

### Step 4: Update notes if required

If the schema change adds new required frontmatter fields, update your
notes. Common changes:

- Adding a new field to frontmatter (e.g., `category`)
- Changing allowed values for `type` or `tier`
- Restructuring `memory.json` output format

### Step 5: Re-encode

```bash
cortex encode
```

The encoder will stamp the new schema version into `memory.json._meta`.

### Step 6: Verify

```bash
cortex encode --check
cortex status
```

Both should report compatible schema versions.

## Schema Version History

| Version | Changes |
|---------|---------|
| 1 | Initial schema |
| 2 | Added structured `memory.json` output with `_meta` block |

## Path Change: `distilled/` → `encoded/`

As part of the rename from "distill" to "encode", the output directory has
moved from `_sync/distilled/` to `_sync/encoded/`. If you have an existing
vault with `_sync/distilled/`, simply rename it:

```bash
mv /path/to/your/vault/_sync/distilled /path/to/your/vault/_sync/encoded
```

Or let `cortex install --upgrade` handle it — it will create the new
directory on the next run.

## Reverting

If something goes wrong, restore from your backup:

```bash
rm -rf /path/to/your/vault
cp -r /path/to/your/vault.bak /path/to/your/vault
```

Or use `cortex uninstall` to revert installed assets (notes are kept):

```bash
cortex uninstall --vault /path/to/your/vault --latest --apply
```
