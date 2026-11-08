'use client';
import { Area, AreaChart, Line, LineChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { EmptyState } from '@/components/ui/empty-state';
import { chartSeries } from '@/lib/chart-series';
import { numeric } from '@/lib/contracts';

type SeriesOptions = { label?: string; color?: string; dash?: string };
type ChartProps = {
  data: Record<string, any>[];
  keys: string[];
  percent?: boolean;
  stacked?: boolean;
  label: string;
  yLabel?: string;
  xLabel?: string;
  decimals?: number;
  tooltipDecimals?: number;
  points?: boolean;
  series?: Record<string, SeriesOptions>;
};

export function ResearchChart({
  data, keys, percent = false, stacked = false, label,
  yLabel = percent ? 'Percent (%)' : 'Rebased index (100 = pre-window)',
  xLabel = 'Trading session', decimals = 2, tooltipDecimals = decimals, points = false, series = {},
}: ChartProps) {
  if (!data.length) return <EmptyState title="No observations" description="No data is available for this selected window." />;
  const definitions = Object.fromEntries(keys.map(key => [key, { ...chartSeries(key), ...series[key] }]));
  const displayValue = (value: unknown, digits: number) => {
    const n = numeric(value);
    return n === null ? 'Unavailable' : `${n.toFixed(digits)}${percent ? '%' : ''}`;
  };
  const axes = [
    <CartesianGrid key="grid" stroke="var(--terminal-border)" strokeDasharray="3 3" vertical={false} />,
    <XAxis key="date" dataKey="date" minTickGap={65} height={48} tick={{ fontSize: 10, fill: 'var(--terminal-text-secondary)' }}
      tickFormatter={value => String(value).slice(0, 10)} axisLine={false} tickLine={false}
      label={{ value: xLabel, position: 'insideBottom', offset: -4, fill: 'var(--terminal-text-secondary)', fontSize: 11 }} />,
    <YAxis key="value" width={88} tick={{ fontSize: 10, fill: 'var(--terminal-text-secondary)' }}
      tickFormatter={value => displayValue(value, decimals)} domain={stacked ? [0, 100] : ['auto', 'auto']}
      axisLine={false} tickLine={false}
      label={{ value: yLabel, angle: -90, position: 'insideLeft', dx: -12, fill: 'var(--terminal-text-secondary)', fontSize: 11 }} />,
    <Tooltip key="tooltip" filterNull={false} content={({ active, payload, label: date }) => {
      if (!active || !payload?.length) return null;
      const observation = payload[0]?.payload ?? {};
      return <div className="rounded border border-terminal-border bg-terminal-panel p-3 shadow-lg text-xs">
        <p className="font-semibold mb-2">Session: {String(date)}</p>
        {keys.map(key => <div key={key} className="flex justify-between gap-5 py-1">
          <span className="flex items-center gap-2"><span className="inline-block h-2 w-2 rounded-full" style={{ background: definitions[key].color }} />{definitions[key].label}</span>
          <span className="font-mono">{displayValue(observation[key], tooltipDecimals)}</span>
        </div>)}
        <p className="text-terminal-muted mt-2">{yLabel}</p>
      </div>;
    }} />,
  ];
  const shared = { data, margin: { top: 12, right: 22, bottom: 12, left: 18 } };
  return <div className="min-w-0">
    <ul aria-label={label + ' legend'} className="flex flex-wrap gap-x-5 gap-y-2 mb-3 text-xs text-terminal-muted">
      {keys.map(key => <li key={key} className="flex items-center gap-2">
        <span className="inline-block w-5 border-t-2" style={{ borderColor: definitions[key].color, borderStyle: definitions[key].dash ? 'dashed' : 'solid' }} />
        {definitions[key].label}
      </li>)}
    </ul>
    <div role="img" aria-label={label} className="h-[340px] w-full min-w-0" data-chart={label}>
      <ResponsiveContainer width="100%" height="100%">
        {stacked ? <AreaChart {...shared}>{axes}{keys.map(key => <Area key={key} dataKey={key} name={definitions[key].label}
          type="stepAfter" stackId="allocation" stroke={definitions[key].color} fill={definitions[key].color}
          fillOpacity={0.7} connectNulls={false} isAnimationActive={false} />)}</AreaChart> :
          <LineChart {...shared}>{axes}{keys.map(key => <Line key={key} dataKey={key} name={definitions[key].label} type="linear"
            stroke={definitions[key].color} strokeDasharray={definitions[key].dash} strokeWidth={1.8}
            dot={points ? { r: 2 } : false} connectNulls={false} isAnimationActive={false} />)}</LineChart>}
      </ResponsiveContainer>
    </div>
  </div>;
}
