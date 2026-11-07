import React from "react";

interface TerminalPanelProps {
  title?: string;
  subtitle?: string;
  badge?: React.ReactNode;
  headerRight?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  bodyClassName?: string;
}

export function TerminalPanel({
  title,
  subtitle,
  badge,
  headerRight,
  children,
  className = "",
  bodyClassName = "p-3.5",
}: TerminalPanelProps) {
  return (
    <div
      className={`rounded-sm border border-terminal-border bg-terminal-panel shadow-sm transition-colors ${className}`}
    >
      {(title || subtitle || headerRight) && (
        <div className="flex items-center justify-between border-b border-terminal-border px-3.5 py-2.5 bg-terminal-secondary/40">
          <div className="flex items-center gap-2">
            <div>
              {title && (
                <div className="flex items-center gap-2">
                  <h3 className="font-mono text-xs font-bold uppercase tracking-wider text-terminal-primary">
                    {title}
                  </h3>
                  {badge}
                </div>
              )}
              {subtitle && (
                <p className="text-[11px] font-mono text-terminal-muted mt-0.5">
                  {subtitle}
                </p>
              )}
            </div>
          </div>
          {headerRight && <div className="flex items-center gap-2">{headerRight}</div>}
        </div>
      )}
      <div className={bodyClassName}>{children}</div>
    </div>
  );
}

