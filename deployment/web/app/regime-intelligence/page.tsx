"use client";

import React, { useEffect, useState } from "react";
import { TerminalPanel } from "@/components/ui/terminal-panel";
import { MetricTile } from "@/components/ui/metric-tile";
import { StatusBadge } from "@/components/ui/status-badge";
import { SectionHeader } from "@/components/ui/section-header";
import { DataTable, ColumnDef } from "@/components/ui/data-table";
import { LoadingTableSkeleton, LoadingMetricSkeleton } from "@/components/ui/loading-state";
import { RefreshCw, Activity, Cpu, Layers } from "lucide-react";

interface RegimeProfile {
  id: number;
  name: string;
  economicMeaning: string;
  expectedDuration: string;
  vixProfile: string;
  authorizedSectors: string[];
  templateACash: string;
  templateBCash: string;
}

const REGIME_PROFILES: RegimeProfile[] = [
  {
    id: 0,
    name: "Cyclical Reflation Rally",
    economicMeaning: "Early bull cycle acceleration, strong industrial and high-beta participation.",
    expectedDuration: "14.2 sessions",
    vixProfile: "Declining / Moderate (13–16)",
    authorizedSectors: ["IT", "METAL"],
    templateACash: "0.0%",
    templateBCash: "0.0%",
  },
  {
    id: 1,
    name: "High-Volatility Bounce",
    economicMeaning: "Post-drawdown relief rally with violent sector rotation and wide intra-day swings.",
    expectedDuration: "8.6 sessions",
    vixProfile: "Elevated / Mean-reverting (18–24)",
    authorizedSectors: ["AUTO", "METAL"],
    templateACash: "0.0%",
    templateBCash: "20.0%",
  },
  {
    id: 2,
    name: "Low-Volatility Consolidation",
    economicMeaning: "Sideways range-bound base building, defensive growth leadership.",
    expectedDuration: "18.4 sessions",
    vixProfile: "Low / Suppressed (11–13)",
    authorizedSectors: ["IT", "PHARMA"],
    templateACash: "0.0%",
    templateBCash: "0.0%",
  },
  {
    id: 3,
    name: "Acute Liquidation / Crisis",
    economicMeaning: "Severe systemic shock, panic selling across equities, rapid flight to liquidity.",
    expectedDuration: "6.1 sessions",
    vixProfile: "Spiking (> 25, high kurtosis)",
    authorizedSectors: ["PHARMA", "FMCG"],
    templateACash: "0.0%",
    templateBCash: "50.0%",
  },
  {
    id: 4,
    name: "Steady Expansion",
    economicMeaning: "Broad-based institutional rally with low realized dispersion.",
    expectedDuration: "22.8 sessions",
    vixProfile: "Steady Low (12–15)",
    authorizedSectors: ["METAL", "AUTO"],
    templateACash: "0.0%",
    templateBCash: "0.0%",
  },
  {
    id: 5,
    name: "Correction / Risk-Off Digestion",
    economicMeaning: "Market breadth deterioration, defensive rotation into staples and healthcare.",
    expectedDuration: "11.5 sessions",
    vixProfile: "Rising / Choppy (16–20)",
    authorizedSectors: ["PHARMA", "FMCG"],
    templateACash: "0.0%",
    templateBCash: "30.0%",
  },
];

export default function RegimeIntelligencePage() {
  const [activeRegimeId, setActiveRegimeId] = useState<number>(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/v1/regime/latest")
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data && data.accepted_regime) {
          setActiveRegimeId(data.accepted_regime.id);
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const columns: ColumnDef<RegimeProfile>[] = [
    {
      key: "id",
      header: "Regime",
      width: "90px",
      render: (row) => (
        <div className="flex items-center gap-1.5">
          <StatusBadge
            label={`R${row.id}`}
            variant="regime"
            regimeId={row.id}
            size="sm"
          />
          {row.id === activeRegimeId && (
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-ping" />
          )}
        </div>
      ),
    },
    {
      key: "name",
      header: "Economic Characterization",
      render: (row) => (
        <div>
          <span className="font-bold text-terminal-primary block">{row.name}</span>
          <span className="text-[11px] text-terminal-muted">{row.economicMeaning}</span>
        </div>
      ),
    },
    {
      key: "authorizedSectors",
      header: "Authorized Sectors",
      render: (row) => (
        <div className="flex gap-1.5">
          {row.authorizedSectors.map((s) => (
            <span
              key={s}
              className="px-1.5 py-0.5 rounded-sm bg-terminal-secondary text-[11px] font-mono border border-terminal-border text-terminal-primary font-semibold"
            >
              {s}
            </span>
          ))}
        </div>
      ),
    },
    {
      key: "vixProfile",
      header: "INDIA VIX Regime",
      render: (row) => (
        <span className="font-mono text-xs text-terminal-primary">{row.vixProfile}</span>
      ),
    },
    {
      key: "expectedDuration",
      header: "Mean Duration",
      align: "right",
      render: (row) => (
        <span className="font-mono text-terminal-primary">{row.expectedDuration}</span>
      ),
    },
    {
      key: "templateBCash",
      header: "Defensive Cash (Tpl B)",
      align: "right",
      render: (row) => (
        <span className="font-mono font-semibold text-amber-600 dark:text-amber-400">
          {row.templateBCash}
        </span>
      ),
    },
  ];

  return (
    <div className="space-y-5">
      <SectionHeader
        title="Gaussian Hidden Markov Model (HMM) Regime Intelligence"
        description="6-State Latent Macro Dynamics &bull; Causal Online Filtering &bull; Hysteresis Guardrails &bull; Crisis Fast-Path"
        badge={
          <StatusBadge
            label="UNSUPERVISED CAUSAL INFERENCE"
            variant="neutral"
          />
        }
      />

      {/* KPI Tiles */}
      {loading ? (
        <LoadingMetricSkeleton count={4} />
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3.5">
          <MetricTile
            label="Gaussian States"
            value="6 States"
            delta="Akaike & Bayesian Criteria"
            deltaType="neutral"
            subtitle="Identified from In-Sample Phase"
          />
          <MetricTile
            label="Acceptance Threshold"
            value="P ≥ 0.50"
            delta="Confidence Floor"
            deltaType="positive"
            subtitle="Prevents Churn on State Uncertainty"
          />
          <MetricTile
            label="Holding Lockup"
            value="5 Days"
            delta="Turnover Reduction"
            deltaType="neutral"
            subtitle="Non-Crisis Persistence"
          />
          <MetricTile
            label="Crisis Bypass (R3)"
            value="0 Sessions"
            delta="Instant Execution"
            deltaType="positive"
            subtitle="Overrules 5-Day Lockup"
          />
        </div>
      )}

      {/* Regime Characterization Table */}
      <TerminalPanel
        title="Institutional Regime Taxonomy & Authorized Allocations"
        subtitle="Complete catalog of 6 economic states discovered from NSE market data"
      >
        <DataTable
          columns={columns}
          data={REGIME_PROFILES}
          keyField="id"
          zebra
        />
      </TerminalPanel>

      {/* Mathematical & Causal Guarantees */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="p-4 rounded-sm border border-terminal-border bg-terminal-panel">
          <h4 className="font-mono text-xs font-bold uppercase text-terminal-primary mb-2">
            Forward Filtering Formulation (Zero Lookahead)
          </h4>
          <p className="text-xs text-terminal-muted leading-relaxed mb-3">
            State inference is executed strictly online using only the causal forward filter.
            Smoothing algorithms (which use future data) are mathematically excluded from the
            production inference path:
          </p>
          <div className="p-2.5 rounded-sm bg-terminal-secondary font-mono text-xs text-terminal-primary border border-terminal-border overflow-x-auto">
            P(S_t | Y_{`1:t`}) ∝ P(Y_t | S_t) &bull; ∑ [ P(S_t | S_{`t-1`}) &bull; P(S_{`t-1`} | Y_{`1:t-1`}) ]
          </div>
        </div>

        <div className="p-4 rounded-sm border border-terminal-border bg-terminal-panel">
          <h4 className="font-mono text-xs font-bold uppercase text-terminal-primary mb-2">
            Hysteresis & Incumbent Persistence Rule
          </h4>
          <p className="text-xs text-terminal-muted leading-relaxed">
            If the maximum posterior probability falls below the confidence threshold
            (max P &lt; 0.50), the system rejects the candidate transition and preserves the
            incumbent regime. This prevents spurious portfolio rebalancing during low-conviction
            market noise.
          </p>
        </div>
      </div>
    </div>
  );
}

