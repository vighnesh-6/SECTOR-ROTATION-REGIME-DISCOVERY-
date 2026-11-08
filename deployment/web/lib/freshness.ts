export function expectedSession(now = new Date()): string {
  const parts = new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Kolkata',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(now);
  const get = (key:string) => parts.find(p => p.type === key)!.value;
  const date = new Date(`${get('year')}-${get('month')}-${get('day')}T00:00:00Z`);
  if (Number(get('hour'))*60+Number(get('minute')) < 21*60+30) date.setUTCDate(date.getUTCDate()-1);
  while ([0,6].includes(date.getUTCDay())) date.setUTCDate(date.getUTCDate()-1);
  return date.toISOString().slice(0,10);
}
