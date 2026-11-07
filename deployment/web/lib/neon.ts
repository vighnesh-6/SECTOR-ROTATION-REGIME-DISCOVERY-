/**
 * deployment/web/lib/neon.ts
 * ==========================
 * Lightweight Serverless Neon HTTP SQL client for Next.js API Route Handlers.
 * Connects directly to Neon's native /sql endpoint over HTTPS fetch.
 */

export interface QueryResult<T = any> {
  rows: T[];
  rowCount: number;
}

export async function queryNeon<T = any>(
  sql: string,
  params: any[] = []
): Promise<T[]> {
  const connString =
    process.env.DATABASE_URL ||
    process.env.NEON_DATABASE_URL ||
    "";

  if (!connString) {
    throw new Error(
      "Missing DATABASE_URL / NEON_DATABASE_URL environment variable."
    );
  }

  // Extract host from connection string (e.g. ep-calm-rain-a1emw9d9.ap-southeast-1.aws.neon.tech)
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

