"use client";

import React, { useEffect, useState } from "react";
import { TerminalPanel } from "@/components/ui/terminal-panel";
import { MetricTile } from "@/components/ui/metric-tile";
import { StatusBadge } from "@/components/ui/status-badge";
import { SectionHeader } from "@/components/ui/section-header";
import { DataTable, ColumnDef } from "@/components/ui/data-table";
import { LoadingMetricSkeleton, LoadingTableSkeleton } from "@/components/ui/loading-state";
import { EmptyState } from "@/components/ui/empty-state";
import { RefreshCw, Compass } from "lucide-react";

interface SectorRRG {
  current_ratio: number;
  current_momentum: number;
  quadrant: "Leading" | "Weakening" | "Lagging" | "Improving";
  trail: Array<{ date: string; ratio: number; momentum: number }>;
}

interface RRGResponse {
  benchmark: string;
  latest_date: string;
  trail_length: number;
  sectors: Record<string, SectorRRG>;
}

const SECTOR_COLORS: Record<string, string> = {
  AUTO: "#D97706",
  BANK: "#2563EB",
  FMCG: "#059669",
  IT: "#0891B2",
  METAL: "#64748B",
  PHARMA: "#9333EA",
};

export default function SectorRotationPage() {
  const [data, setData] = useState<RRGResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hoveredSector, setHoveredSector] = useState<string | null>(null);

  const fetchRRG = async () => {
    try {
      setError(null);
      const res = await fetch("/api/v1/rrg?trail=5");
      if (!res.ok) throw new Error(`RRG API error: HTTP ${res.status}`);
      const json = await res.json();
      setData(json);
    } catch (e: any) {
      console.error("Failed to load RRG data:", e);
      setError(e.message || "Failed to load Relative Rotation data.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchRRG();
  }, []);

  const getQuadrantBadge = (quadrant: string) => {
    switch (quadrant) {
      case "Leading":
        return <StatusBadge label="LEADING" variant="success" />;
      case "Weakening":
        return <StatusBadge label="WEAKENING" variant="warning" />;
      case "Lagging":
        return <StatusBadge label="LAGGING" variant="danger" />;
      case "Improving":
        return <StatusBadge label="IMPROVING" variant="neutral" />;
      default:
        return <StatusBadge label={quadrant} variant="neutral" />;
    }
  };

  const columns: ColumnDef<{ sector: string; data: SectorRRG }>[] = [
    {
      key: "sector",
      header: "Sector Index",
      render: (row) => (
        <div className="flex items-center gap-2">
          <span
            className="w-2.5 h-2.5 rounded-full flex-shrink-0"
            style={{ backgroundColor: SECTOR_COLORS[row.sector] || "#94A3B8" }}
          />
          <span className="font-bold text-terminal-primary">
            NIFTY {row.sector}
          </span>
        </div>
      ),
    },
    {
      key: "quadrant",
      header: "RRG Quadrant",
      align: "center",
      render: (row) => getQuadrantBadge(row.data.quadrant),
    },
    {
      key: "rs_ratio",
      header: "RS-Ratio (50-Day)",
      align: "right",
      render: (row) => (
        <span
          className={`font-mono font-semibold ${
            row.data.current_ratio >= 100
              ? "text-emerald-600 dark:text-emerald-400"
              : "text-rose-600 dark:text-rose-400"
          }`}
        >
          {row.data.current_ratio.toFixed(2)}
        </span>
      ),
    },
    {
      key: "rs_momentum",
      header: "RS-Momentum (10-Day)",
      align: "right",
      render: (row) => (
        <span
          className={`font-mono font-semibold ${
            row.data.current_momentum >= 100
              ? "text-emerald-600 dark:text-emerald-400"
              : "text-rose-600 dark:text-rose-400"
          }`}
        >
          {row.data.current_momentum.toFixed(2)}
        </span>
      ),
    },
    {
      key: "interpretation",
      header: "Rotational State",
      render: (row) => {
        if (row.data.quadrant === "Leading") return "Outperforming benchmark with positive momentum";
        if (row.data.quadrant === "Weakening") return "Outperforming benchmark but momentum decelerating";
        if (row.data.quadrant === "Lagging") return "Underperforming benchmark with negative momentum";
        return "Underperforming benchmark but momentum rebounding";
      },
    },
  ];

  const tableData = data?.sectors
    ? Object.entries(data.sectors).map(([sector, sData]) => ({
        sector,
        data: sData,
      }))
    : [];

  const leadingCount = tableData.filter((s) => s.data.quadrant === "Leading").length;
  const improvingCount = tableData.filter((s) => s.data.quadrant === "Improving").length;
  const weakeningCount = tableData.filter((s) => s.data.quadrant === "Weakening").length;
  const laggingCount = tableData.filter((s) => s.data.quadrant === "Lagging").length;

  // Coordinate scaling for 500x500 SVG canvas
  // X range: 94 to 106 (center 100)
  // Y range: 94 to 106 (center 100)
  const mapCoord = (ratio: number, momentum: number) => {
    const minVal = 95;
    const maxVal = 105;
    const size = 500;
    const padding = 40;
    const innerSize = size - 2 * padding;

    const x = padding + ((ratio - minVal) / (maxVal - minVal)) * innerSize;
    // Invert Y because SVG coordinates increase downwards
    const y = size - (padding + ((momentum - minVal) / (maxVal - minVal)) * innerSize);

    return {
      x: Math.max(padding, Math.min(size - padding, x)),
      y: Math.max(padding, Math.min(size - padding, y)),
    };
  };

  const centerCoord = mapCoord(100, 100);

  return (
    <div className="space-y-5">
      <SectionHeader
        title="Sector Rotation Intelligence & Relative Rotation Graph (RRG)"
        description="JdK Relative Rotation Graph &bull; Benchmark: NIFTY 50 &bull; 50-Day Normalized Relative Strength vs 10-Day Momentum"
        badge={
          <StatusBadge
            label="RELATIVE STRENGTH MODEL"
            variant="neutral"
          />
        }
        action={
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-mono text-terminal-muted hidden sm:inline">
              Session: {data?.latest_date || "2026-11-06"}
            </span>
            <button
              onClick={() => {
                setRefreshing(true);
                fetchRRG();
              }}
              disabled={refreshing}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-mono rounded-sm border border-terminal-border bg-terminal-secondary hover:bg-terminal-border/40 text-terminal-primary transition-colors disabled:opacity-50"
            >
              <RefreshCw className={`w-3 h-3 ${refreshing ? "animate-spin" : ""}`} />
              <span>{refreshing ? "CALCULATING" : "SYNC"}</span>
            </button>
          </div>
        }
      />

      {/* KPI Tiles */}
      {loading ? (
        <LoadingMetricSkeleton count={4} />
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3.5">
          <MetricTile
            label="Leading Sectors"
            value={String(leadingCount)}
            delta="Outperforming & Accelerating"
            deltaType="positive"
            subtitle="RS-Ratio ≥ 100, RS-Mom ≥ 100"
          />
          <MetricTile
            label="Improving Sectors"
            value={String(improvingCount)}
            delta="Rebound Candidates"
            deltaType="neutral"
            subtitle="RS-Ratio < 100, RS-Mom ≥ 100"
          />
          <MetricTile
            label="Weakening Sectors"
            value={String(weakeningCount)}
            delta="Decelerating Outperformers"
            deltaType="warning"
            subtitle="RS-Ratio ≥ 100, RS-Mom < 100"
          />
          <MetricTile
            label="Lagging Sectors"
            value={String(laggingCount)}
            delta="Underperforming Drag"
            deltaType="negative"
            subtitle="RS-Ratio < 100, RS-Mom < 100"
          />
        </div>
      )}

      {/* Primary RRG Visualizer & Quadrant Matrix */}
      {loading ? (
        <LoadingTableSkeleton rows={6} columns={5} />
      ) : error ? (
        <EmptyState
          title="RRG Telemetry Error"
          description={error}
          action={
            <button
              onClick={fetchRRG}
              className="px-3 py-1.5 text-xs font-mono rounded-sm border border-terminal-border bg-terminal-panel text-terminal-primary"
            >
              Retry
            </button>
          }
        />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
          {/* Interactive RRG Scatter & Trajectory Canvas */}
          <div className="lg:col-span-6 flex flex-col">
            <TerminalPanel
              title="Relative Rotation Graph (2D Vector Space)"
              subtitle="5-Session Trailing Vector against NIFTY 50 (100, 100)"
              className="flex-1"
            >
              <div className="relative w-full aspect-square max-w-[500px] mx-auto bg-terminal-secondary/30 rounded-sm border border-terminal-border/80 overflow-hidden select-none">
                <svg
                  viewBox="0 0 500 500"
                  className="w-full h-full"
                >
                  {/* Quadrant Background Tints */}
                  {/* Top-Right: Leading */}
                  <rect
                    x={centerCoord.x}
                    y={40}
                    width={460 - centerCoord.x}
                    height={centerCoord.y - 40}
                    className="fill-emerald-500/5"
                  />
                  {/* Bottom-Right: Weakening */}
                  <rect
                    x={centerCoord.x}
                    y={centerCoord.y}
                    width={460 - centerCoord.x}
                    height={460 - centerCoord.y}
                    className="fill-amber-500/5"
                  />
                  {/* Bottom-Left: Lagging */}
                  <rect
                    x={40}
                    y={centerCoord.y}
                    width={centerCoord.x - 40}
                    height={460 - centerCoord.y}
                    className="fill-rose-500/5"
                  />
                  {/* Top-Left: Improving */}
                  <rect
                    x={40}
                    y={40}
                    width={centerCoord.x - 40}
                    height={centerCoord.y - 40}
                    className="fill-blue-500/5"
                  />

                  {/* Quadrant Corner Labels */}
                  <text x="440" y="55" textAnchor="end" className="text-[10px] font-mono font-bold fill-emerald-600/70 dark:fill-emerald-400/70">
                    LEADING (↗)
                  </text>
                  <text x="440" y="450" textAnchor="end" className="text-[10px] font-mono font-bold fill-amber-600/70 dark:fill-amber-400/70">
                    WEAKENING (↘)
                  </text>
                  <text x="50" y="450" textAnchor="start" className="text-[10px] font-mono font-bold fill-rose-600/70 dark:fill-rose-400/70">
                    LAGGING (↙)
                  </text>
                  <text x="50" y="55" textAnchor="start" className="text-[10px] font-mono font-bold fill-blue-600/70 dark:fill-blue-400/70">
                    IMPROVING (↖)
                  </text>

                  {/* Crosshair Center Lines */}
                  <line
                    x1={centerCoord.x}
                    y1="40"
                    x2={centerCoord.x}
                    y2="460"
                    className="stroke-terminal-border stroke-[1.5] stroke-dashed"
                  />
                  <line
                    x1="40"
                    y1={centerCoord.y}
                    x2="460"
                    y2={centerCoord.y}
                    className="stroke-terminal-border stroke-[1.5] stroke-dashed"
                  />

                  {/* Benchmark Center Point */}
                  <circle
                    cx={centerCoord.x}
                    cy={centerCoord.y}
                    r="5"
                    className="fill-terminal-primary"
                  />
                  <text
                    x={centerCoord.x + 8}
                    y={centerCoord.y - 8}
                    className="text-[10px] font-mono font-bold fill-terminal-primary"
                  >
                    NIFTY 50 (100, 100)
                  </text>

                  {/* Sector Trails and Nodes */}
                  {tableData.map(({ sector, data: sData }) => {
                    const color = SECTOR_COLORS[sector] || "#94A3B8";
                    const isHovered = hoveredSector === sector;
                    const trailPoints = (sData.trail || []).map((t) => mapCoord(t.ratio, t.momentum));
                    const currentPos = mapCoord(sData.current_ratio, sData.current_momentum);

                    // Polyline points string
                    const allPoints = [...trailPoints, currentPos];
                    const pointsStr = allPoints.map((p) => `${p.x},${p.y}`).join(" ");

                    return (
                      <g
                        key={sector}
                        onMouseEnter={() => setHoveredSector(sector)}
                        onMouseLeave={() => setHoveredSector(null)}
                        className="cursor-pointer transition-opacity"
                        opacity={hoveredSector && !isHovered ? 0.3 : 1}
                      >
                        {/* Connecting Trailing Line */}
                        {allPoints.length > 1 && (
                          <polyline
                            points={pointsStr}
                            fill="none"
                            stroke={color}
                            strokeWidth={isHovered ? "2.5" : "1.5"}
                            strokeDasharray={isHovered ? undefined : "3 3"}
                          />
                        )}

                        {/* Historical Trail Dots */}
                        {trailPoints.map((tp, idx) => (
                          <circle
                            key={idx}
                            cx={tp.x}
                            cy={tp.y}
                            r={1.5 + (idx / trailPoints.length) * 2}
                            fill={color}
                            opacity={0.3 + (idx / trailPoints.length) * 0.5}
                          />
                        ))}

                        {/* Current Head Node */}
                        <circle
                          cx={currentPos.x}
                          cy={currentPos.y}
                          r={isHovered ? "7" : "5.5"}
                          fill={color}
                          className="stroke-terminal-panel stroke-2"
                        />

                        {/* Sector Abbreviation Label */}
                        <text
                          x={currentPos.x + 8}
                          y={currentPos.y + 4}
                          className={`text-[10px] font-mono font-bold ${
                            isHovered ? "fill-terminal-primary text-xs" : "fill-terminal-muted"
                          }`}
                        >
                          {sector}
                        </text>
                      </g>
                    );
                  })}

                  {/* Axis Legend Labels */}
                  <text x="250" y="490" textAnchor="middle" className="text-[10px] font-mono fill-terminal-muted">
                    ← Underperforming (RS-Ratio) Outperforming →
                  </text>
                  <text
                    x="15"
                    y="250"
                    textAnchor="middle"
                    transform="rotate(-90 15 250)"
                    className="text-[10px] font-mono fill-terminal-muted"
                  >
                    ← Momentum Lagging / Momentum Gaining →
                  </text>
                </svg>
              </div>
            </TerminalPanel>
          </div>

          {/* Sector Table */}
          <div className="lg:col-span-6 flex flex-col">
            <TerminalPanel
              title="Sector Rotation Status Matrix"
              subtitle="50-Day JdK RS-Ratio vs 10-Day RS-Momentum"
              headerRight={
                <span className="text-[11px] font-mono text-terminal-muted">
                  6 Authoritative Sectors
                </span>
              }
              className="flex-1"
            >
              <DataTable
                columns={columns}
                data={tableData}
                keyField="sector"
                zebra
              />
            </TerminalPanel>
          </div>
        </div>
      )}

      {/* Institutional Quadrant Explanation */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
        <div className="p-3 rounded-sm border border-terminal-border bg-terminal-panel">
          <div className="flex items-center gap-2 mb-1">
            <span className="w-2 h-2 rounded-full bg-emerald-500" />
            <span className="font-mono text-xs font-bold uppercase text-terminal-primary">
              Leading Quadrant
            </span>
          </div>
          <p className="text-[11px] text-terminal-muted leading-relaxed">
            RS-Ratio ≥ 100, Momentum ≥ 100. Strong relative outperformance accelerating against NIFTY 50. Primary candidate for active long exposure.
          </p>
        </div>

        <div className="p-3 rounded-sm border border-terminal-border bg-terminal-panel">
          <div className="flex items-center gap-2 mb-1">
            <span className="w-2 h-2 rounded-full bg-amber-500" />
            <span className="font-mono text-xs font-bold uppercase text-terminal-primary">
              Weakening Quadrant
            </span>
          </div>
          <p className="text-[11px] text-terminal-muted leading-relaxed">
            RS-Ratio ≥ 100, Momentum &lt; 100. Still outperforming on an absolute basis, but relative momentum is declining. Potential rotation out.
          </p>
        </div>

        <div className="p-3 rounded-sm border border-terminal-border bg-terminal-panel">
          <div className="flex items-center gap-2 mb-1">
            <span className="w-2 h-2 rounded-full bg-rose-500" />
            <span className="font-mono text-xs font-bold uppercase text-terminal-primary">
              Lagging Quadrant
            </span>
          </div>
          <p className="text-[11px] text-terminal-muted leading-relaxed">
            RS-Ratio &lt; 100, Momentum &lt; 100. Trailing benchmark performance with negative momentum. Subordinate allocation or zero-weight target.
          </p>
        </div>

        <div className="p-3 rounded-sm border border-terminal-border bg-terminal-panel">
          <div className="flex items-center gap-2 mb-1">
            <span className="w-2 h-2 rounded-full bg-blue-500" />
            <span className="font-mono text-xs font-bold uppercase text-terminal-primary">
              Improving Quadrant
            </span>
          </div>
          <p className="text-[11px] text-terminal-muted leading-relaxed">
            RS-Ratio &lt; 100, Momentum ≥ 100. Still underperforming the benchmark, but relative momentum is rebounding. Early cyclical candidate.
          </p>
        </div>
      </div>
    </div>
  );
}
