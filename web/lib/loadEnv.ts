import { readFileSync } from "node:fs";
import { resolve } from "node:path";

function parseEnv(text: string) {
  for (const line of text.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const eq = trimmed.indexOf("=");
    if (eq < 1) continue;
    const key = trimmed.slice(0, eq).trim();
    if (!key.startsWith("NAVER_")) continue;
    let value = trimmed.slice(eq + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    if (!process.env[key]) process.env[key] = value;
  }
}

export function loadNaverEnv() {
  const candidates = [
    resolve(process.cwd(), ".env.local"),
    resolve(process.cwd(), ".env"),
    resolve(process.cwd(), "..", ".env"),
  ];
  for (const file of candidates) {
    try {
      parseEnv(readFileSync(file, "utf8"));
    } catch {
      /* missing file is normal */
    }
  }
}
