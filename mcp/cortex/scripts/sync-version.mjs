#!/usr/bin/env node
/**
 * sync-version.mjs — keep package.json's version in lockstep with the root VERSION file.
 *
 * Runs automatically as the `prebuild` npm hook. Resolves the VERSION file from
 * the repo root (installed or dev layout) and rewrites package.json only when the
 * value differs, so it stays a no-op on a clean build.
 */
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url)); // .../mcp/cortex/scripts
const pkgPath = join(here, "..", "package.json");

// Candidate VERSION locations, in priority order.
const candidates = [
  process.env.CORTEX_VERSION_FILE || "",
  join(here, "..", "..", "..", "VERSION"), // repo root (scripts -> cortex -> mcp -> repo)
  join(here, "..", "VERSION"), // package root (installed layout)
];

function readVersion() {
  for (const p of candidates) {
    if (!p) continue;
    try {
      return readFileSync(p, "utf-8").trim();
    } catch {
      /* try next */
    }
  }
  return null;
}

const version = readVersion();
if (!version) {
  console.warn("[sync-version] no VERSION file found — leaving package.json unchanged");
  process.exit(0);
}

const pkg = JSON.parse(readFileSync(pkgPath, "utf-8"));
if (pkg.version === version) {
  console.log(`[sync-version] package.json already at ${version}`);
  process.exit(0);
}

const old = pkg.version;
pkg.version = version;
writeFileSync(pkgPath, JSON.stringify(pkg, null, 2) + "\n", "utf-8");
console.log(`[sync-version] package.json version ${old} -> ${version}`);
