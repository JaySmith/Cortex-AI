import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import {
  initVault,
  searchNotes,
  getNote,
  getRelated,
  findVaultFile,
  readFileRaw,
  writeNote,
  reloadVault,
  buildThinkContext,
  type VaultNote,
} from "./vault.js";
import { HubClient } from "./hub-client.js";

/**
 * Read the Cortex version from the repo-root VERSION file (single source of truth).
 * This module compiles to build/index.js, so the repo root is two levels up.
 * Falls back to "unknown" if the file can't be found.
 */
function cortexVersion(): string {
  const here = dirname(fileURLToPath(import.meta.url)); // .../mcp/cortex/build
  const candidates = [
    join(here, "..", "..", "..", "VERSION"), // repo root (build/ -> cortex -> mcp -> repo)
    join(here, "..", "..", "VERSION"), // repo root when run from src/ (dev)
    join(here, "..", "VERSION"), // package root: .../mcp/cortex/VERSION (installed layout)
    process.env.CORTEX_VERSION_FILE || "", // explicit override
  ];
  for (const p of candidates) {
    if (!p) continue;
    try {
      return readFileSync(p, "utf-8").trim();
    } catch {
      /* try next */
    }
  }
  return "unknown";
}

const server = new McpServer({
  name: "cortex",
  version: cortexVersion(),
});

// ── memory_search ───────────────────────────────────────────────────
server.registerTool(
  "memory_search",
  {
    description:
      "Search the Cortex vault by keyword. Returns note summaries (id, type, category, aliases, tags, snippet). " +
      "Use memory_get(id) to fetch full content of a result.",
    inputSchema: {
      query: z.string().describe("Natural language search query"),
      limit: z
        .number()
        .optional()
        .default(5)
        .describe("Max results to return (default 5)"),
    },
  },
  async ({ query, limit }) => {
    let results = searchNotes(query, limit);

    // Merge hub results if hive is enabled
    if (_hubEnabled && _hubClient) {
      const hubResults = await hiveSearch(query, limit);
      if (hubResults.length > 0) {
        // Merge: local wins on id collision, hub fills gaps
        const merged = new Map<string, VaultNote>();
        for (const note of hubResults) {
          merged.set(note.id, note);
        }
        for (const note of results) {
          merged.set(note.id, note); // local overwrites hub on collision
        }
        results = Array.from(merged.values()).slice(0, limit);
      }
    }

    if (results.length === 0) {
      return {
        content: [{ type: "text", text: `No memories found for "${query}".` }],
      };
    }
    const lines = results.map((note) => {
      const alias = note.aliases.length > 0 ? note.aliases[0] : note.id;
      const tags = note.tags.length > 0 ? ` [${note.tags.join(", ")}]` : "";
      const snippet = note.content.slice(0, 200).replace(/\n/g, " ").trim();
      return `**${note.id}** (${note.type}/${note.category}) — ${alias}${tags}\n  ${snippet}…`;
    });
    return {
      content: [{ type: "text", text: lines.join("\n\n") }],
    };
  },
);

// ── memory_get ──────────────────────────────────────────────────────
server.registerTool(
  "memory_get",
  {
    description:
      "Fetch a single memory note by its id. Returns the full content and metadata. " +
      "Falls back to reading the raw vault .md file if the note is not in memory.json.",
    inputSchema: {
      id: z.string().describe("Note id slug (e.g. 'askdel', 'jira-rest-api')"),
    },
  },
  async ({ id }) => {
    const note = getNote(id);
    if (note) {
      const alias =
        note.aliases.length > 0 ? `\nAliases: ${note.aliases.join(", ")}` : "";
      const header = `# ${note.id}\ntype: ${note.type} | category: ${note.category} | tier: ${note.tier} | updated: ${note.updated}${alias}\ntags: ${note.tags.join(", ")}`;
      return {
        content: [{ type: "text", text: `${header}\n\n${note.content}` }],
      };
    }

    // Fallback: try reading the vault file directly
    const vaultPath = findVaultFile(id);
    if (vaultPath) {
      const raw = readFileRaw(vaultPath);
      return {
        content: [
          {
            type: "text",
            text: `_From vault file: ${vaultPath}_\n\n${raw}`,
          },
        ],
      };
    }

    return {
      content: [
        { type: "text", text: `No note found with id "${id}".` },
      ],
      isError: true,
    };
  },
);

// ── memory_related ──────────────────────────────────────────────────
server.registerTool(
  "memory_related",
  {
    description:
      "Find notes related to a given note by shared tags and category. " +
      "Returns summaries of related notes.",
    inputSchema: {
      id: z.string().describe("Note id to find related notes for"),
      limit: z
        .number()
        .optional()
        .default(5)
        .describe("Max related notes to return (default 5)"),
    },
  },
  async ({ id, limit }) => {
    const source = getNote(id);
    if (!source) {
      return {
        content: [
          { type: "text", text: `No note found with id "${id}".` },
        ],
        isError: true,
      };
    }

    const related = getRelated(id, limit);
    if (related.length === 0) {
      return {
        content: [
          {
            type: "text",
            text: `No related notes found for "${id}" (tags: [${source.tags.join(", ")}]).`,
          },
        ],
      };
    }

    const lines = related.map((note) => {
      const alias = note.aliases.length > 0 ? note.aliases[0] : note.id;
      const sharedTags = note.tags.filter((t) => source.tags.includes(t));
      const tagNote =
        sharedTags.length > 0 ? ` (shared: ${sharedTags.join(", ")})` : "";
      const snippet = note.content.slice(0, 150).replace(/\n/g, " ").trim();
      return `**${note.id}** (${note.type}/${note.category}) — ${alias}${tagNote}\n  ${snippet}…`;
    });
    return {
      content: [{ type: "text", text: lines.join("\n\n") }],
    };
  },
);

// ── memory_think ────────────────────────────────────────────────────
server.registerTool(
  "memory_think",
  {
    description:
      "Synthesize a rich context for answering a question from the Cortex vault. " +
      "Unlike memory_search (which returns summaries), this gathers full content from " +
      "primary results, pulls in cross-referenced related notes, and identifies gaps " +
      "in coverage. Returns a structured synthesis context designed to let you produce " +
      "a single, well-sourced answer in one pass — no follow-up searches needed.",
    inputSchema: {
      query: z.string().describe("Natural language question to synthesize context for"),
      limit: z
        .number()
        .optional()
        .default(5)
        .describe("Max primary notes to include (default 5; related notes added on top)"),
    },
  },
  async ({ query, limit }) => {
    const ctx = buildThinkContext(query, limit);

    if (ctx.sourceNotes.length === 0) {
      return {
        content: [
          {
            type: "text",
            text: `No memories found for "${query}". The vault has no coverage on this topic.`,
          },
        ],
      };
    }

    const parts: string[] = [];

    // Header
    parts.push(`# Synthesis Context for: "${ctx.query}"`);
    parts.push("");

    // Primary sources (full content)
    const primary = ctx.sourceNotes.filter((n) => n.relevance === "primary");
    parts.push(`## Primary Sources (${primary.length})`);
    parts.push("");
    for (const note of primary) {
      const alias =
        note.aliases.length > 0 ? ` (aka ${note.aliases.join(", ")})` : "";
      const tags = note.tags.length > 0 ? ` [${note.tags.join(", ")}]` : "";
      parts.push(`### ${note.id}${alias} — ${note.type}/${note.category}${tags}`);
      parts.push("");
      parts.push(note.content);
      parts.push("");
    }

    // Related context (truncated)
    const related = ctx.sourceNotes.filter((n) => n.relevance === "related");
    if (related.length > 0) {
      parts.push(`## Related Context (${related.length})`);
      parts.push("");
      for (const note of related) {
        const tags = note.tags.length > 0 ? ` [${note.tags.join(", ")}]` : "";
        parts.push(`- **${note.id}** (${note.type}/${note.category})${tags}`);
        parts.push(`  ${note.content.slice(0, 300).replace(/\n/g, " ").trim()}…`);
        parts.push("");
      }
    }

    // Cross-references
    if (ctx.crossReferences.length > 0) {
      parts.push("## Cross-References");
      parts.push("");
      for (const ref of ctx.crossReferences) {
        parts.push(
          `- ${ref.from} ↔ ${ref.to} (shared: ${ref.sharedTags.join(", ")})`,
        );
      }
      parts.push("");
    }

    // Gap analysis
    if (ctx.gaps.length > 0) {
      parts.push("## Gaps in Coverage");
      parts.push("");
      for (const gap of ctx.gaps) {
        parts.push(`- ${gap}`);
      }
      parts.push("");
    }

    parts.push(
      "---\nUse the above context to synthesize a direct, well-cited answer. " +
        "Cite note ids (e.g. [[note-id]]) when referencing specific sources. " +
        "If gaps exist, explicitly note what the vault doesn't know.",
    );

    return {
      content: [{ type: "text", text: parts.join("\n") }],
    };
  },
);

// ── memory_write ────────────────────────────────────────────────────
server.registerTool(
  "memory_write",
  {
    description:
      "Create or update a note in the Cortex vault. Distillation runs automatically " +
      "in the background after the write.\n\n" +
      "ALWAYS call memory_search first — if a related note exists, pass update:true " +
      "to patch it rather than create a duplicate.\n\n" +
      "Use for: preferences/corrections (feedback), patterns or solutions learned " +
      "(knowledge), significant decisions (decision), project status changes (entity), " +
      "identified threats to success (risk), session summaries (session).",
    inputSchema: {
      id: z
        .string()
        .describe("Note id slug — lowercase, hyphens, no spaces (e.g. 'jira-bulk-transition')"),
      type: z
        .enum(["knowledge", "entity", "feedback", "decision", "risk", "session", "log"])
        .describe("Note type"),
      tier: z
        .string()
        .describe(
          "Routing tier: 'core' (always loaded), 'skill:<name>' (e.g. 'skill:jira'), " +
            "'project', or 'vault-only' (never distilled to agents)",
        ),
      category: z
        .string()
        .default("")
        .describe(
          "Grouping label. knowledge: patterns|api|calendars|infrastructure. " +
            "entity: projects|people|systems|teams. Others: free-form.",
        ),
      phase: z
        .string()
        .optional()
        .describe("For entity/projects only: delivery | discovery | completed"),
      aliases: z
        .array(z.string())
        .default([])
        .describe("Human-readable titles; the first is the display name"),
      tags: z.array(z.string()).default([]).describe("Tags for filtering/retrieval"),
      body: z
        .string()
        .describe("Full markdown body of the note — do NOT include YAML frontmatter"),
      update: z
        .boolean()
        .default(false)
        .describe("If true and the note exists, patch its body and bump the updated date"),
    },
  },
  async ({ id, type, tier, category, phase, aliases, tags, body, update }) => {
    try {
      const result = writeNote({
        id,
        type,
        tier,
        category,
        phase,
        aliases,
        tags,
        body,
        update,
      });

      // Hive push: fire-and-forget if hub is configured
      if (_hubClient && _hubEnabled) {
        hivePushNote(id, type, tier, category, aliases, tags, body).catch((err) =>
          console.error(`hive push failed for ${id}:`, err),
        );
      }

      return {
        content: [
          {
            type: "text",
            text:
              `Note ${result.action}: ${result.path}\n` +
              `Distillation triggered in background (memory.json updates within ~1-2s).`,
          },
        ],
      };
    } catch (err) {
      return {
        content: [
          {
            type: "text",
            text: `Failed to write note "${id}": ${err instanceof Error ? err.message : String(err)}`,
          },
        ],
        isError: true,
      };
    }
  },
);

// ── memory_reload ───────────────────────────────────────────────────
server.registerTool(
  "memory_reload",
  {
    description:
      "Reload the vault index from memory.json. Reads pick up changes automatically " +
      "when the file's mtime advances, so this is rarely needed — use it only to force " +
      "an immediate refresh (e.g. right after a write, before a distill has finished).",
    inputSchema: {},
  },
  async () => {
    try {
      const count = reloadVault();
      return {
        content: [{ type: "text", text: `Vault index reloaded — ${count} notes.` }],
      };
    } catch (err) {
      return {
        content: [
          {
            type: "text",
            text: `Reload failed: ${err instanceof Error ? err.message : String(err)}`,
          },
        ],
        isError: true,
      };
    }
  },
);

// ── Start ───────────────────────────────────────────────────────────

// ── Hive state ──────────────────────────────────────────────────────
let _hubClient: HubClient | null = null;
let _hubEnabled = false;
let _hubMachineId = "";

/** Push a note to the hub (fire-and-forget from memory_write). */
async function hivePushNote(
  id: string,
  type: string,
  tier: string,
  category: string,
  aliases: string[],
  tags: string[],
  body: string,
): Promise<void> {
  if (!_hubClient) return;
  const key = `vault/${_hubMachineId}/${id}`;
  const value = JSON.stringify({
    id,
    type,
    category,
    tier,
    tags,
    aliases,
    updated: new Date().toISOString().slice(0, 10),
    content: body,
    machine_id: _hubMachineId,
  });
  const hubTags = ["vault", _hubMachineId, tier, type];
  await _hubClient.memorySet(key, value, hubTags);
}

/** Search hub for vault notes matching query. Returns VaultNote[] compatible results. */
async function hiveSearch(query: string, limit: number): Promise<VaultNote[]> {
  if (!_hubClient) return [];
  try {
    const results = await _hubClient.memorySearch(query);
    if (!Array.isArray(results)) return [];
    return results
      .filter((entry: Record<string, unknown>) => {
        const val = entry.value;
        if (typeof val !== "string") return false;
        try {
          const data = JSON.parse(val);
          return data.machine_id !== _hubMachineId; // skip our own notes
        } catch {
          return false;
        }
      })
      .map((entry: Record<string, unknown>) => {
        const data = JSON.parse(entry.value as string);
        return {
          id: data.id ?? "",
          type: data.type ?? "unknown",
          category: data.category ?? "",
          tier: data.tier ?? "core",
          tags: data.tags ?? [],
          updated: data.updated ?? "",
          aliases: data.aliases ?? [],
          content: data.content ?? "",
        };
      })
      .slice(0, limit);
  } catch (err) {
    console.error("hive search failed:", err);
    return [];
  }
}

async function main(): Promise<void> {
  const memoryJson = process.env.MEMORY_JSON;
  const vaultRoot = process.env.VAULT_ROOT;
  if (!memoryJson || !vaultRoot) {
    console.error(
      "FATAL: MEMORY_JSON and VAULT_ROOT environment variables are required.",
    );
    process.exit(1);
  }

  initVault(memoryJson, vaultRoot);
  console.error(
    `cortex MCP v${cortexVersion()} loaded — ${memoryJson} from vault ${vaultRoot}`,
  );

  // Initialize hive if configured
  _hubEnabled = process.env.HIVE_ENABLED === "true";
  if (_hubEnabled) {
    _hubMachineId = process.env.HIVE_MACHINE_ID || "unknown";
    const hubUrl = process.env.HIVE_HUB_URL || "http://localhost:4096/mcp";
    const hubToken = process.env.HIVE_HUB_TOKEN || "";
    _hubClient = new HubClient({ url: hubUrl, token: hubToken });
    try {
      await _hubClient.connect();
      console.error(`hive connected to ${hubUrl} as machine "${_hubMachineId}"`);
    } catch (err) {
      console.error(`hive connection failed: ${err}. Hive features disabled for this session.`);
      _hubClient = null;
      _hubEnabled = false;
    }
  }

  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main().catch((err) => {
  console.error("cortex MCP fatal:", err);
  process.exit(1);
});
