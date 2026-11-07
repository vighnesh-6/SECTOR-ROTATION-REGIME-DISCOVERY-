/**
 * deployment/web/lib/neon.ts
 * ==========================
 * Lightweight Serverless Neon HTTP SQL client for Next.js API Route Handlers.
 * Connects directly to Neon's native /sql endpoint over HTTPS fetch.
 */

import fs from "fs";
import path from "path";

export interface QueryResult<T = any> {
  rows: T[];
  rowCount: number;
}

function getConnectionString(): string {
  let connString =
    process.env.DATABASE_URL ||
    process.env.NEON_DATABASE_URL ||
    "";

  if (!connString) {
    // Dynamic fallback to resolve .env.local across execution contexts
    const candidates = [
      path.resolve(process.cwd(), ".env.local"),
      path.resolve(process.cwd(), "deployment/web/.env.local"),
      path.resolve(process.cwd(), "../.env.local"),
      path.resolve(process.cwd(), "deployment/.env.local"),
    ];

    for (const cand of candidates) {
      try {
        if (fs.existsSync(cand)) {
          const content = fs.readFileSync(cand, "utf-8");
          const m = content.match(/DATABASE_URL=["']?([^"'\r\n]+)["']?/);
          if (m && m[1]) {
            connString = m[1].trim();
            process.env.DATABASE_URL = connString;
            break;
          }
        }
      } catch {
        // Continue to next candidate
      }
    }
  }

  return connString;
}

export async function queryNeon<T = any>(
  sql: string,
  params: any[] = []
): Promise<T[]> {
  const connString = getConnectionString();

  if (!connString) {
    throw new Error(
      "Missing DATABASE_URL / NEON_DATABASE_URL environment variable."
    );
  }

  // Extract host from connection string (e.g. ep-calm-rain-a1emw9d9-pooler.ap-southeast-1.aws.neon.tech)
  const match = connString.match(/@([^/:]+)/);
  if (!match) {
    throw new Error("Unable to parse database hostname from connection string.");
  }
  const host = match[1];
  const endpoint = `https://${host}/sql`;

  const payload: Record<string, any> = { query: sql };
  if (params && params.length > 0) {
    payload.params = params;
  }

  const response = await fetch(endpoint, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Neon-Connection-String": connString,
    },
    body: JSON.stringify(payload),
    cache: "no-store",
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(
      `Neon HTTP SQL Error (${response.status}): ${errorText}`
    );
  }

  const data: QueryResult<T> = await response.json();
  return data.rows || [];
}
