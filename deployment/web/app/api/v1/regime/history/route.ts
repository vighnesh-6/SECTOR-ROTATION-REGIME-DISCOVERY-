import { NextRequest,NextResponse } from 'next/server';
import { queryNeon } from '@/lib/neon';
import { validInference, numeric } from '@/lib/contracts';
import { dates,apiError } from '@/lib/http';
export const dynamic='force-dynamic';
export async function GET(request:NextRequest) {
  try {
    const {from,to}=dates(new URL(request.url).searchParams,'2019-10-31','2099-12-31');
    const rows=await queryNeon('SELECT date::text AS date,period,prob_0,prob_1,prob_2,prob_3,prob_4,prob_5,raw_argmax,max_probability,is_confident,accepted_regime FROM regime_inference_daily WHERE date >= $1::date AND date <= $2::date ORDER BY date',[from,to]);
    return NextResponse.json({from_date:from,to_date:to,invalid_rows:rows.filter(r=>!validInference(r)).length,history:rows.map(r=>({date:r.date,period:r.period,valid:validInference(r),accepted_regime:validInference(r)?Number(r.accepted_regime):null,...Object.fromEntries(Array.from({length:6},(_,i)=>[`R${i}`,validInference(r)?numeric(r[`prob_${i}`]):null]))}))});
  }catch(error){return apiError(error);}
}
