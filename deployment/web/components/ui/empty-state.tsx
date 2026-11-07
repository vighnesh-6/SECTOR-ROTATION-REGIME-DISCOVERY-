import React from "react";
import { AlertCircle } from "lucide-react";

interface EmptyStateProps {
  title?: string;
  description?: string;
  icon?: React.ComponentType<{ className?: string }>;
  action?: React.ReactNode;
  className?: string;
}

export function EmptyState({
  title = "No Data Available",
  description = "No records were found for the selected filter or timeframe.",
  icon: Icon = AlertCircle,
  action,
  className = "",
}: EmptyStateProps) {
  return (
    <div
      className={`flex flex-col items-center justify-center p-8 rounded-sm border border-dashed border-terminal-border bg-terminal-secondary/20 text-center ${className}`}
    >
      <div className="w-8 h-8 rounded-full bg-terminal-secondary flex items-center justify-center text-terminal-muted mb-2.5">
        <Icon className="w-4 h-4 stroke-[1.5]" />
      </div>
      <h4 className="font-mono text-xs font-bold uppercase tracking-wider text-terminal-primary">
        {title}
      </h4>
      {description && (
        <p className="text-xs text-terminal-muted max-w-md mt-1 leading-relaxed">
          {description}
        </p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

