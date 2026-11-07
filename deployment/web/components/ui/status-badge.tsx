import React from "react";

interface StatusBadgeProps {
  label: string;
  variant?: "success" | "danger" | "warning" | "neutral" | "regime";
  regimeId?: number;
  size?: "sm" | "md";
  className?: string;
}

export function StatusBadge({
  label,
  variant = "neutral",
  regimeId,
  size = "sm",
  className = "",
}: StatusBadgeProps) {
  const sizeClasses = size === "sm" ? "px-1.5 py-0.5 text-[10px]" : "px-2.5 py-1 text-xs";

  let variantClasses = "border border-terminal-border bg-terminal-secondary text-terminal-muted";

  if (variant === "success") {
    variantClasses = "border border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400";
  } else if (variant === "danger") {
    variantClasses = "border border-rose-500/30 bg-rose-500/10 text-rose-600 dark:text-rose-400";
  } else if (variant === "warning") {
    variantClasses = "border border-amber-500/30 bg-amber-500/10 text-amber-600 dark:text-amber-400";
  } else if (variant === "regime") {
    // Regime colors mapping
    switch (regimeId) {
      case 0: // Reflation Rally (Tech/Metal)
        variantClasses = "border border-cyan-500/40 bg-cyan-500/10 text-cyan-600 dark:text-cyan-300";
        break;
      case 1: // Vol Bounce (Auto/Metal)
        variantClasses = "border border-amber-500/40 bg-amber-500/10 text-amber-600 dark:text-amber-300";
        break;
      case 2: // Low-Vol Base (IT/Pharma)
        variantClasses = "border border-blue-500/40 bg-blue-500/10 text-blue-600 dark:text-blue-300";
        break;
      case 3: // Crisis Liquidation (Pharma/FMCG/Cash)
        variantClasses = "border border-rose-500/40 bg-rose-500/10 text-rose-600 dark:text-rose-300";
        break;
      case 4: // Steady Expansion (Metal/Auto)
        variantClasses = "border border-emerald-500/40 bg-emerald-500/10 text-emerald-600 dark:text-emerald-300";
        break;
      case 5: // Risk-Off Digestion (Pharma/FMCG/Cash)
        variantClasses = "border border-purple-500/40 bg-purple-500/10 text-purple-600 dark:text-purple-300";
        break;
      default:
        variantClasses = "border border-slate-500/40 bg-slate-500/10 text-slate-600 dark:text-slate-300";
    }
  }

  return (
    <span
      className={`inline-flex items-center font-mono font-medium rounded-sm uppercase tracking-wider ${sizeClasses} ${variantClasses} ${className}`}
    >
      {label}
    </span>
  );
}

