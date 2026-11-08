import { NextRequest, NextResponse } from 'next/server';
import { queryNeon } from '@/lib/neon';
import { metadata, severity } from '@/lib/contracts';
import { integer, dates, apiError } from '@/lib/http';
export const dynamic = 'force-dynamic';
export async function GET(request:NextRequest) {
  try {
    const p=new URL(request.url).searchParams,limit=integer(p.get('limit'),50,1,500),offset=integer(p.get('offset'),0,0,100000);
    const {from,to}=dates(p,'2019-01-01','2099-12-31'),category=p.get('category');
    const params:unknown[]=[from,to];let filter='WHERE date >= $1::date AND date <= $2::date';
    if(category){params.push(category);filter+=' AND category = $3';}
    const [rows,counts,categories] = await Promise.all([
      queryNeon(`SELECT event_id,date::text AS date,category,title,actual,forecast,previous,source FROM macro_events ${filter} ORDER BY date DESC,event_id DESC LIMIT $${params.length+1} OFFSET $${params.length+2}`,[...params,limit,offset]),
      queryNeon(`SELECT COUNT(*)::int AS total,MIN(date)::text AS first_date,MAX(date)::text AS latest_date FROM macro_events ${filter}`,params),
      queryNeon('SELECT category,COUNT(*)::int AS count FROM macro_events GROUP BY category ORDER BY category')
    ]);
    return NextResponse.json({count:rows.length,total:counts[0]?.total??0,first_date:counts[0]?.first_date??null,latest_date:counts[0]?.latest_date??null,limit,offset,categories,
      events:rows.map(r=>({...r,severity:severity(r.actual),region:metadata(r.forecast,'Region'),end_date:metadata(r.previous,'End')}))});
  }catch(error){return apiError(error);}
}
