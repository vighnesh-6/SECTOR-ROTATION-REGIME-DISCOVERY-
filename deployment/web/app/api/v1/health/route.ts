import { NextResponse } from 'next/server';
import { queryNeon } from '@/lib/neon';
import { UNIVERSE, VARIANTS, numeric, validInference } from '@/lib/contracts';
import { expectedSession } from '@/lib/freshness';
export const dynamic = 'force-dynamic';
export async function GET() {
  const started = Date.now();
  try {
    const [candles,regimes,logs,holdings] = await Promise.all([
      queryNeon('SELECT symbol, MAX(date)::text AS latest_date, COUNT(*)::int AS records FROM index_candles_daily GROUP BY symbol ORDER BY symbol'),
      queryNeon('SELECT date::text AS date, accepted_regime, is_confident, max_probability, raw_argmax, prob_0,prob_1,prob_2,prob_3,prob_4,prob_5 FROM regime_inference_daily ORDER BY date DESC LIMIT 1'),
      queryNeon("SELECT trigger_type,status,step_reached,session_date::text AS session_date,created_at::text AS executed_at FROM pipeline_execution_logs WHERE trigger_type <> 'event_collector' ORDER BY created_at DESC LIMIT 1"),
      queryNeon('SELECT variant,MAX(date)::text AS latest_date FROM portfolio_simulations_daily GROUP BY variant')
    ]);
    const expected = expectedSession(), inference = regimes[0], reasons:string[] = [];
    const indices = UNIVERSE.map(symbol => {
      const row=candles.find(r=>r.symbol===symbol);const stale=!row?.latest_date || row.latest_date<expected;
      if(stale) reasons.push(`${symbol}: missing/stale candles`);
      return {symbol,latest_date:row?.latest_date??null,records:row?.records??0,stale};
    });
    if(!validInference(inference)) reasons.push('Latest regime inference is missing or invalid');
    if(!inference?.date || inference.date<expected) reasons.push('Regime inference is stale');
    for(const variant of VARIANTS) {
      const row=holdings.find(r=>r.variant===variant);
      if(!row?.latest_date || row.latest_date<expected || row.latest_date!==inference?.date) reasons.push(`${variant}: missing/stale or unaligned simulation`);
    }
    if(indices.some(r=>r.latest_date!==inference?.date)) reasons.push('Candle and inference dates are not aligned');
    if(!logs[0] || logs[0].status!=='SUCCESS') reasons.push('Latest Market EOD execution is missing or not SUCCESS');
    return NextResponse.json({status:reasons.length?'DEGRADED':'HEALTHY',reasons,expected_session:expected,
      freshness_policy:'Weekdays, after 21:30 IST. Exchange holidays are not inferred; check the official trading calendar when flagged.',
      database:{connected:true,latency_ms:Date.now()-started,latest_candle_date:indices.every(r=>r.latest_date)?indices.map(r=>r.latest_date!).sort()[0]:null,total_candle_records:indices.reduce((a,r)=>a+Number(r.records),0)},
      indices,inference:{latest_regime_date:inference?.date??null,accepted_regime:validInference(inference)?Number(inference.accepted_regime):null,is_confident:validInference(inference)?inference.is_confident:null,confidence:validInference(inference)?numeric(inference.max_probability):null,valid:validInference(inference)},
      portfolios:holdings,last_pipeline_execution:logs[0]??null,timestamp:new Date().toISOString()});
  } catch {
    return NextResponse.json({status:'UNAVAILABLE',database:{connected:false},reasons:['Database inspection failed; no cached healthy state is substituted.'],timestamp:new Date().toISOString()},{status:503});
  }
}
