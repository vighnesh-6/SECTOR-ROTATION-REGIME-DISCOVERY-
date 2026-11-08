'use client';
import Link from 'next/link';
import { ThemeToggle } from './theme-toggle';
import { StatusBadge } from './status-badge';
import { useApi } from '@/lib/use-api';
import { fmt } from '@/lib/contracts';
export function TerminalHeader(){
 const {data,error,loading}=useApi<any>('/api/v1/health',true);
 const status=loading?'CHECKING':error?'UNAVAILABLE':data?.status??'UNKNOWN';
 return <header className="border-b border-terminal-border bg-terminal-panel px-4 sm:px-6 py-4"><div className="max-w-[1600px] mx-auto flex flex-col lg:flex-row gap-4 lg:items-center justify-between">
 <Link href="/" className="flex items-center gap-3"><span className="w-9 h-9 rounded border border-emerald-400/40 bg-emerald-500/10 text-emerald-500 flex items-center justify-center font-mono font-bold">SR</span><span><span className="block text-sm font-semibold tracking-wide">SECTOR ROTATION REGIME DISCOVERY</span><span className="text-[11px] text-terminal-muted tracking-wider">NSE INDIA / QUANTITATIVE RESEARCH & PORTFOLIO INTELLIGENCE</span></span></Link>
 <div className="flex flex-wrap items-center gap-3 text-[11px] font-mono"><StatusBadge label={status} variant={status==='HEALTHY'?'success':status==='CHECKING'?'neutral':'warning'}/><span className="text-terminal-muted">Market {data?.database?.latest_candle_date??'—'}</span><span className="hidden sm:inline text-terminal-muted">Inference {data?.inference?.latest_regime_date??'—'}</span><span className="hidden xl:inline text-terminal-muted">DB {data?.database?.connected?fmt(data.database.latency_ms,0)+' ms':'unavailable'}</span><ThemeToggle/></div>
 </div></header>;
}
