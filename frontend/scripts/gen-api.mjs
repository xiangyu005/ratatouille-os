// Regenerate frontend/openapi.json from CORE, then the TypeScript contract.
//
//   1. scripts/generate_types.py exports CORE's OpenAPI document (single source).
//   2. openapi-typescript turns it into src/api/schema.d.ts.
//
// Generated files are committed so the build never needs a running CORE, and
// must never be edited by hand (docs/22-01 §7.1).

import { execFileSync } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const frontendDir = resolve(here, "..");
const repoRoot = resolve(frontendDir, "..");

execFileSync("uv", ["run", "python", "scripts/generate_types.py"], {
  cwd: repoRoot,
  stdio: "inherit",
  shell: process.platform === "win32",
});

execFileSync("npx", ["openapi-typescript", "openapi.json", "-o", "src/api/schema.d.ts"], {
  cwd: frontendDir,
  stdio: "inherit",
  shell: process.platform === "win32",
});

console.log("[gen:api] src/api/schema.d.ts updated");
