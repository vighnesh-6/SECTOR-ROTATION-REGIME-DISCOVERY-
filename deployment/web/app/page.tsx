"use client";

import React, { useEffect, useState } from "react";

interface RegimeData {
  date: string;
  accepted_regime: {
    id: number;
    economic_name: string;
    is_confident: boolean;
    max_probability: number;
  };
  probabilities: Array<{ id: number; name: string; prob: number }>;
  current_allocations: Array<any>;
}

interface PortfolioData {
  latest_holdings: Array<any>;
  strategy_simulations: Array<any>;
  benchmark_simulations: Array<any>;
}

interface RRGData {
  latest_date: string;
  sectors: Record<string, { current_ratio: number; current_momentum: number; quadrant: string }>;
}

export default function DashboardPage() {
  const [regime, setRegime] = useState<RegimeData | null>(null);
  const [portfolio, setPortfolio] = useState<PortfolioData | null>(null);
  const [rrg, setRrg] = useState<RRGData | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"overview" | "portfolios" | "rrg">("overview");

  useEffect(() => {
    async function loadData() {
      try {
        const [regimeRes, portRes, rrgRes] = await Promise.all([
          fetch("/api/v1/regime/latest").then((r) => (r.ok ? r.json() : null)),
          fetch("/api/v1/portfolios").then((r) => (r.ok ? r.json() : null)),
          fetch("/api/v1/rrg?trail=5").then((r) => (r.ok ? r.json() : null)),
        ]);
        setRegime(regimeRes);
        setPortfolio(portRes);
        setRrg(rrgRes);
      } catch (e) {
        console.error("Failed to load initial data", e);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 sm:px-6 lg:px-8">
      {/* Header */}
      <header className="border-b border-slate-800 pb-6 mb-8 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <span className="h-3 w-3 rounded-full bg-emerald-500 animate-pulse"></span>
            <span className="text-xs font-semibold tracking-wider text-emerald-400 uppercase">
              Daily EOD System Active
            </span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-white mt-1">
            Sector Rotation Regime Discovery
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Machine Learning Quantitative Architecture &bull; National Stock Exchange of India (NSE)
          </p>
        </div>

        {/* Tab Selector */}
        <div className="flex bg-slate-900 border border-slate-800 rounded-lg p-1">
          {(["overview", "portfolios", "rrg"] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-4 py-2 text-xs font-medium rounded-md capitalize transition ${
                activeTab === tab
                  ? "bg-indigo-600 text-white shadow-sm"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              {tab === "rrg" ? "Relative Rotation Graph" : tab}
            </button>
          ))}
        </div>
      </header>

      {loading ? (
        <div className="flex items-center justify-center py-24 text-slate-500 text-sm">
          Loading production telemetry from Neon PostgreSQL...
        </div>
      ) : (
        <>
          {/* Active Regime Banner */}
          {regime && (
            <div className="bg-gradient-to-r from-slate-900 via-indigo-950/40 to-slate-900 border border-indigo-900/50 rounded-xl p-6 mb-8 shadow-xl">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                  <div className="text-xs uppercase tracking-wider text-indigo-400 font-semibold">
                    Current Market Regime &bull; {regime.date}
                  </div>
                  <div className="text-2xl font-bold text-white mt-1">
                    Regime {regime.accepted_regime.id}: {regime.accepted_regime.economic_name}
                  </div>
                  <div className="text-sm text-slate-400 mt-1 flex items-center gap-2">
                    <span>
                      Confidence: {(regime.accepted_regime.max_probability * 100).toFixed(1)}%
                    </span>
                    <span>&bull;</span>
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold ${
                        regime.accepted_regime.is_confident
                          ? "bg-emerald-950 text-emerald-400 border border-emerald-800"
                          : "bg-amber-950 text-amber-400 border border-amber-800"
                      }`}
                    >
                      {regime.accepted_regime.is_confident
                        ? "P >= 0.50 Threshold Confirmed"
                        : "Incumbent Persistence"}
                    </span>
                  </div>
                </div>

                {/* Probability bars */}
                <div className="flex-1 max-w-md bg-slate-950/60 p-4 rounded-lg border border-slate-800">
                  <div className="text-xs text-slate-400 mb-2 font-medium">
                    HMM Forward Filtered Probabilities
                  </div>
                  <div className="space-y-1.5">
                    {regime.probabilities.map((p) => (
                      <div key={p.id} className="text-xs">
                        <div className="flex justify-between text-slate-300 mb-0.5">
                          <span>
                            R{p.id}: {p.name.split("/")[0]}
                          </span>
                          <span className="font-mono">{(p.prob * 100).toFixed(1)}%</span>
                        </div>
                        <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
                          <div
                            className={`h-1.5 rounded-full ${
                              p.id === regime.accepted_regime.id ? "bg-indigo-500" : "bg-slate-600"
                            }`}
                            style={{ width: `${Math.max(p.prob * 100, 2)}%` }}
                          ></div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 1: OVERVIEW */}
          {activeTab === "overview" && regime && (
            <div className="space-y-8">
              {/* Allocations Table */}
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
                <h2 className="text-lg font-semibold text-white mb-4">
                  Current Authorized Target Allocations across 4 Strategy Variants
                </h2>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm text-slate-300">
                    <thead className="bg-slate-950 text-xs uppercase text-slate-400 border-b border-slate-800">
                      <tr>
                        <th className="px-4 py-3">Variant</th>
                        <th className="px-4 py-3">Template</th>
                        <th className="px-4 py-3">Weighting</th>
                        <th className="px-4 py-3">Holding Days</th>
                        <th className="px-4 py-3">Target Holdings</th>
                        <th className="px-4 py-3">Cash Reserve</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800">
                      {regime.current_allocations.map((alloc) => {
                        const isTplA = alloc.variant.startsWith("1");
                        const isEq = alloc.variant.endsWith("A");
                        const holdings: string[] = [];
                        if (parseFloat(alloc.w_it) > 0) holdings.push(`IT ${(alloc.w_it * 100).toFixed(1)}%`);
                        if (parseFloat(alloc.w_pharma) > 0) holdings.push(`Pharma ${(alloc.w_pharma * 100).toFixed(1)}%`);
                        if (parseFloat(alloc.w_auto) > 0) holdings.push(`Auto ${(alloc.w_auto * 100).toFixed(1)}%`);
                        if (parseFloat(alloc.w_metal) > 0) holdings.push(`Metal ${(alloc.w_metal * 100).toFixed(1)}%`);
                        if (parseFloat(alloc.w_fmcg) > 0) holdings.push(`FMCG ${(alloc.w_fmcg * 100).toFixed(1)}%`);
                        if (parseFloat(alloc.w_bank) > 0) holdings.push(`Bank ${(alloc.w_bank * 100).toFixed(1)}%`);

                        return (
                          <tr key={alloc.variant} className="hover:bg-slate-800/40">
                            <td className="px-4 py-3 font-semibold text-white">{alloc.variant}</td>
                            <td className="px-4 py-3">{isTplA ? "Template A (100% Invested)" : "Template B (Defensive Cash Floor)"}</td>
                            <td className="px-4 py-3">{isEq ? "Equal Weight" : "Inverse Volatility"}</td>
                            <td className="px-4 py-3 font-mono">{alloc.holding_days_after} days</td>
                            <td className="px-4 py-3 text-emerald-400 font-medium">{holdings.join(", ") || "None"}</td>
                            <td className="px-4 py-3 font-mono text-slate-400">
                              {(parseFloat(alloc.w_cash) * 100).toFixed(1)}%
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* System Architecture Specifications */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5">
                  <div className="text-xs uppercase font-semibold text-indigo-400">5-Day Holding Lockup</div>
                  <div className="text-sm text-slate-300 mt-2">
                    Prevents excessive turnover in choppy markets. Elective regime changes require at least 5 elapsed trading sessions.
                  </div>
                </div>
                <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5">
                  <div className="text-xs uppercase font-semibold text-rose-400">R3 Crisis Override</div>
                  <div className="text-sm text-slate-300 mt-2">
                    Acute Liquidation / Flight to Safety (Regime 3) bypasses the 5-day lockup immediately to protect capital.
                  </div>
                </div>
                <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5">
                  <div className="text-xs uppercase font-semibold text-emerald-400">T+1 Execution & Friction</div>
                  <div className="text-sm text-slate-300 mt-2">
                    Signals evaluated at Date t Close execute at Date t+1 Close with institutional 15 bps one-way friction drag.
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: PORTFOLIOS */}
          {activeTab === "portfolios" && portfolio && (
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-6">
              <h2 className="text-lg font-semibold text-white">
                Holdout Performance & Portfolio Compounding (2025–2026)
              </h2>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                {portfolio.latest_holdings.map((h) => (
                  <div key={h.variant} className="bg-slate-950 border border-slate-800 rounded-lg p-4">
                    <div className="text-xs text-slate-400 font-semibold uppercase">Strategy {h.variant}</div>
                    <div className="text-xl font-bold text-white mt-1">
                      {parseFloat(h.net_nav).toFixed(4)} NAV
                    </div>
                    <div className="text-xs text-emerald-400 mt-1">
                      Holdout Cumulative: {(((parseFloat(h.net_nav) / 4.0) - 1.0) * 100).toFixed(1)}%
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* TAB 3: RELATIVE ROTATION GRAPH */}
          {activeTab === "rrg" && rrg && (
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
              <div className="flex justify-between items-center mb-6">
                <div>
                  <h2 className="text-lg font-semibold text-white">Relative Rotation Graph (RRG)</h2>
                  <p className="text-xs text-slate-400">Benchmark: NIFTY 50 &bull; 50-day RS-Ratio vs 10-day RS-Momentum</p>
                </div>
                <div className="text-xs font-mono text-slate-400">Session: {rrg.latest_date}</div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {Object.entries(rrg.sectors).map(([sector, data]) => {
                  const qColors: Record<string, string> = {
                    Leading: "text-emerald-400 bg-emerald-950/40 border-emerald-800",
                    Weakening: "text-amber-400 bg-amber-950/40 border-amber-800",
                    Lagging: "text-rose-400 bg-rose-950/40 border-rose-800",
                    Improving: "text-blue-400 bg-blue-950/40 border-blue-800",
                  };
                  return (
                    <div key={sector} className="bg-slate-950 border border-slate-800 rounded-lg p-4">
                      <div className="flex justify-between items-center">
                        <span className="font-semibold text-white">{sector}</span>
                        <span className={`text-xs px-2 py-0.5 rounded border font-semibold ${qColors[data.quadrant]}`}>
                          {data.quadrant}
                        </span>
                      </div>
                      <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                        <div className="bg-slate-900 p-2 rounded">
                          <span className="text-slate-400">RS-Ratio:</span>
                          <span className="font-mono text-white block mt-0.5">{data.current_ratio}</span>
                        </div>
                        <div className="bg-slate-900 p-2 rounded">
                          <span className="text-slate-400">RS-Momentum:</span>
                          <span className="font-mono text-white block mt-0.5">{data.current_momentum}</span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

