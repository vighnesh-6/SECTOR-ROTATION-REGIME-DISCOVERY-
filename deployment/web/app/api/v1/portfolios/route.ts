import { NextRequest, NextResponse } from 'next/server';
import { queryNeon } from '@/lib/neon';
import { VARIANTS } from '@/lib/contracts';
import { dates, InputError, apiError } from '@/lib/http';
import research from '@/lib/research-artifacts.json';
export const dynamic = 'force-dynamic';
export async function GET(request:NextRequest) {
  try {
    const p=new URL(request.url).searchParams,period=p.get('period')??'holdout',variant=p.get('variant')?.toUpperCase();
    const windows:Record<string,[string,string]>={full:[research.periods.simulation_start,'2099-12-31'],train:[research.periods.simulation_start,research.periods.train_end],holdout:[research.periods.holdout_start,research.periods.holdout_end],post:[research.periods.post_research_start,'2099-12-31']};
    if(!Object.hasOwn(windows,period) || (variant && !VARIANTS.includes(variant as typeof VARIANTS[number]))) throw new InputError('Unknown period or strategy variant.');
    const {from,to}=dates(p,...windows[period]),params:unknown[]=[from,to];
    let filter='WHERE date >= $1::date AND date <= $2::date';
    if(variant){params.push(variant);filter+=' AND variant=$3';}
    const [strategies,benchmarks,holdings]=await Promise.all([
      queryNeon(`WITH history AS (SELECT variant,date,period,rebalance_executed,actual_turnover,transaction_cost,net_return,net_nav,accepted_regime,w_post_auto,w_post_bank,w_post_fmcg,w_post_it,w_post_metal,w_post_pharma,w_post_cash,LAG(net_nav) OVER(PARTITION BY variant ORDER BY date) AS previous_nav FROM portfolio_simulations_daily) SELECT variant,date::text AS date,period,rebalance_executed,actual_turnover,transaction_cost,net_return,net_nav,accepted_regime,w_post_auto,w_post_bank,w_post_fmcg,w_post_it,w_post_metal,w_post_pharma,w_post_cash,previous_nav FROM history ${filter} ORDER BY history.date,variant`,params),
      queryNeon('WITH history AS (SELECT benchmark_name,date,period,net_return,net_nav,LAG(net_nav) OVER(PARTITION BY benchmark_name ORDER BY date) AS previous_nav FROM benchmark_simulations_daily) SELECT benchmark_name,date::text AS date,period,net_return,net_nav,previous_nav FROM history WHERE date >= $1::date AND date <= $2::date ORDER BY history.date,benchmark_name',[from,to]),
      queryNeon('SELECT DISTINCT ON (variant) variant,date::text AS date,period,net_nav,net_return,actual_turnover,transaction_cost,rebalance_executed,accepted_regime,w_post_auto,w_post_bank,w_post_fmcg,w_post_it,w_post_metal,w_post_pharma,w_post_cash FROM portfolio_simulations_daily ORDER BY variant,date DESC')
    ]);
    return NextResponse.json({filters:{period,variant:variant??'ALL',from_date:from,to_date:to},total_simulation_records:strategies.length,latest_holdings:variant?holdings.filter(r=>r.variant===variant):holdings,strategy_simulations:strategies,benchmark_simulations:benchmarks,
      provenance:{source:'Neon daily simulation tables',research_holdout_end:research.periods.holdout_end,period_override:p.has('from_date')||p.has('to_date'),metric_convention:'252 sessions; sample volatility; Sharpe Rf=0%; Sortino MAR=0%. Undefined ratios remain null.'}});
  }catch(error){return apiError(error);}
}
