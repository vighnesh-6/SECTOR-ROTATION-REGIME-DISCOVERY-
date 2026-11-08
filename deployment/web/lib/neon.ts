/** Website-only SELECT client. Never expose credentials or upstream error bodies. */
import fs from 'fs';
import path from 'path';
export function getConnectionString(): string {
  if (process.env.DATABASE_URL || process.env.NEON_DATABASE_URL) return (process.env.DATABASE_URL || process.env.NEON_DATABASE_URL)!;
  for (const candidate of ['.env.local','deployment/web/.env.local','../.env.local','deployment/.env.local']) {
    try {
      const text = fs.readFileSync(path.resolve(process.cwd(),candidate),'utf8');
      const match = text.match(/^\s*(?:DATABASE_URL|NEON_DATABASE_URL)\s*=\s*(?:"([^"\r\n]+)"|'([^'\r\n]+)'|([^\s#\r\n]+))\s*(?:#.*)?$/m);
      if (match) return match[1] || match[2] || match[3];
    } catch { /* Optional fallback files are read, never changed. */ }
  }
  throw new Error('Website database connection is not configured.');
}
export async function queryNeon<T = Record<string, any>>(sql: string, params: unknown[] = []): Promise<T[]> {
  if (!/^\s*(SELECT|WITH)\b/i.test(sql) || /\b(INSERT|UPDATE|DELETE|ALTER|DROP|CREATE|TRUNCATE)\b/i.test(sql)) throw new Error('Website queries must be read-only.');
  const connection = getConnectionString();
  let url: URL;
  try { url = new URL(connection); } catch { throw new Error('Invalid website database configuration.'); }
  if (!['postgres:','postgresql:'].includes(url.protocol) || !url.hostname.endsWith('.neon.tech')) throw new Error('Invalid website database configuration.');
  for (let attempt=0; attempt<3; attempt++) {
    let response: Response;
    try {
      response = await fetch(`https://${url.hostname}/sql`, {method:'POST',headers:{'Content-Type':'application/json','Neon-Connection-String':connection},body:JSON.stringify({query:sql,params}),cache:'no-store',signal:AbortSignal.timeout(8000)});
    } catch {
      if (attempt===2) throw new Error('Website database request failed.');
      await new Promise(resolve=>setTimeout(resolve,250*2**attempt));
      continue;
    }
    if (!response.ok) {
      if ([429,500,502,503,504].includes(response.status) && attempt<2) {
        await new Promise(resolve=>setTimeout(resolve,250*2**attempt));
        continue;
      }
      throw new Error('Website database request failed.');
    }
    try {
      const data = await response.json();
      if (!Array.isArray(data.rows)) throw new Error('Invalid database response.');
      return data.rows;
    } catch { throw new Error('Website database response failed.'); }
  }
  throw new Error('Website database request failed.');
}
