import React from "react";
import { ArrowUpRight, ArrowDownRight, Minus } from "lucide-react";

export interface MetricTileProps {
  label: string;
  value: string | number | null | undefined;
  subValue?: string;
  subtitle?: string;
  delta?: number | string | null;
  deltaType?: "positive" | "negative" | "neutral" | "warning";
  deltaLabel?: string;
  deltaSuffix?: string;
  variant?: "default" | "positive" | "negative";
  className?: string;
}

export function MetricTile({
  label,
  value,
  subValue,
  subtitle,
  delta,
  deltaType,
  deltaLabel,
  deltaSuffix = "%",
  variant = "default",
  className = "",
}: MetricTileProps) {
  // Support either subtitle or subValue seamlessly
  const secondaryText = subtitle || subValue;

  // Determine direction & polarity
  let isPositive = false;
  let isNegative = false;
  let isWarning = false;
  let isNeutral = false;

  if (deltaType) {
    isPositive = deltaType === "positive";
    isNegative = deltaType === "negative";
    isWarning = deltaType === "warning";
    isNeutral = deltaType === "neutral";
  } else if (typeof delta === "number") {
    isPositive = delta > 0;
    isNegative = delta < 0;
    isNeutral = delta === 0;
  } else if (typeof delta === "string") {
    const trimmed = delta.trim();
    if (trimmed.startsWith("+")) isPositive = true;
    else if (trimmed.startsWith("-")) isNegative = true;
    else isNeutral = true;
  }

  // Format the display string for delta safely without calling .toFixed on non-numbers
  const renderDeltaContent = () => {
    if (delta === null || delta === undefined) return null;

    if (typeof delta === "number") {
      const formattedNum = Number.isFinite(delta) ? delta.toFixed(2) : String(delta);
      return `${delta > 0 ? "+" : ""}${formattedNum}${deltaSuffix || ""}`;
    }

    // String delta: render directly as provided without arbitrary modification
    return delta;
  };

  const deltaText = renderDeltaContent();

  const getBadgeStyle = () => {
    if (isPositive || variant === "positive") {
      return "border border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400";
    }
    if (isNegative || variant === "negative") {
      return "border border-rose-500/30 bg-rose-500/10 text-rose-600 dark:text-rose-400";
    }
    if (isWarning) {
      return "border border-amber-500/30 bg-amber-500/10 text-amber-600 dark:text-amber-400";
    }
    return "border border-terminal-border bg-terminal-secondary text-terminal-muted";
  };

  return (
    <div
      className={`rounded-sm border border-terminal-border bg-terminal-panel p-3 transition-colors ${className}`}
    >
      <div className="flex items-center justify-between text-[11px] font-mono text-terminal-muted uppercase tracking-wider mb-1">
        <span>{label}</span>
        {deltaLabel && <span className="text-[10px] text-terminal-muted/80">{deltaLabel}</span>}
      </div>

      <div className="flex items-baseline justify-between gap-2">
        <div className="font-mono text-xl sm:text-2xl font-bold tracking-tight text-terminal-primary tabular-nums">
          {value !== null && value !== undefined ? value : "—"}
        </div>

        {deltaText !== null && (
          <div
            className={`inline-flex items-center gap-0.5 text-xs font-mono font-semibold px-1.5 py-0.5 rounded-sm tabular-nums ${getBadgeStyle()}`}
          >
            {isPositive ? (
              <ArrowUpRight className="w-3 h-3 flex-shrink-0" />
            ) : isNegative ? (
              <ArrowDownRight className="w-3 h-3 flex-shrink-0" />
            ) : (
              <Minus className="w-3 h-3 flex-shrink-0" />
            )}
            <span>{deltaText}</span>
          </div>
        )}
      </div>

      {secondaryText && (
        <div className="text-[11px] font-mono text-terminal-muted mt-1 tabular-nums">
          {secondaryText}
        </div>
      )}
    </div>
  );
}
