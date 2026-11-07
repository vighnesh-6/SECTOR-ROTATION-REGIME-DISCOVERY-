"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { TerminalPanel } from "@/components/ui/terminal-panel";
import { MetricTile } from "@/components/ui/metric-tile";
import { StatusBadge } from "@/components/ui/status-badge";
import { SectionHeader } from "@/components/ui/section-header";
import { DataTable, ColumnDef } from "@/components/ui/data-table";
import {
  LoadingMetricSkeleton,
  LoadingTableSkeleton,
} from "@/components/ui/loading-state";
import { EmptyState } from "@/components/ui/empty-state";
import {
  ShieldAlert,
  ArrowRight,
  TrendingUp,
  RefreshCw,
  Lock,
} from "lucide-react";

interface RegimeData {
  date: string;
  period: string;
  accepted_regime: {
    id: number;
    economic_name: string;
    is_confident: boolean;
    max_probability: number;
    raw_argmax: number;
  };
  probabilities: Array<{ id: number; name: string; prob: number }>;
  current_allocations: Array<{
    variant: string;
    holding_days_after: number;
    rebalance_triggered: boolean;
    rebalance_bypassed_r3: boolean;
    turnover: string | number;
    w_nifty50: string | number;
    w_auto: string | number;
    w_bank: string | number;
    w_fmcg: string | number;
    w_it: string | number;
    w_metal: string | number;
    w_pharma: string | number;
    w_cash: string | number;
  }>;
}

interface PortfolioData {
  latest_holdings: Array<{
    variant: string;
    date: string;
    net_nav: string | number;
    net_return: string | number;
    accepted_regime: number;
  }>;
  strategy_simulations: Array<{
    variant: string;
    date: string;
    net_nav: string | number;
    net_return: string | number;
  }>;
  benchmark_simulations: Array<{
    benchmark_name: string;
    date: string;
    net_nav: string | number;
  }>;
}

export default function OverviewPage() {
  const [regime, setRegime] = useState<RegimeData | null>(null);
  const [portfolio, setPortfolio] = useState<PortfolioData | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    try {
      setError(null);
      const [regimeRes, portRes] = await Promise.all([
        fetch("/api/v1/regime/latest").then((r) => {
          if (!r.ok) throw new Error(`Regime API returned HTTP ${r.status}`);
          return r.json();
        }),
        fetch("/api/v1/portfolios").then((r) => {
          if (!r.ok) throw new Error(`Portfolios API returned HTTP ${r.status}`);
          return r.json();
        }),
      ]);
      setRegime(regimeRes);
      setPortfolio(portRes);
    } catch (err: any) {
      console.error("Failed to load overview data:", err);
      setError(err?.message || "Failed to connect to Neon database.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleRefresh = () => {
    setRefreshing(true);
    fetchData();
  };

  // Target allocations table columns definition
  const allocationColumns: ColumnDef<any>[] = [
    {
      key: "variant",
      header: "Strategy Variant",
      render: (row) => (
        <div className="flex items-center gap-1.5 font-bold text-terminal-primary">
          <span>Strategy {row.variant}</span>
          {row.variant === "1B" && (
            <span className="text-[10px] font-sans px-1.5 py-0.2 rounded bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/30">
              Optimal
            </span>
          )}
        </div>
      ),
    },
    {
      key: "specification",
      header: "Architecture & Template",
      render: (row) => {
        const isTplA = row.variant.startsWith("1");
        return (
          <span className="text-terminal-muted">
            {isTplA ? "Template A (100% Fully Invested)" : "Template B (Dynamic Defensive Floor)"}
          </span>
        );
      },
    },
    {
      key: "weighting",
      header: "Weighting Scheme",
      render: (row) => (
        <span className="text-terminal-primary">
          {row.variant.endsWith("A") ? "Equal Weighting" : "Inverse Volatility"}
        </span>
      ),
    },
    {
      key: "lockup",
      header: "Holding Days",
      align: "center",
      render: (row) => (
        <span className="font-mono text-terminal-primary">
          {row.holding_days_after}d / 5d lock
        </span>
      ),
    },
    {
      key: "active_sectors",
      header: "Target Sector Allocation",
      render: (row) => {
        const sectors: { name: string; pct: number }[] = [];
        if (parseFloat(row.w_auto) > 0) sectors.push({ name: "AUTO", pct: row.w_auto * 100 });
        if (parseFloat(row.w_bank) > 0) sectors.push({ name: "BANK", pct: row.w_bank * 100 });
        if (parseFloat(row.w_fmcg) > 0) sectors.push({ name: "FMCG", pct: row.w_fmcg * 100 });
        if (parseFloat(row.w_it) > 0) sectors.push({ name: "IT", pct: row.w_it * 100 });
        if (parseFloat(row.w_metal) > 0) sectors.push({ name: "METAL", pct: row.w_metal * 100 });
        if (parseFloat(row.w_pharma) > 0) sectors.push({ name: "PHARMA", pct: row.w_pharma * 100 });

        if (sectors.length === 0) {
          return <span className="text-terminal-muted italic">100% Cash Reserve</span>;
        }

        return (
          <div className="flex flex-wrap gap-1.5">
            {sectors.map((s) => (
              <span
                key={s.name}
                className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-sm bg-terminal-secondary text-[11px] font-mono border border-terminal-border"
              >
                <span className="text-terminal-muted">{s.name}</span>
                <span className="font-semibold text-terminal-primary">
                  {s.pct.toFixed(1)}%
                </span>
              </span>
            ))}
          </div>
        );
      },
    },
    {
      key: "w_cash",
      header: "Cash Floor",
      align: "right",
      render: (row) => {
        const cashPct = parseFloat(row.w_cash) * 100;
        return (
          <span
            className={`font-mono font-semibold ${
              cashPct > 0 ? "text-amber-600 dark:text-amber-400" : "text-terminal-muted"
            }`}
          >
            {cashPct.toFixed(1)}%
          </span>
        );
      },
    },
  ];

  // Benchmark return calculation directly from simulation data
  const benchSims = portfolio?.benchmark_simulations?.filter((b) => b.benchmark_name === "NIFTY50_BUY_HOLD") || [];
  const initialBenchNav = benchSims[0]?.net_nav ? parseFloat(String(benchSims[0].net_nav)) : 1.0;
  const latestBenchNav = benchSims[benchSims.length - 1]?.net_nav ? parseFloat(String(benchSims[benchSims.length - 1].net_nav)) : null;
  const benchHoldoutReturn = latestBenchNav && initialBenchNav > 0
    ? ((latestBenchNav / initialBenchNav - 1.0) * 100).toFixed(1)
    : "—";

  // Strategy 1B NAV and holdout return directly from simulation data
  const s1bSims = portfolio?.strategy_simulations?.filter((s) => s.variant === "1B") || [];
  const s1bInitial = s1bSims[0]?.net_nav ? parseFloat(String(s1bSims[0].net_nav)) : null;
  const s1b = portfolio?.latest_holdings?.find((h) => h.variant === "1B");
  const s1bLatest = s1b ? parseFloat(String(s1b.net_nav)) : null;
  const s1bReturn = s1bLatest && s1bInitial && s1bInitial > 0
    ? ((s1bLatest / s1bInitial - 1.0) * 100).toFixed(1)
    : null;

  return (
    <div className="space-y-5">
      {/* Page Title & Institutional Telemetry Toolbar */}
      <SectionHeader
        title="Executive Overview & Market Regime Telemetry"
        description="National Stock Exchange of India (NSE) &bull; 8-Index Gaussian HMM Causal Engine &bull; Holdout Compounding"
        badge={
          <StatusBadge
            label={regime?.accepted_regime.is_confident ? "CONFIDENT INFERENCE" : "HYSTERESIS PERSISTENCE"}
            variant={regime?.accepted_regime.is_confident ? "success" : "warning"}
          />
        }
        action={
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-mono text-terminal-muted hidden sm:inline">
              Session: {regime?.date || "2026-11-06"}
            </span>
            <button
              onClick={handleRefresh}
              disabled={refreshing}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-mono rounded-sm border border-terminal-border bg-terminal-secondary hover:bg-terminal-border/40 text-terminal-primary transition-colors disabled:opacity-50"
              title="Refresh database telemetry"
            >
              <RefreshCw className={`w-3 h-3 ${refreshing ? "animate-spin" : ""}`} />
              <span>{refreshing ? "FETCHING" : "SYNC"}</span>
            </button>
          </div>
        }
      />

      {/* Top Telemetry KPI Metric Tiles */}
      {loading ? (
        <LoadingMetricSkeleton count={4} />
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3.5">
          <MetricTile
            label="Inferred Market Regime"
            value={regime ? `R${regime.accepted_regime.id}` : "—"}
            delta={regime?.accepted_regime.economic_name || "—"}
            deltaType="neutral"
            subtitle={`Filtered State (${regime?.date || "—"})`}
          />
          <MetricTile
            label="Posterior Confidence"
            value={regime ? `${(regime.accepted_regime.max_probability * 100).toFixed(1)}%` : "—"}
            delta={regime?.accepted_regime.is_confident ? "P ≥ 0.50 Confirmed" : "Hysteresis Hold"}
            deltaType={regime?.accepted_regime.is_confident ? "positive" : "warning"}
            subtitle="Forward Gaussian Probability"
          />
          <MetricTile
            label="Strategy 1B (Optimal) NAV"
            value={s1bLatest ? s1bLatest.toFixed(4) : "—"}
            delta={s1bReturn ? `${parseFloat(s1bReturn) >= 0 ? "+" : ""}${s1bReturn}% Holdout` : "—"}
            deltaType={s1bReturn && parseFloat(s1bReturn) >= 0 ? "positive" : "negative"}
            subtitle="Template A &bull; Inverse Volatility"
          />
          <MetricTile
            label="NIFTY 50 Benchmark NAV"
            value={latestBenchNav ? latestBenchNav.toFixed(4) : "—"}
            delta={benchHoldoutReturn !== "—" ? `${parseFloat(benchHoldoutReturn) >= 0 ? "+" : ""}${benchHoldoutReturn}% Holdout` : "—"}
            deltaType="neutral"
            subtitle="Passive Buy-and-Hold"
          />
        </div>
      )}

      {/* Regime Classification & Forward Probability Matrix */}
      {loading ? (
        <LoadingTableSkeleton rows={4} columns={2} />
      ) : error ? (
        <EmptyState
          title="Telemetry Ingestion Offline"
          description={error}
          action={
            <button
              onClick={handleRefresh}
              className="px-3 py-1.5 text-xs font-mono rounded-sm border border-terminal-border bg-terminal-panel text-terminal-primary hover:bg-terminal-secondary"
            >
              Retry Database Connection
            </button>
          }
        />
      ) : regime && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
          {/* Inferred Regime Card */}
          <div className="lg:col-span-5">
            <TerminalPanel
              title="Active Inferred State"
              subtitle={`Causal Evaluation as of ${regime.date}`}
              headerRight={
                <StatusBadge
                  label={`REGIME ${regime.accepted_regime.id}`}
                  variant="regime"
                  regimeId={regime.accepted_regime.id}
                  size="md"
                />
              }
            >
              <div className="space-y-4">
                <div>
                  <div className="text-lg font-bold text-terminal-primary">
                    {regime.accepted_regime.economic_name}
                  </div>
                  <p className="text-xs text-terminal-muted mt-1 leading-relaxed">
                    Identified via 8-index Gaussian Hidden Markov Model with 6 hidden states.
                    State switching adheres to strict 5-day persistence lockup unless overridden by
                    crisis state (R3).
                  </p>
                </div>

                <div className="grid grid-cols-2 gap-2 pt-2 border-t border-terminal-border/60">
                  <div className="p-2 rounded-sm bg-terminal-secondary/50 border border-terminal-border/50">
                    <span className="text-[10px] font-mono uppercase text-terminal-muted block">
                      Raw Argmax
                    </span>
                    <span className="font-mono text-sm font-bold text-terminal-primary">
                      State {regime.accepted_regime.raw_argmax}
                    </span>
                  </div>
                  <div className="p-2 rounded-sm bg-terminal-secondary/50 border border-terminal-border/50">
                    <span className="text-[10px] font-mono uppercase text-terminal-muted block">
                      Switching Rule
                    </span>
                    <span className="font-mono text-sm font-bold text-terminal-primary">
                      {regime.accepted_regime.is_confident ? "Posterior ≥ 0.50" : "Incumbent Guard"}
                    </span>
                  </div>
                </div>

                <div className="pt-2 border-t border-terminal-border/60 flex items-center justify-between text-xs">
                  <span className="text-terminal-muted">Detailed HMM State Analytics</span>
                  <Link
                    href="/regime-intelligence"
                    className="inline-flex items-center gap-1 font-mono text-xs text-terminal-primary hover:underline"
                  >
                    <span>View Regime Intelligence</span>
                    <ArrowRight className="w-3 h-3" />
                  </Link>
                </div>
              </div>
            </TerminalPanel>
          </div>

          {/* Forward-Filtered Probabilities Distribution */}
          <div className="lg:col-span-7">
            <TerminalPanel
              title="Forward State Probability Distribution"
              subtitle="Posterior mass across 6 Gaussian regimes"
              headerRight={
                <span className="text-[11px] font-mono text-terminal-muted">
                  ∑ P(S_t | Y_{`1:t`}) = 1.000
                </span>
              }
            >
              <div className="space-y-2.5">
                {regime.probabilities.map((p) => {
                  const isAccepted = p.id === regime.accepted_regime.id;
                  const pct = p.prob * 100;
                  return (
                    <div
                      key={p.id}
                      className={`p-2 rounded-sm border transition-colors ${
                        isAccepted
                          ? "bg-terminal-secondary/60 border-terminal-primary/40"
                          : "bg-terminal-panel border-terminal-border/40"
                      }`}
                    >
                      <div className="flex items-center justify-between text-xs mb-1">
                        <div className="flex items-center gap-2">
                          <StatusBadge
                            label={`R${p.id}`}
                            variant="regime"
                            regimeId={p.id}
                            size="sm"
                          />
                          <span
                            className={`font-mono ${
                              isAccepted
                                ? "font-bold text-terminal-primary"
                                : "text-terminal-muted"
                            }`}
                          >
                            {p.name}
                          </span>
                        </div>
                        <span className="font-mono tabular-nums font-semibold text-terminal-primary">
                          {pct.toFixed(2)}%
                        </span>
                      </div>
                      <div className="w-full bg-terminal-secondary h-1.5 rounded-sm overflow-hidden">
                        <div
                          className={`h-full transition-all duration-300 ${
                            isAccepted
                              ? "bg-terminal-primary"
                              : "bg-terminal-muted/40"
                          }`}
                          style={{ width: `${Math.max(pct, 0.5)}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </TerminalPanel>
          </div>
        </div>
      )}

      {/* Authorized Portfolio Allocations Table */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <div>
            <h3 className="font-mono text-xs font-bold uppercase tracking-wider text-terminal-primary">
              Authorized Strategy Allocations
            </h3>
            <p className="text-[11px] font-mono text-terminal-muted">
              Live weights enforced at Date t Close for T+1 execution across all 4 strategy variants
            </p>
          </div>
          <Link
            href="/portfolio-analytics"
            className="inline-flex items-center gap-1 font-mono text-xs text-terminal-primary hover:underline"
          >
            <span>Full Portfolio Analytics</span>
            <ArrowRight className="w-3 h-3" />
          </Link>
        </div>

        {loading ? (
          <LoadingTableSkeleton rows={4} columns={6} />
        ) : (
          <DataTable
            columns={allocationColumns}
            data={regime?.current_allocations || []}
            keyField="variant"
            zebra
          />
        )}
      </div>

      {/* Institutional Architecture & Systematic Risk Safeguards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5 pt-2">
        <div className="p-3.5 rounded-sm border border-terminal-border bg-terminal-panel">
          <div className="flex items-center gap-2 mb-1.5">
            <Lock className="w-4 h-4 text-terminal-muted stroke-[1.5]" />
            <span className="font-mono text-xs font-bold uppercase tracking-wider text-terminal-primary">
              5-Day Holding Lockup
            </span>
          </div>
          <p className="text-xs text-terminal-muted leading-relaxed">
            Eliminates whipsaws in choppy rotation markets. Elective rebalancing requires at least
            5 elapsed trading sessions before capital can be reallocated.
          </p>
        </div>

        <div className="p-3.5 rounded-sm border border-terminal-border bg-terminal-panel">
          <div className="flex items-center gap-2 mb-1.5">
            <ShieldAlert className="w-4 h-4 text-rose-500 stroke-[1.5]" />
            <span className="font-mono text-xs font-bold uppercase tracking-wider text-terminal-primary">
              Regime 3 Crisis Override
            </span>
          </div>
          <p className="text-xs text-terminal-muted leading-relaxed">
            Acute Liquidation (R3) immediately overrides the 5-day lockup period, executing an
            emergency shift to defensive assets (Pharma, FMCG) and cash floors.
          </p>
        </div>

        <div className="p-3.5 rounded-sm border border-terminal-border bg-terminal-panel">
          <div className="flex items-center gap-2 mb-1.5">
            <TrendingUp className="w-4 h-4 text-emerald-500 stroke-[1.5]" />
            <span className="font-mono text-xs font-bold uppercase tracking-wider text-terminal-primary">
              T+1 Realistic Friction
            </span>
          </div>
          <p className="text-xs text-terminal-muted leading-relaxed">
            Signals generated at Date t Close execute at Date t+1 Close with institutional 15 bps
            one-way transaction costs to strictly guarantee zero lookahead bias.
          </p>
        </div>
      </div>
    </div>
  );
}
