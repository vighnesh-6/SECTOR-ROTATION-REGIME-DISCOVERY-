import { handleSchedule } from '@vercel/schedules';
import { tick } from '../lib/dispatcher.mjs';

// Private schedule/v1beta function: there is no public trigger URL or DB client.
export const POST = handleSchedule(async metadata => {
  if (process.env.AUTOMATION_ENABLED !== 'true') {
    console.log(JSON.stringify({ status: 'DISABLED', schedule: metadata.name }));
    return;
  }
  if (process.env.DATABASE_URL) throw new Error('Automation project must not have a database connection');
  const args = { scheduledAt: metadata.scheduledAt, now:new Date(), token:process.env.AUTOMATION_GITHUB_TOKEN };
  const result = await tick({ ...args, name:metadata.name });
  console.log(JSON.stringify({ ...result, execution_id: metadata.executionId }));
  if (metadata.name==='events-watchdog') {
    const health = await tick({ ...args, name:'events-health' });
    console.log(JSON.stringify({ ...health,execution_id:metadata.executionId }));
  }
});
