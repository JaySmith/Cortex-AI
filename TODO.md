# TODO

Outstanding work for cortex-ai. Each item links to its tracking issue on
[GitHub](https://github.com/JaySmith/cortex-ai/issues). Keep this file in sync
when issues are opened or closed.

## Open

- [ ] **Unify the two skill-install paths** —
  [#2](https://github.com/JaySmith/cortex-ai/issues/2). The per-platform
  registry path (`cortex opencode install`) resolves the skill template inside
  the installed package and fails from the installed tool; only the top-level
  `cortex install` works. Consolidate to one skill-writing path, preserving the
  2.0.2 contract (SKILL.md written raw, frontmatter-first, no managed-block
  wrapper). Also noted in `CHANGELOG.md` [2.0.2] Known issues.

- [ ] **Wave 2: Codex platform asset generation** —
  [#3](https://github.com/JaySmith/cortex-ai/issues/3).
  `CodexInstaller.install()` is a no-op stub (`cortex/platforms/codex.py:26`).

- [ ] **Wave 2: GitHub Copilot platform asset generation** —
  [#4](https://github.com/JaySmith/cortex-ai/issues/4).
  `CopilotInstaller.install()` is a no-op stub (`cortex/platforms/copilot.py:26`).

## Pre-existing

- [ ] **`memory write` fixes** —
  [#1](https://github.com/JaySmith/cortex-ai/issues/1). `--update` can't find
  notes; `--category` ignored; type dir mis-pluralized.
</content>
