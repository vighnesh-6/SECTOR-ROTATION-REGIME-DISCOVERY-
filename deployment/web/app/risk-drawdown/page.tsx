"use client";

import React, { useEffect, useState } from "react";
import { TerminalPanel } from "@/components/ui/terminal-panel";
import { MetricTile } from "@/components/ui/metric-tile";
import { StatusBadge } from "@/components/ui/status-badge";
import { SectionHeader } from "@/components/ui/section-header";
import { DataTable, ColumnDef } from "@/components/ui/data-table";
import { LoadingMetricSkeleton, LoadingTableSkeleton } from "@/components/ui/loading-state";
import { EmptyState } from "@/components/ui/empty-state";
import { ShieldAlert, RefreshCw, Lock, AlertTriangle } from "lucide-react";

interface RiskMetricRow {
  variant: string;
  name: string;
  maxDrawdown: string;
  annualizedVol: string;
  sharpeRatio: string;
  sortinoRatio: string;
  var95: string;
  cvar95: string;
}

export default function RiskDrawdownPage() {
  const [riskData, setRiskData] = useState<RiskMetricRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const calculateRiskMetrics = (simulations: any[], benchmarks: any[]) => {
    const rows: RiskMetricRow[] = [];

    const variants = [
      { id: "1A", name: "Template A &bull; Equal Weight" },
      { id: "1B", name: "Template A &bull; Inverse Vol (Optimal)" },
      { id: "2A", name: "Template B &bull; Equal Weight + Cash" },
      { id: "2B", name: "Template B &bull; Inverse Vol + Cash" },
    ];

    for (const v of variants) {
      const vSims = simulations.filter((s) => s.variant === v.id);
      if (vSims.length === 0) continue;

      const navs: number[] = vSims.map((s) => parseFloat(String(s.net_nav)));
      const rets: number[] = vSims.map((s) => parseFloat(String(s.net_return)));

      // Compute peak-to-trough Maximum Drawdown
      let peak = navs[0];
      let maxDd = 0;
      for (const nav of navs) {
        if (nav > peak) peak = nav;
        const dd = (nav - peak) / peak;
        if (dd < maxDd) maxDd = dd;
      }

      // Volatility and return metrics
      const n = rets.length;
      const meanRet = rets.reduce((a, b) => a + b, 0) / n;
      const variance = rets.reduce((a, b) => a + Math.pow(b - meanRet, 2), 0) / (n - 1);
      const dailyVol = Math.sqrt(variance);
      const annVol = dailyVol * Math.sqrt(252);
      const annRet = meanRet * 252;
      const rf = 0.06;
      const sharpe = annVol > 0 ? (annRet - rf) / annVol : 0;

      // Downside deviation for Sortino
      const negRets = rets.filter((r) => r < 0);
      const downsideVar = negRets.length > 0 ? negRets.reduce((a, b) => a + Math.pow(b, 2), 0) / n : 1e-4;
      const downsideDev = Math.sqrt(downsideVar) * Math.sqrt(252);
      const sortino = downsideDev > 0 ? (annRet - rf) / downsideDev : 0;

      // VaR 95% and CVaR 95%
      const sortedRets = [...rets].sort((a, b) => a - b);
      const varIdx = Math.floor(0.05 * sortedRets.length);
      const var95 = sortedRets[varIdx];
      const tailRets = sortedRets.slice(0, varIdx + 1);
      const cvar95 = tailRets.reduce((a, b) => a + b, 0) / tailRets.length;

      rows.push({
        variant: v.id,
        name: v.name,
        maxDrawdown: `${(maxDd * 100).toFixed(2)}%`,
        annualizedVol: `${(annVol * 100).toFixed(2)}%`,
        sharpeRatio: sharpe.toFixed(2),
        sortinoRatio: sortino.toFixed(2),
        var95: `${(var95 * 100).toFixed(2)}%`,
        cvar95: `${(cvar95 * 100).toFixed(2)}%`,
      });
    }

    // Benchmark: NIFTY 50
    const niftySims = benchmarks.filter((b) => b.benchmark_name === "NIFTY50_BUY_HOLD");
    if (niftySims.length > 0) {
      const navs: number[] = niftySims.map((s) => parseFloat(String(s.net_nav)));
      const rets: number[] = niftySims.map((s) => parseFloat(String(s.net_return)));

      let peak = navs[0];
      let maxDd = 0;
      for (const nav of navs) {
        if (nav > peak) peak = nav;
        const dd = (nav - peak) / peak;
        if (dd < maxDd) maxDd = dd;
      }

      const n = rets.length;
      const meanRet = rets.reduce((a, b) => a + b, 0) / n;
      const variance = rets.reduce((a, b) => a + Math.pow(b - meanRet, 2), 0) / (n - 1);
      const annVol = Math.sqrt(variance) * Math.sqrt(252);
      const annRet = meanRet * 252;
      const rf = 0.06;
      const sharpe = annVol > 0 ? (annRet - rf) / annVol : 0;

      const negRets = rets.filter((r) => r < 0);
      const downsideVar = negRets.length > 0 ? negRets.reduce((a, b) => a + Math.pow(b, 2), 0) / n : 1e-4;
      const downsideDev = Math.sqrt(downsideVar) * Math.sqrt(252);
      const sortino = downsideDev > 0 ? (annRet - rf) / downsideDev : 0;

      const sortedRets = [...rets].sort((a, b) => a - b);
      const varIdx = Math.floor(0.05 * sortedRets.length);
      const var95 = sortedRets[varIdx];
      const tailRets = sortedRets.slice(0, varIdx + 1);
      const cvar95 = tailRets.reduce((a, b) => a + b, 0) / tailRets.length;

      rows.push({
        variant: "BENCH",
        name: "NIFTY 50 (Passive Buy & Hold)",
        maxDrawdown: `${(maxDd * 100).toFixed(2)}%`,
        annualizedVol: `${(annVol * 100).toFixed(2)}%`,
        sharpeRatio: sharpe.toFixed(2),
        sortinoRatio: sortino.toFixed(2),
        var95: `${(var95 * 100).toFixed(2)}%`,
        cvar95: `${(cvar95 * 100).toFixed(2)}%`,
      });
    }

    return rows;
  };

  const fetchRisk = async () => {
    try {
      setError(null);
      const res = await fetch("/api/v1/portfolios");
      if (!res.ok) throw new Error(`API error: HTTP ${res.status}`);
      const json = await res.json();
      const rows = calculateRiskMetrics(json.strategy_simulations || [], json.benchmark_simulations || []);
      setRiskData(rows);
    } catch (e: any) {
      console.error("Failed to load risk telemetry:", e);
      setError(e.message || "Failed to load risk data.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchRisk();
  }, []);

  const columns: ColumnDef<RiskMetricRow>[] = [
    {
      key: "variant",
      header: "Portfolio / Index",
      render: (row) => (
        <div className="flex items-center gap-2">
          <span className="font-bold text-terminal-primary">
            {row.variant === "BENCH" ? "NIFTY 50" : `Strategy ${row.variant}`}
          </span>
          {row.variant === "1B" && (
            <span className="text-[10px] font-sans px-1.5 py-0.2 rounded bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/30">
              Optimal
            </span>
          )}
        </div>
      ),
    },
    {
      key: "maxDrawdown",
      header: "Max Drawdown (MDD)",
      align: "right",
      render: (row) => (
        <span
          className={`font-mono font-semibold ${
            parseFloat(row.maxDrawdown) < -20
              ? "text-rose-600 dark:text-rose-400"
              : "text-amber-600 dark:text-amber-400"
          }`}
        >
          {row.maxDrawdown}
        </span>
      ),
    },
    {
      key: "annualizedVol",
      header: "Ann. Volatility",
      align: "right",
      render: (row) => (
        <span className="font-mono text-terminal-primary">{row.annualizedVol}</span>
      ),
    },
    {
      key: "sharpeRatio",
      header: "Sharpe (Rf=6%)",
      align: "right",
      render: (row) => (
        <span className="font-mono font-semibold text-terminal-primary">{row.sharpeRatio}</span>
      ),
    },
    {
      key: "sortinoRatio",
      header: "Sortino Ratio",
      align: "right",
      render: (row) => (
        <span className="font-mono text-terminal-primary">{row.sortinoRatio}</span>
      ),
    },
    {
      key: "var95",
      header: "Daily VaR (95%)",
      align: "right",
      render: (row) => (
        <span className="font-mono text-rose-600 dark:text-rose-400">{row.var95}</span>
      ),
    },
    {
      key: "cvar95",
      header: "Expected Shortfall",
      align: "right",
      render: (row) => (
        <span className="font-mono text-rose-600 dark:text-rose-400">{row.cvar95}</span>
      ),
    },
  ];

  const s1bRow = riskData.find((r) => r.variant === "1B");
  const s2bRow = riskData.find((r) => r.variant === "2B");

  return (
    <div className="space-y-5">
      <SectionHeader
        title="Institutional Risk & Drawdown Analytics"
        description="Downside Deviation &bull; Tail Risk (VaR/CVaR) &bull; Maximum Drawdown Mitigation &bull; Realized Empirical Telemetry"
        badge={
          <StatusBadge
            label="REALIZED RISK PROFILES"
            variant="success"
          />
        }
        action={
          <button
            onClick={() => {
              setRefreshing(true);
              fetchRisk();
            }}
            disabled={refreshing}
            className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-mono rounded-sm border border-terminal-border bg-terminal-secondary hover:bg-terminal-border/40 text-terminal-primary transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-3 h-3 ${refreshing ? "animate-spin" : ""}`} />
            <span>{refreshing ? "CALCULATING" : "SYNC"}</span>
          </button>
        }
      />

      {/* Risk KPI Tiles */}
      {loading ? (
        <LoadingMetricSkeleton count={4} />
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3.5">
          <MetricTile
            label="Optimal Strategy 1B MDD"
            value={s1bRow ? s1bRow.maxDrawdown : "—"}
            delta="Realized Peak-to-Trough"
            deltaType="neutral"
            subtitle="Template A &bull; Inverse Volatility"
          />
          <MetricTile
            label="Strategy 2B MDD"
            value={s2bRow ? s2bRow.maxDrawdown : "—"}
            delta="Defensive Cash Floor"
            deltaType="neutral"
            subtitle="Template B &bull; Inverse Volatility"
          />
          <MetricTile
            label="Crisis Override Activation"
            value="0d Lag"
            delta="Immediate R3 Defense"
            deltaType="positive"
            subtitle="Bypasses 5-Day Holding Lock"
          />
          <MetricTile
            label="Friction Slippage Budget"
            value="15 bps"
            delta="One-Way Transaction Drag"
            deltaType="neutral"
            subtitle="Applied on Every Portfolio Turnover"
          />
        </div>
      )}

      {/* Comparative Risk Table */}
      {loading ? (
        <LoadingTableSkeleton rows={5} columns={7} />
      ) : error ? (
        <EmptyState
          title="Risk Telemetry Offline"
          description={error}
          action={
            <button
              onClick={fetchRisk}
              className="px-3 py-1.5 text-xs font-mono rounded-sm border border-terminal-border bg-terminal-panel text-terminal-primary"
            >
              Retry
            </button>
          }
        />
      ) : (
        <TerminalPanel
          title="Comparative Downside & Tail Risk Profiles (Calculated from Live Simulations)"
          subtitle="Evaluated across all holdout trading sessions net of 15 bps one-way execution drag"
        >
          <DataTable
            columns={columns}
            data={riskData}
            keyField="variant"
            zebra
          />
        </TerminalPanel>
      )}

      {/* Downside Protection Mechanisms */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5">
        <div className="p-3.5 rounded-sm border border-terminal-border bg-terminal-panel">
          <div className="flex items-center gap-2 mb-1.5">
            <Lock className="w-4 h-4 text-terminal-muted stroke-[1.5]" />
            <h4 className="font-mono text-xs font-bold uppercase text-terminal-primary">
              Turnover Dampening (5-Day Lock)
            </h4>
          </div>
          <p className="text-xs text-terminal-muted leading-relaxed">
            Eliminates rapid rebalancing churn during market consolidations. By requiring 5 full
            trading sessions before non-crisis regime transitions, unnecessary friction drag is
            slashed by over 60%.
          </p>
        </div>

        <div className="p-3.5 rounded-sm border border-terminal-border bg-terminal-panel">
          <div className="flex items-center gap-2 mb-1.5">
            <ShieldAlert className="w-4 h-4 text-rose-500 stroke-[1.5]" />
            <h4 className="font-mono text-xs font-bold uppercase text-terminal-primary">
              Regime 3 Fast Liquidation
            </h4>
          </div>
          <p className="text-xs text-terminal-muted leading-relaxed">
            When the Gaussian HMM detects Acute Liquidation (R3), the lockup timer is instantly
            bypassed. Capital is reallocated into low-beta defensives (Pharma, FMCG) and cash
            reserves to preserve principal.
          </p>
        </div>

        <div className="p-3.5 rounded-sm border border-terminal-border bg-terminal-panel">
          <div className="flex items-center gap-2 mb-1.5">
            <AlertTriangle className="w-4 h-4 text-amber-500 stroke-[1.5]" />
            <h4 className="font-mono text-xs font-bold uppercase text-terminal-primary">
              Conservative Template B Buffers
            </h4>
          </div>
          <p className="text-xs text-terminal-muted leading-relaxed">
            For institutional mandates requiring defensive protection, Template B maintains
            systematic cash buffers of 20% to 50% during turbulent and digestive market regimes
            (R1, R3, R5).
          </p>
        </div>
      </div>
    </div>
  );
}
