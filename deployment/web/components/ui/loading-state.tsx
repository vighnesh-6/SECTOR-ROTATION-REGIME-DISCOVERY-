import React from "react";

interface LoadingSkeletonProps {
  className?: string;
  count?: number;
}

export function LoadingSkeleton({
  className = "h-4 w-full",
  count = 1,
}: LoadingSkeletonProps) {
  return (
    <>
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className={`animate-pulse rounded-sm bg-terminal-secondary/80 ${className}`}
        />
      ))}
    </>
  );
}

interface LoadingTableSkeletonProps {
  rows?: number;
  columns?: number;
  className?: string;
}

export function LoadingTableSkeleton({
  rows = 5,
  columns = 4,
  className = "",
}: LoadingTableSkeletonProps) {
  return (
    <div
      className={`rounded-sm border border-terminal-border bg-terminal-panel p-4 ${className}`}
    >
      <div className="flex gap-4 pb-3 border-b border-terminal-border/60">
        {Array.from({ length: columns }).map((_, i) => (
          <div
            key={i}
            className="h-3.5 flex-1 rounded-sm bg-terminal-secondary animate-pulse"
          />
        ))}
      </div>
      <div className="space-y-3 pt-3">
        {Array.from({ length: rows }).map((_, rowIdx) => (
          <div key={rowIdx} className="flex gap-4">
            {Array.from({ length: columns }).map((_, colIdx) => (
              <div
                key={colIdx}
                className="h-4 flex-1 rounded-sm bg-terminal-secondary/60 animate-pulse"
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

interface LoadingMetricSkeletonProps {
  count?: number;
  className?: string;
}

export function LoadingMetricSkeleton({
  count = 4,
  className = "",
}: LoadingMetricSkeletonProps) {
  return (
    <div className={`grid grid-cols-2 md:grid-cols-4 gap-3.5 ${className}`}>
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className="rounded-sm border border-terminal-border bg-terminal-panel p-3.5 space-y-2"
        >
          <div className="h-3 w-1/2 rounded-sm bg-terminal-secondary animate-pulse" />
          <div className="h-6 w-3/4 rounded-sm bg-terminal-secondary/80 animate-pulse" />
          <div className="h-2.5 w-1/3 rounded-sm bg-terminal-secondary/50 animate-pulse" />
        </div>
      ))}
    </div>
  );
}

interface LoadingStateProps {
  message?: string;
  className?: string;
}

export function LoadingState({
  message = "Loading telemetry from Neon PostgreSQL...",
  className = "py-16",
}: LoadingStateProps) {
  return (
    <div
      className={`flex flex-col items-center justify-center text-center gap-3 ${className}`}
    >
      <div className="flex items-center gap-1.5">
        <span className="w-1.5 h-1.5 rounded-full bg-terminal-primary animate-ping" />
        <span className="w-1.5 h-1.5 rounded-full bg-terminal-muted animate-pulse" />
        <span className="w-1.5 h-1.5 rounded-full bg-terminal-border animate-pulse" />
      </div>
      <p className="font-mono text-xs text-terminal-muted">{message}</p>
    </div>
  );
}

