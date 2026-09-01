import { tool } from "@opencode-ai/plugin"
import { execFile } from "node:child_process"
import { promisify } from "node:util"

const execFileAsync = promisify(execFile)

async function runCortex(args: string[]): Promise<string> {
  try {
    const { stdout, stderr } = await execFileAsync("cortex", args, {
      timeout: 30000,
      maxBuffer: 10 * 1024 * 1024,
    })
    const merged = [stdout, stderr].filter(Boolean).join("\n").trim()
    return merged || "(no output)"
  } catch (err: any) {
    const message = err?.stderr || err?.stdout || String(err)
    return `cortex command failed:\n${message}`
  }
}

export const search = tool({
  description:
    "Search the Cortex memory vault (~/cortex-ai) for notes relevant to a topic. " +
    "Run this BEFORE spawning any filesystem-exploring agent or running a broad " +
    "glob/find/grep to locate files or code — the vault often already knows where things live. " +
    "Lists matching notes (id, type, alias, snippet). For a full note, follow up with the get tool.",
  args: {
    query: tool.schema
      .string()
      .describe(
        "Search topic: a project, system, feature, person, or 'where is X' style question."
      ),
  },
  async execute(args) {
    return runCortex(["memory", "search", args.query])
  },
})

export const get = tool({
  description:
    "Get the full content of a single Cortex memory note by id (from a prior search result). " +
    "Useful to read the complete details/decisions recorded in the vault.",
  args: {
    id: tool
      .schema
      .string()
      .describe("The note id returned by the search tool (e.g. omarchy-pomodoro-plugin-with-activity-logging)."),
  },
  async execute(args) {
    return runCortex(["memory", "get", args.id])
  },
})
