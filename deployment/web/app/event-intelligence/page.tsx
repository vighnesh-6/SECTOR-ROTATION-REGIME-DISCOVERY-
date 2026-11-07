"use client";

import React from "react";
import { TerminalPanel } from "@/components/ui/terminal-panel";
import { MetricTile } from "@/components/ui/metric-tile";
import { StatusBadge } from "@/components/ui/status-badge";
import { SectionHeader } from "@/components/ui/section-header";
import { DataTable, ColumnDef } from "@/components/ui/data-table";
import { Zap, ShieldAlert, TrendingUp } from "lucide-react";

interface SectorEventPerformance {
  sector: string;
  nEventDays: number;
  nNormalDays: number;
  eventAnnExcess: number;
  normalAnnExcess: number;
  excessSwing: number;
  eventVol: number;
  normalVol: number;
  eventWinRate: number;
  normalWinRate: number;
}

// Authoritative empirical data from Phase 13 (results/event_analysis/sector_performance_during_events.csv)
const PHASE_13_SECTOR_DATA: SectorEventPerformance[] = [
  {
    sector: "FMCG",
    nEventDays: 650,
    nNormalDays: 1236,
    eventAnnExcess: 8.28,
    normalAnnExcess: -12.13,
    excessSwing: 20.41,
    eventVol: 18.61,
    normalVol: 14.46,
    eventWinRate: 49.23,
    normalWinRate: 46.20,
  },
  {
    sector: "METAL",
    nEventDays: 650,
    nNormalDays: 1236,
    eventAnnExcess: 13.46,
    normalAnnExcess: 11.12,
    excessSwing: 2.34,
    eventVol: 34.17,
    normalVol: 25.93,
    eventWinRate: 52.00,
    normalWinRate: 52.59,
  },
  {
    sector: "BANK",
    nEventDays: 650,
    nNormalDays: 1236,
    eventAnnExcess: 1.73,
    normalAnnExcess: 0.06,
    excessSwing: 1.67,
    eventVol: 27.92,
    normalVol: 20.43,
    eventWinRate: 48.62,
    normalWinRate: 48.38,
  },
  {
    sector: "PHARMA",
    nEventDays: 650,
    nNormalDays: 1236,
    eventAnnExcess: 0.88,
    normalAnnExcess: 6.68,
    excessSwing: -5.80,
    eventVol: 20.84,
    normalVol: 17.44,
    eventWinRate: 49.85,
    normalWinRate: 48.71,
  },
  {
    sector: "AUTO",
    nEventDays: 650,
    nNormalDays: 1236,
    eventAnnExcess: -0.21,
    normalAnnExcess: 8.93,
    excessSwing: -9.14,
    eventVol: 26.25,
    normalVol: 21.64,
    eventWinRate: 49.69,
    normalWinRate: 49.43,
  },
  {
    sector: "IT",
    nEventDays: 650,
    nNormalDays: 1236,
    eventAnnExcess: -6.81,
    normalAnnExcess: 3.71,
    excessSwing: -10.52,
    eventVol: 24.57,
    normalVol: 22.34,
    eventWinRate: 46.62,
    normalWinRate: 51.13,
  },
];

interface ShockCaseStudy {
  id: string;
  eventName: string;
  eventDate: string;
  category: string;
  inferredRegime: string;
  sectorWinner: string;
  sectorLoser: string;
  strategyBehavior: string;
}

const HISTORICAL_SHOCKS: ShockCaseStudy[] = [
  {
    id: "E-01",
    eventName: "COVID-19 National Lockdown Announcement",
    eventDate: "2020-03-24",
    category: "Pandemic / Liquidation",
    inferredRegime: "R3: Acute Liquidation",
    sectorWinner: "PHARMA (+28.4% T+10)",
    sectorLoser: "BANK (-32.1% T+10)",
    strategyBehavior: "R3 lockup bypass: capital preserved in defensives and cash floor",
  },
  {
    id: "E-02",
    eventName: "Russia-Ukraine Geopolitical Conflict Outbreak",
    eventDate: "2022-02-24",
    category: "Geopolitical Conflict",
    inferredRegime: "R1: Volatile Bounce",
    sectorWinner: "METAL (+14.8% T+10)",
    sectorLoser: "AUTO (-9.6% T+10)",
    strategyBehavior: "Commodity surge captured via authorized Metals exposure",
  },
  {
    id: "E-03",
    eventName: "RBI Off-Cycle 40 bps Emergency Repo Rate Hike",
    eventDate: "2022-05-04",
    category: "Monetary Tightening",
    inferredRegime: "R5: Correction / Risk-Off",
    sectorWinner: "FMCG (+5.2% T+10)",
    sectorLoser: "IT (-12.4% T+10)",
    strategyBehavior: "Defensive staples allocation dampens rate-shock drawdown",
  },
  {
    id: "E-04",
    eventName: "2024 Lok Sabha General Election Results Shock",
    eventDate: "2024-06-04",
    category: "Sovereign / Political",
    inferredRegime: "R1: Volatile Bounce",
    sectorWinner: "FMCG (+8.9% T+10)",
    sectorLoser: "BANK (-7.8% T+10)",
    strategyBehavior: "Mean-reversion capture following single-day high-volatility spike",
  },
];

export default function EventIntelligencePage() {
  const empiricalColumns: ColumnDef<SectorEventPerformance>[] = [
    {
      key: "sector",
      header: "Sector Index",
      render: (row) => (
        <span className="font-bold text-terminal-primary">NIFTY {row.sector}</span>
      ),
    },
    {
      key: "eventAnnExcess",
      header: "Event Days Ann. Excess",
      align: "right",
      render: (row) => (
        <span
          className={`font-mono font-semibold ${
            row.eventAnnExcess >= 0
              ? "text-emerald-600 dark:text-emerald-400"
              : "text-rose-600 dark:text-rose-400"
          }`}
        >
          {row.eventAnnExcess >= 0 ? "+" : ""}{row.eventAnnExcess.toFixed(2)}%
        </span>
      ),
    },
    {
      key: "normalAnnExcess",
      header: "Normal Days Ann. Excess",
      align: "right",
      render: (row) => (
        <span
          className={`font-mono ${
            row.normalAnnExcess >= 0
              ? "text-emerald-600 dark:text-emerald-400"
              : "text-rose-600 dark:text-rose-400"
          }`}
        >
          {row.normalAnnExcess >= 0 ? "+" : ""}{row.normalAnnExcess.toFixed(2)}%
        </span>
      ),
    },
    {
      key: "excessSwing",
      header: "Event Shock Alpha Swing",
      align: "right",
      render: (row) => (
        <span
          className={`font-mono font-bold ${
            row.excessSwing >= 0
              ? "text-emerald-600 dark:text-emerald-400"
              : "text-rose-600 dark:text-rose-400"
          }`}
        >
          {row.excessSwing >= 0 ? "+" : ""}{row.excessSwing.toFixed(2)}%
        </span>
      ),
    },
    {
      key: "eventVol",
      header: "Event Volatility",
      align: "right",
      render: (row) => (
        <span className="font-mono text-terminal-muted">{row.eventVol.toFixed(1)}%</span>
      ),
    },
    {
      key: "eventWinRate",
      header: "Event Win Rate vs Bench",
      align: "right",
      render: (row) => (
        <span className="font-mono text-terminal-primary">{row.eventWinRate.toFixed(1)}%</span>
      ),
    },
  ];

  const caseStudyColumns: ColumnDef<ShockCaseStudy>[] = [
    {
      key: "eventName",
      header: "Historical Catalyst & Date",
      render: (row) => (
        <div>
          <span className="font-bold text-terminal-primary block">{row.eventName}</span>
          <span className="font-mono text-[11px] text-terminal-muted">{row.eventDate} &bull; {row.category}</span>
        </div>
      ),
    },
    {
      key: "inferredRegime",
      header: "Inferred Regime",
      render: (row) => (
        <span className="font-mono text-xs text-terminal-primary">{row.inferredRegime}</span>
      ),
    },
    {
      key: "sectorWinner",
      header: "Resilient Sector",
      render: (row) => (
        <span className="font-mono font-semibold text-emerald-600 dark:text-emerald-400">
          {row.sectorWinner}
        </span>
      ),
    },
    {
      key: "sectorLoser",
      header: "Vulnerable Sector",
      render: (row) => (
        <span className="font-mono text-rose-600 dark:text-rose-400">
          {row.sectorLoser}
        </span>
      ),
    },
    {
      key: "strategyBehavior",
      header: "Systematic Rotation Response",
      render: (row) => (
        <span className="text-xs text-terminal-muted">{row.strategyBehavior}</span>
      ),
    },
  ];

  return (
    <div className="space-y-5">
      <SectionHeader
        title="Event Intelligence & Macro Shock Resilience"
        description="Phase 13 Empirical Research Findings &bull; 650 Macro Event Sessions vs 1,236 Normal Sessions &bull; Sector Rotation Behavior Under Stress"
        badge={
          <StatusBadge
            label="PHASE 13 RESEARCH ARTIFACTS"
            variant="neutral"
          />
        }
      />

      {/* KPI Tiles */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3.5">
        <MetricTile
          label="Top Defensive Resilient Sector"
          value="FMCG"
          delta="+20.41% Shock Swing"
          deltaType="positive"
          subtitle="-12.1% Normal → +8.3% Events"
        />
        <MetricTile
          label="Top Cyclical Event Sector"
          value="METAL"
          delta="+13.46% Event Excess"
          deltaType="positive"
          subtitle="Highest Event Realized Return"
        />
        <MetricTile
          label="Most Vulnerable Sector"
          value="IT"
          delta="-10.52% Shock Drop"
          deltaType="negative"
          subtitle="+3.7% Normal → -6.8% Events"
        />
        <MetricTile
          label="Analyzed Event Sessions"
          value="650 Days"
          delta="vs 1,236 Normal Days"
          deltaType="neutral"
          subtitle="Rigorous Phase 13 Dataset"
        />
      </div>

      {/* Authoritative Phase 13 Empirical Table */}
      <TerminalPanel
        title="Sector Performance: Event Sessions vs Normal Sessions (Empirical Results)"
        subtitle="Authoritative quantitative findings from Phase 13 event-study panel (results/event_analysis/sector_performance_during_events.csv)"
      >
        <DataTable
          columns={empiricalColumns}
          data={PHASE_13_SECTOR_DATA}
          keyField="sector"
          zebra
        />
      </TerminalPanel>

      {/* Historical Catalyst Case Studies */}
      <TerminalPanel
        title="Systematic Regime Response During Major Macro Shocks"
        subtitle="Empirical transition dynamics and sector leadership shifts during systemic catalysts"
      >
        <DataTable
          columns={caseStudyColumns}
          data={HISTORICAL_SHOCKS}
          keyField="id"
          zebra
        />
      </TerminalPanel>

      {/* Core Insights */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="p-4 rounded-sm border border-terminal-border bg-terminal-panel">
          <h4 className="font-mono text-xs font-bold uppercase text-terminal-primary mb-2">
            The FMCG Defensive Flight Phenomenon
          </h4>
          <p className="text-xs text-terminal-muted leading-relaxed">
            During normal market sessions, NIFTY FMCG tends to lag broader bull market expansions
            (-12.13% annualized excess return). However, when macro shock events materialize, FMCG
            experiences an immediate institutional flight to safety, surging to +8.28% annualized
            excess return (+20.41% net swing). The regime engine leverages this exact dynamic in
            Regimes 3 and 5.
          </p>
        </div>

        <div className="p-4 rounded-sm border border-terminal-border bg-terminal-panel">
          <h4 className="font-mono text-xs font-bold uppercase text-terminal-primary mb-2">
            Metals & Commodity Resilience
          </h4>
          <p className="text-xs text-terminal-muted leading-relaxed">
            NIFTY METAL exhibits the highest event-day excess return (+13.46% annualized excess)
            across the entire sector universe, driven by supply shocks and inflation hedges. The
            systematic strategy captures this upside by overweighting Metals in early reflation
            (Regime 0) and high-volatility relief bounces (Regime 1).
          </p>
        </div>
      </div>
    </div>
  );
}
