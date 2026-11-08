'use client';
import { useState } from 'react';
import { DataTable, ColumnDef } from '@/components/ui/data-table';

export function HistoryTable({ rows, columns, rowKey, pageSize = 20 }: {
  rows: Record<string, any>[]; columns: ColumnDef<any>[];
  rowKey: string | ((row: any) => string); pageSize?: number;
}) {
  const [page, setPage] = useState(0);
  const pages = Math.max(1, Math.ceil(rows.length / pageSize));
  const current = Math.min(page, pages - 1);
  const start = current * pageSize;
  return <>
    <DataTable<any> data={rows.slice(start, start + pageSize)} columns={columns} keyField={rowKey} />
    <div className="flex items-center justify-between gap-3 mt-3 text-xs text-terminal-muted">
      <button className="control" disabled={current === 0} onClick={() => setPage(current - 1)}>Previous</button>
      <span>{rows.length ? start + 1 : 0}-{Math.min(start + pageSize, rows.length)} of {rows.length} records</span>
      <button className="control" disabled={current >= pages - 1} onClick={() => setPage(current + 1)}>Next</button>
    </div>
  </>;
}
