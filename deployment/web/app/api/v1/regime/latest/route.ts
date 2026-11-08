import { NextResponse } from 'next/server';
import { queryNeon } from '@/lib/neon';
import { REGIME_NAMES, validInference, numeric } from '@/lib/contracts';
import { apiError } from '@/lib/http';
export const dynamic = 'force-dynamic';
export async function GET() {
  try {
    const rows=await queryNeon('SELECT date::text AS date,period,prob_0,prob_1,prob_2,prob_3,prob_4,prob_5,raw_argmax,max_probability,is_confident,accepted_regime FROM regime_inference_daily ORDER BY date DESC LIMIT 1');
    if(!rows.length)return NextResponse.json({error:'No regime inference records available.'},{status:404});
    const r=rows[0];
    if(!validInference(r))return NextResponse.json({error:'Latest stored regime inference is invalid. No substitute regime is displayed.'},{status:503});
    const allocations=await queryNeon('SELECT variant,holding_days_after,rebalance_triggered,rebalance_bypassed_r3,turnover,w_nifty50,w_auto,w_bank,w_fmcg,w_it,w_metal,w_pharma,w_cash FROM portfolio_allocations_daily WHERE date=$1::date ORDER BY variant',[r.date]);
    return NextResponse.json({date:r.date,period:r.period,accepted_regime:{id:Number(r.accepted_regime),economic_name:REGIME_NAMES[Number(r.accepted_regime)],is_confident:r.is_confident,max_probability:numeric(r.max_probability),raw_argmax:Number(r.raw_argmax)},
      probabilities:REGIME_NAMES.map((name,id)=>({id,name,prob:numeric(r[`prob_${id}`])})),current_allocations:allocations});
  }catch(error){return apiError(error);}
}
