import React from "react";

export interface ColumnDef<T> {
  key: string;
  header: string;
  align?: "left" | "center" | "right";
  width?: string;
  render?: (row: T, index: number) => React.ReactNode;
}

interface DataTableProps<T> {
  columns: ColumnDef<T>[];
  data: T[];
  keyField?: keyof T | ((row: T) => string);
  emptyMessage?: string;
  dense?: boolean;
  stickyHeader?: boolean;
  zebra?: boolean;
  className?: string;
}

export function DataTable<T extends Record<string, any>>({
  columns,
  data,
  keyField = "id",
  emptyMessage = "No records found.",
  dense = false,
  stickyHeader = false,
  zebra = false,
  className = "",
}: DataTableProps<T>) {
  const getRowKey = (row: T, idx: number): string => {
    if (typeof keyField === "function") return keyField(row);
    if (row[keyField] !== undefined) return String(row[keyField]);
    return `row-${idx}`;
  };

  const getAlignClass = (align?: "left" | "center" | "right") => {
    if (align === "right") return "text-right justify-end";
    if (align === "center") return "text-center justify-center";
    return "text-left justify-start";
  };

  const pyClass = dense ? "py-1.5" : "py-2.5";
  const pxClass = dense ? "px-2.5" : "px-3.5";

  return (
    <div
      className={`w-full overflow-x-auto rounded-sm border border-terminal-border bg-terminal-panel shadow-sm ${className}`}
    >
      <table className="w-full border-collapse text-xs">
        <thead
          className={`bg-terminal-secondary border-b border-terminal-border text-[11px] font-mono font-semibold uppercase tracking-wider text-terminal-muted ${
            stickyHeader ? "sticky top-0 z-10" : ""
          }`}
        >
          <tr>
            {columns.map((col) => (
              <th
                key={col.key}
                style={col.width ? { width: col.width } : undefined}
                className={`${pxClass} ${pyClass} ${getAlignClass(col.align)} whitespace-nowrap`}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-terminal-border/50 text-terminal-primary">
          {data.length === 0 ? (
            <tr>
              <td
                colSpan={columns.length}
                className="py-8 text-center font-mono text-xs text-terminal-muted"
              >
                {emptyMessage}
              </td>
            </tr>
          ) : (
            data.map((row, idx) => (
              <tr
                key={getRowKey(row, idx)}
                className={`transition-colors hover:bg-terminal-secondary/40 ${
                  zebra && idx % 2 === 1 ? "bg-terminal-secondary/20" : ""
                }`}
              >
                {columns.map((col) => {
                  const content = col.render ? col.render(row, idx) : row[col.key];
                  return (
                    <td
                      key={col.key}
                      className={`${pxClass} ${pyClass} ${getAlignClass(
                        col.align
                      )} font-mono tabular-nums whitespace-nowrap`}
                    >
                      {content !== undefined && content !== null ? content : "—"}
                    </td>
                  );
                })}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

