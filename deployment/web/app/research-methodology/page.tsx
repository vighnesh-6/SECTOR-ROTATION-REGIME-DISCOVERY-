"use client";

import React from "react";
import { TerminalPanel } from "@/components/ui/terminal-panel";
import { MetricTile } from "@/components/ui/metric-tile";
import { StatusBadge } from "@/components/ui/status-badge";
import { SectionHeader } from "@/components/ui/section-header";
import { DataTable, ColumnDef } from "@/components/ui/data-table";
import { BookOpen, ShieldCheck, CheckCircle2, FileText, Database } from "lucide-react";

interface ResearchPhase {
  phase: string;
  name: string;
  scope: string;
  deliverables: string;
  status: "COMPLETED" | "ACTIVE DEPLOYMENT";
}

const RESEARCH_PHASES: ResearchPhase[] = [
  {
    phase: "Phase 1",
    name: "Problem Formulation & Architecture",
    scope: "Mathematical framing of unsupervised market regime discovery across NSE sectors.",
    deliverables: "System specification, 8 index universe selection, data boundaries.",
    status: "COMPLETED",
  },
  {
    phase: "Phase 2",
    name: "Historical Data Ingestion & Audit",
    scope: "Ingestion and validation of 8 NSE index series from 2019-01-01 to 2026-09-18.",
    deliverables: "15,088 validated daily candles, calendar alignment, zero NaNs.",
    status: "COMPLETED",
  },
  {
    phase: "Phase 3",
    name: "Exploratory Data Analysis (EDA)",
    scope: "Stylized empirical facts: fat tails, volatility clustering, sector correlation shifts.",
    deliverables: "Stationarity tests, cross-asset correlation distributions.",
    status: "COMPLETED",
  },
  {
    phase: "Phase 4",
    name: "Feature Engineering & Stationarity",
    scope: "Construction of causal macro-features: logarithmic returns, Parkinson vol, VIX spread.",
    deliverables: "Multi-timeframe features with strict backward lookback.",
    status: "COMPLETED",
  },
  {
    phase: "Phase 5",
    name: "Feature Normalization & Scaling",
    scope: "Standardization preventing future information leakage via expanding-window estimators.",
    deliverables: "Robust z-score scaling matrices, causal normalization pipelines.",
    status: "COMPLETED",
  },
  {
    phase: "Phase 6",
    name: "Unsupervised Model Selection",
    scope: "Rigorous benchmarking of GMM, K-Means and Hidden Markov Models.",
    deliverables: "BIC/AIC scoring, temporal continuity, Gaussian HMM selection.",
    status: "COMPLETED",
  },
  {
    phase: "Phase 7",
    name: "Regime Characterization & Mapping",
    scope: "Economic mapping of 6 latent states to real-world Indian macro conditions.",
    deliverables: "Regime dictionary (R0 to R5), sector leadership attribution.",
    status: "COMPLETED",
  },
  {
    phase: "Phase 8",
    name: "Sector Rotation Rules Engine",
    scope: "Formulation of 4 strategy variants (1A, 1B, 2A, 2B), hysteresis, lockup.",
    deliverables: "Mathematical specification of allocation rules and cash floors.",
    status: "COMPLETED",
  },
  {
    phase: "Phase 9",
    name: "Causal Backtesting Engine",
    scope: "Event-driven backtesting engine with T+1 execution and 15 bps friction.",
    deliverables: "Vectorized causal simulator, turnover calculations, cash accounting.",
    status: "COMPLETED",
  },
  {
    phase: "Phase 10",
    name: "Comparative Strategy Evaluation",
    scope: "Holdout evaluation (2025–2026) against NIFTY 50 and Equal-Weight benchmarks.",
    deliverables: "Risk-adjusted performance metrics, drawdown curves, alpha verification.",
    status: "COMPLETED",
  },
  {
    phase: "Phase 11",
    name: "Statistical Significance Testing",
    scope: "Bootstrapping, White's Reality Check, and Monte Carlo permutation tests.",
    deliverables: "p-values < 0.01 for outperformance over passive benchmark.",
    status: "COMPLETED",
  },
  {
    phase: "Phase 12",
    name: "Parameter Sensitivity & Robustness",
    scope: "Perturbation scans of holding lockup (3–10d), friction (10–30 bps), lookback windows.",
    deliverables: "Robustness surface confirming strategy stability across parameter space.",
    status: "COMPLETED",
  },
  {
    phase: "Phase 13",
    name: "Event Study & Macro Resilience",
    scope: "Empirical CAAR evaluation across macro catalysts from 2019 through 2026.",
    deliverables: "Downside resilience proof during COVID-19, geopolitical and election shocks.",
    status: "COMPLETED",
  },
  {
    phase: "Phase 14 / D1",
    name: "Production Cloud Deployment",
    scope: "Daily automated EOD pipeline, Neon PostgreSQL schema, GitHub Actions workflow.",
    deliverables: "Autonomous daily catch-up, live state persistence, zero schema mutations.",
    status: "ACTIVE DEPLOYMENT",
  },
];

export default function ResearchMethodologyPage() {
  const columns: ColumnDef<ResearchPhase>[] = [
    {
      key: "phase",
      header: "Phase",
      width: "100px",
      render: (row) => (
        <span className="font-mono font-bold text-terminal-primary">{row.phase}</span>
      ),
    },
    {
      key: "name",
      header: "Research Milestone",
      render: (row) => (
        <div>
          <span className="font-bold text-terminal-primary block">{row.name}</span>
          <span className="text-[11px] text-terminal-muted">{row.scope}</span>
        </div>
      ),
    },
    {
      key: "deliverables",
      header: "Core Deliverables & Validation",
      render: (row) => (
        <span className="text-xs text-terminal-muted">{row.deliverables}</span>
      ),
    },
    {
      key: "status",
      header: "Verification",
      align: "right",
      render: (row) => (
        <StatusBadge
          label={row.status}
          variant={row.status === "ACTIVE DEPLOYMENT" ? "success" : "neutral"}
          size="sm"
        />
      ),
    },
  ];

  return (
    <div className="space-y-5">
      <SectionHeader
        title="Institutional Research Methodology & Engineering Lineage"
        description="Comprehensive 14-Phase Quantitative Architecture &bull; Unsupervised Regime Discovery &bull; National Stock Exchange of India"
        badge={
          <StatusBadge
            label="FULL REPRODUCIBILITY"
            variant="success"
          />
        }
      />

      {/* KPI Tiles */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3.5">
        <MetricTile
          label="Research Phases"
          value="14 Phases"
          delta="100% Fully Completed"
          deltaType="positive"
          subtitle="Systematic Development Pipeline"
        />
        <MetricTile
          label="In-Sample Historical Scope"
          value="2019–2024"
          delta="15,088 Verified Candles"
          deltaType="neutral"
          subtitle="Unsupervised State Calibration"
        />
        <MetricTile
          label="Holdout Evaluation Period"
          value="2025–2026"
          delta="Out-of-Sample Compounding"
          deltaType="positive"
          subtitle="Zero Contamination Guarantee"
        />
        <MetricTile
          label="Universe Specification"
          value="8 NSE Indices"
          delta="NIFTY 50 + 6 Sectors + VIX"
          deltaType="neutral"
          subtitle="Strict Index-Level Universe"
        />
      </div>

      {/* 14 Phases Execution Log */}
      <TerminalPanel
        title="Complete Quantitative Research Lifecycle (Phases 1 through 14)"
        subtitle="End-to-end scientific methodology preserving mathematical causality at every stage"
      >
        <DataTable
          columns={columns}
          data={RESEARCH_PHASES}
          keyField="phase"
          zebra
        />
      </TerminalPanel>

      {/* Scientific Principles & Integrity Guarantees */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5">
        <div className="p-3.5 rounded-sm border border-terminal-border bg-terminal-panel">
          <div className="flex items-center gap-2 mb-1.5">
            <ShieldCheck className="w-4 h-4 text-emerald-500 stroke-[1.5]" />
            <h4 className="font-mono text-xs font-bold uppercase text-terminal-primary">
              Strict Causal Inference
            </h4>
          </div>
          <p className="text-xs text-terminal-muted leading-relaxed">
            All feature engineering, scaling parameters, HMM state probabilities, and portfolio
            allocations are calculated using information available strictly on or before Date t Close.
            Future returns and retrospective HMM smoothing are mathematically forbidden.
          </p>
        </div>

        <div className="p-3.5 rounded-sm border border-terminal-border bg-terminal-panel">
          <div className="flex items-center gap-2 mb-1.5">
            <Database className="w-4 h-4 text-terminal-muted stroke-[1.5]" />
            <h4 className="font-mono text-xs font-bold uppercase text-terminal-primary">
              Frozen Research Isolation
            </h4>
          </div>
          <p className="text-xs text-terminal-muted leading-relaxed">
            The historical research codebase (`src/`, `data/`, `results/`, `reports/`) and original
            15,088 baseline candles are completely frozen and immutable. Deployment pipelines operate
            independently without ever mutating historical research artifacts.
          </p>
        </div>

        <div className="p-3.5 rounded-sm border border-terminal-border bg-terminal-panel">
          <div className="flex items-center gap-2 mb-1.5">
            <FileText className="w-4 h-4 text-amber-500 stroke-[1.5]" />
            <h4 className="font-mono text-xs font-bold uppercase text-terminal-primary">
              Real-World Execution Drag
            </h4>
          </div>
          <p className="text-xs text-terminal-muted leading-relaxed">
            Every rebalance incurred by the strategy accounts for institutional transaction costs
            (15 bps one-way) and next-day-close (T+1) execution timing. No theoretical zero-friction
            assumptions are permitted in performance reporting.
          </p>
        </div>
      </div>
    </div>
  );
}

