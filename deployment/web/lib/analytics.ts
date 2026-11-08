import { numeric, VARIANTS } from './contracts';
export type Observation = {date:string;net_nav:unknown;net_return:unknown;previous_nav?:unknown;actual_turnover?:unknown;transaction_cost?:unknown;[key:string]:unknown};
export function ordered(rows:Observation[]) { return [...rows].sort((a,b)=>a.date.localeCompare(b.date)); }
export function baseNav(rows:Observation[]):number|null {
  if(!rows.length)return null;
  const r=ordered(rows)[0],prev=numeric(r.previous_nav),nav=numeric(r.net_nav),ret=numeric(r.net_return);
  if(prev!==null&&prev>0)return prev;
  return nav!==null&&nav>0&&ret!==null&&ret>-1?nav/(1+ret):null;
}
export function performance(input:Observation[]) {
  const rows=ordered(input),base=baseNav(rows);
  if(!rows.length||base===null||rows.some(r=>numeric(r.net_nav)===null||Number(r.net_nav)<=0||numeric(r.net_return)===null||Number(r.net_return)<-1))return null;
  const returns=rows.map(r=>Number(r.net_return)),navs=rows.map(r=>Number(r.net_nav)),n=returns.length;
  const mean=returns.reduce((a,b)=>a+b,0)/n;
  const volatility=n>1?Math.sqrt(returns.reduce((a,b)=>a+(b-mean)**2,0)/(n-1)*252):null;
  const downside=Math.sqrt(returns.reduce((a,b)=>a+Math.min(0,b)**2,0)/n*252);
  let peak=navs[0],mdd=0;
  for(const nav of navs){peak=Math.max(peak,nav);mdd=Math.min(mdd,nav/peak-1);}
  const sorted=[...returns].sort((a,b)=>a-b),index=Math.floor(0.05*n),tail=sorted.slice(0,index+1);
  return {count:n,start:rows[0].date,end:rows[n-1].date,base_nav:base,net_nav:navs[n-1],total_return:navs[n-1]/base-1,cagr:(navs[n-1]/base)**(252/n)-1,volatility,sharpe:volatility&&volatility>0?mean*252/volatility:null,sortino:downside>0?mean*252/downside:null,max_drawdown:mdd,var95:sorted[index],cvar95:tail.reduce((a,b)=>a+b,0)/tail.length,
    turnover:rows.every(r=>numeric(r.actual_turnover)!==null)?rows.reduce((a,r)=>a+Number(r.actual_turnover),0):null,
    transaction_cost:rows.every(r=>numeric(r.transaction_cost)!==null)?rows.reduce((a,r)=>a+Number(r.transaction_cost),0):null};
}
export function curve(series:Record<string,Observation[]>,drawdown=false) {
  const byDate:Record<string,Record<string,string|number|null>>={};
  for(const [key,input] of Object.entries(series)){
    const rows=ordered(input),base=baseNav(rows);if(base===null)continue;
    let peak:number|null=null;
    for(const r of rows){
      const nav=numeric(r.net_nav);
      byDate[r.date]??={date:r.date};
      if(nav===null||nav<=0){byDate[r.date][key]=null;continue;}
      peak=peak===null?nav:Math.max(peak,nav);
      byDate[r.date][key]=drawdown?100*(nav/peak-1):100*nav/base;
    }
  }
  const keys=Object.keys(series);
  return Object.values(byDate).sort((a,b)=>String(a.date).localeCompare(String(b.date))).map(row=>Object.fromEntries(['date',...keys].map(k=>[k,row[k]??null])));
}

export function simulationSeries(data:any):Record<string,Observation[]>{
 const series:Record<string,Observation[]>={};
 for(const v of VARIANTS)series[v]=(data?.strategy_simulations??[]).filter((r:any)=>r.variant===v);
 for(const name of Array.from(new Set<string>((data?.benchmark_simulations??[]).map((r:any)=>r.benchmark_name))))series[name]=(data?.benchmark_simulations??[]).filter((r:any)=>r.benchmark_name===name);
 return series;
}
