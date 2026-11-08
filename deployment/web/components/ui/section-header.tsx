import React from "react";

interface SectionHeaderProps {
  title: string;
  description?: string;
  badge?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}

export function SectionHeader({
  title,
  description,
  badge,
  action,
  className = "",
}: SectionHeaderProps) {
  return (
    <div
      className={`flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 pb-2.5 mb-4 border-b border-terminal-border ${className}`}
    >
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-xl sm:text-2xl font-semibold tracking-tight text-terminal-primary">
            {title}
          </h2>
          {badge}
        </div>
        {description && (
          <p className="text-sm text-terminal-muted mt-2 leading-relaxed">
            {description}
          </p>
        )}
      </div>
      {action && (
        <div className="flex items-center gap-2 self-start sm:self-center">
          {action}
        </div>
      )}
    </div>
  );
}

