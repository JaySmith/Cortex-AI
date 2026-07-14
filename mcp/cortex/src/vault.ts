import {
  readFileSync,
  writeFileSync,
  existsSync,
  mkdirSync,
  statSync,
} from "node:fs";
import { join, dirname } from "node:path";
import { execFile } from "node:child_process";

export interface VaultNote {
  id: string;
  type: string;
  category: string;
  tier: string;
  tags: string[];
  updated: string;
  aliases: string[];
  content: string;
}

export interface VaultIndex {
  generated: string;
  source: string;
  count: number;
  notes: Record<string, VaultNote>;
}

let _index: VaultIndex | null = null;
let _vaultRoot: string | null = null;
let _memoryJsonPath: string | null = null;
let _loadedMtimeMs = 0;

/** Read memory.json from disk into the in-memory index. */
function loadIndex(): void {
  if (!_memoryJsonPath) throw new Error("Vault not initialized");
  const raw = readFileSync(_memoryJsonPath, "utf-8");
  const data = JSON.parse(raw);
  _index = {
    generated: data._meta.generated,
    source: data._meta.source,
    count: data._meta.count,
    notes: data.notes,
  };
  try {
    _loadedMtimeMs = statSync(_memoryJsonPath).mtimeMs;
  } catch {
    _loadedMtimeMs = 0;
  }
}

export function initVault(memoryJsonPath: string, vaultRoot: string): void {
  _vaultRoot = vaultRoot;
  _memoryJsonPath = memoryJsonPath;
  loadIndex();
}

/**
 * Force a reload of memory.json from disk. Returns the note count after reload.
 */
export function reloadVault(): number {
  loadIndex();
  return _index ? _index.count : 0;
}

/**
 * Return the index, transparently reloading if memory.json changed on disk
 * (e.g. a background distill from cortex_memory_write finished since last read).
 */
function getIndex(): VaultIndex {
  if (!_index || !_memoryJsonPath)
    throw new Error("Vault not initialized — call initVault() first");
  // Auto-reload if the file's mtime advanced since we last loaded it.
  try {
    const mtime = statSync(_memoryJsonPath).mtimeMs;
    if (mtime > _loadedMtimeMs) loadIndex();
  } catch {
    // stat failed — keep serving the cached index
  }
  return _index;
}

export function getNote(id: string): VaultNote | undefined {
  return getIndex().notes[id];
}

export function getAllNotes(): VaultNote[] {
  return Object.values(getIndex().notes);
}

export function searchNotes(query: string, limit: number): VaultNote[] {
  const notes = getAllNotes();
  const terms = query
    .toLowerCase()
    .split(/\s+/)
    .filter((t) => t.length > 1);

  if (terms.length === 0) return notes.slice(0, limit);

  const scored = notes
    .map((note) => {
      let score = 0;
      const id = note.id.toLowerCase();
      const aliases = note.aliases.map((a) => a.toLowerCase());
      const tags = note.tags.map((t) => t.toLowerCase());
      const category = note.category.toLowerCase();
      const content = note.content.toLowerCase();

      for (const term of terms) {
        if (id.includes(term)) score += 10;
        for (const alias of aliases) {
          if (alias.includes(term)) score += 8;
        }
        for (const tag of tags) {
          if (tag === term) score += 6;
          else if (tag.includes(term)) score += 3;
        }
        if (category === term) score += 5;
        else if (category.includes(term)) score += 2;
        if (content.includes(term)) score += 1;
      }
      return { note, score };
    })
    .filter((s) => s.score > 0)
    .sort((a, b) => b.score - a.score);

  return scored.slice(0, limit).map((s) => s.note);
}

export function getRelated(id: string, limit: number): VaultNote[] {
  const note = getNote(id);
  if (!note) return [];

  const notes = getAllNotes();
  const scored = notes
    .filter((n) => n.id !== id)
    .map((n) => {
      let score = 0;
      const tagOverlap = n.tags.filter((t) => note.tags.includes(t)).length;
      score += tagOverlap * 4;
      if (n.category === note.category) score += 3;
      if (n.type === note.type) score += 1;
      return { note: n, score };
    })
    .filter((s) => s.score > 0)
    .sort((a, b) => b.score - a.score);

  return scored.slice(0, limit).map((s) => s.note);
}

export function findVaultFile(id: string): string | null {
  if (!_vaultRoot) return null;
  const root = _vaultRoot;

  // Search common vault subdirs for a matching .md file.
  //
  // The `entities/projects/{delivery,completed,discovery}` phase subdirs are
  // DEPRECATED and retained only as a legacy fallback so notes written before
  // the phase-folder flattening are still found and updated in place. Phase is
  // now a frontmatter attribute, not a location, and new project notes are
  // always written to the flat `entities/projects/` dir (see resolveWritePath).
  //
  // TODO(remove-next-release): once all vaults have been migrated (phase folders
  // flattened into entities/projects/), delete the three phase-subdir entries
  // below. Tracked as the phase-as-attribute migration.
  const dirs = [
    // --- DEPRECATED phase subdirs (legacy fallback; remove next release) ---
    "entities/projects/delivery",
    "entities/projects/completed",
    "entities/projects/discovery",
    // --- canonical ---
    "entities/projects",
    "entities/people",
    "entities/systems",
    "entities/teams",
    "knowledge/api",
    "knowledge/patterns",
    "knowledge/infrastructure",
    "knowledge/calendars",
    "feedback",
    "decisions",
    "risks",
    "logs",
  ];

  for (const dir of dirs) {
    const filePath = join(root, dir, `${id}.md`);
    if (existsSync(filePath)) return filePath;
  }
  return null;
}

export function readFileRaw(filePath: string): string {
  return readFileSync(filePath, "utf-8");
}

// ── Write support ───────────────────────────────────────────────────

export interface WriteNoteParams {
  id: string;
  type: string;
  tier: string;
  category: string;
  phase?: string;
  aliases: string[];
  tags: string[];
  body: string;
  update?: boolean;
}

export interface WriteNoteResult {
  path: string;
  action: "created" | "updated";
}

/**
 * Resolve the absolute vault path for a note from its type + category.
 *
 * Identity is the note `id`; phase/state are frontmatter attributes, NOT
 * locations. Projects therefore always resolve to a single flat directory
 * (`entities/projects/<id>.md`) — `phase` lives in frontmatter, never in the
 * path. This prevents the duplicate-id class of bug where the same id ended up
 * in both `entities/projects/<id>.md` and `entities/projects/<phase>/<id>.md`.
 *
 * Dup-proofing: if a note with this id already exists ANYWHERE in the vault
 * (including legacy phase subdirs, pre-migration), we return that existing path
 * so the write patches the note in place instead of creating a second file.
 */
export function resolveWritePath(params: WriteNoteParams): string {
  if (!_vaultRoot) throw new Error("Vault not initialized");
  const root = _vaultRoot;
  const { type, category, id } = params;
  const cat = (category || "").toLowerCase();

  // If the note already exists somewhere, always write to that same file.
  // Never create a second file for an id that already lives in the vault.
  const existing = findVaultFile(id);
  if (existing) return existing;

  let dir: string;
  switch (type) {
    case "feedback":
      dir = "feedback";
      break;
    case "decision":
      dir = "decisions";
      break;
    case "risk":
      dir = "risks";
      break;
    case "session":
    case "log":
      dir = "logs";
      break;
    case "knowledge":
      if (["patterns", "api", "calendars", "infrastructure"].includes(cat)) {
        dir = join("knowledge", cat);
      } else {
        dir = join("knowledge", "patterns");
      }
      break;
    case "entity":
      if (cat === "projects") {
        // Flat: phase is a frontmatter attribute, not a subdirectory.
        dir = join("entities", "projects");
      } else if (["people", "systems", "teams"].includes(cat)) {
        dir = join("entities", cat);
      } else {
        dir = join("entities", cat || "systems");
      }
      break;
    default:
      dir = "knowledge/patterns";
  }

  return join(root, dir, `${id}.md`);
}

/** Format a value into a YAML frontmatter line. */
function yamlList(items: string[]): string {
  if (items.length === 0) return "[]";
  return "[" + items.map((s) => JSON.stringify(s)).join(", ") + "]";
}

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

/** Build a fresh frontmatter block for a new note. */
function buildFrontmatter(p: WriteNoteParams): string {
  const lines = ["---"];
  lines.push(`id: ${p.id}`);
  lines.push(`type: ${p.type}`);
  lines.push(`tier: ${p.tier}`);
  if (p.category) lines.push(`category: "${p.category}"`);
  if (p.phase) lines.push(`phase: ${p.phase}`);
  lines.push(`source: session`);
  lines.push(`updated: "${today()}"`);
  lines.push(`aliases: ${yamlList(p.aliases)}`);
  lines.push(`tags: ${yamlList(p.tags)}`);
  lines.push("---");
  return lines.join("\n");
}

/**
 * Update mode: split existing file into frontmatter + body, replace the body,
 * bump the `updated:` field, preserve all other frontmatter fields.
 */
function patchExisting(existing: string, newBody: string): string {
  let fm = existing;
  let rest = "";
  if (existing.startsWith("---")) {
    const end = existing.indexOf("\n---", 3);
    if (end !== -1) {
      fm = existing.slice(0, end + 4); // include closing ---
      rest = existing.slice(end + 4);
    }
  }
  // bump or insert updated: field
  if (/^updated:.*$/m.test(fm)) {
    fm = fm.replace(/^updated:.*$/m, `updated: "${today()}"`);
  } else {
    fm = fm.replace(/\n---\s*$/, `\nupdated: "${today()}"\n---`);
  }
  return `${fm}\n\n${newBody.trim()}\n`;
}

/**
 * Trigger the distiller in the background (fire-and-forget).
 * Does not block the tool call — memory.json catches up within ~1-2s.
 *
 * Resolution order for the python interpreter:
 *   1. $DISTILL_PYTHON env var, if set (e.g. an explicit venv path)
 *   2. <vault>/_sync/.venv/bin/python, if it exists (the distiller's own venv)
 *   3. plain `python3` on PATH
 *
 * The distiller script defaults to <vault>/_sync/distill.py; override with
 * $DISTILL_SCRIPT if your layout differs.
 */
function fireDistill(): void {
  if (!_vaultRoot) return;
  const script =
    process.env.DISTILL_SCRIPT || join(_vaultRoot, "_sync", "distill.py");
  if (!existsSync(script)) return;
  const venvPython = join(_vaultRoot, "_sync", ".venv", "bin", "python");
  const python =
    process.env.DISTILL_PYTHON ||
    (existsSync(venvPython) ? venvPython : "python3");
  try {
    const child = execFile(python, [script], {
      detached: true,
      stdio: "ignore",
    } as any);
    child.unref();
  } catch {
    // swallow — distill is best-effort; next manual sync will catch up
  }
}

/**
 * Create or update a vault note, then fire the distiller in the background.
 */
export function writeNote(params: WriteNoteParams): WriteNoteResult {
  const path = resolveWritePath(params);
  const exists = existsSync(path);

  let action: "created" | "updated";
  let content: string;

  if (params.update && exists) {
    const existing = readFileSync(path, "utf-8");
    content = patchExisting(existing, params.body);
    action = "updated";
  } else {
    content = `${buildFrontmatter(params)}\n\n${params.body.trim()}\n`;
    action = exists ? "updated" : "created";
  }

  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, content, "utf-8");

  fireDistill();

  return { path, action };
}
