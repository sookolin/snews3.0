"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";

const STORAGE_PREFIX = "table-widths:";
const MIN_WIDTH = 56;

/**
 * Column widths are keyed by table id and column index, so a table keeps its
 * layout across reloads and navigation. Unknown/legacy entries are ignored.
 */
function load(tableId: string): Record<number, number> {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(STORAGE_PREFIX + tableId);
    return raw ? (JSON.parse(raw) as Record<number, number>) : {};
  } catch {
    return {};
  }
}

function save(tableId: string, widths: Record<number, number>): void {
  try {
    window.localStorage.setItem(STORAGE_PREFIX + tableId, JSON.stringify(widths));
  } catch {
    // Private mode / quota — widths simply stay per-session.
  }
}

interface Props {
  /** Stable id used as the localStorage key. */
  id: string;
  /** Header contents, in order (plain text or a node like a checkbox). */
  columns: ReactNode[];
  /** Column indexes whose header stays left-aligned (e.g. checkbox cells). */
  rawColumns?: number[];
  /**
   * Initial pixel widths per column index, applied when the user has not
   * manually resized that column yet (no persisted value in localStorage).
   * Lets a page pin narrow columns like the checkbox/ID cells.
   */
  defaultWidths?: Record<number, number>;
  children: ReactNode;
}

/**
 * Table with centred headers and drag-resizable columns whose widths persist.
 * Rows are supplied by the caller as ``<tr>`` children, so each page keeps
 * full control over cell rendering.
 */
export function ResizableTable({
  id,
  columns,
  rawColumns = [],
  defaultWidths = {},
  children,
}: Props) {
  const [widths, setWidths] = useState<Record<number, number>>({});
  const drag = useRef<{ index: number; startX: number; startW: number } | null>(null);
  const headRefs = useRef<(HTMLTableCellElement | null)[]>([]);
  const tableRef = useRef<HTMLTableElement | null>(null);

  /** Plain-text labels for each column, used as mobile card field names. */
  const labelText = (node: ReactNode): string => {
    if (typeof node === "string" || typeof node === "number") return String(node);
    return "";
  };

  // On mobile the table collapses into cards (see globals.css). Each cell then
  // shows its column name via a ``data-label`` attribute, which we stamp onto
  // every ``<td>`` after render so pages don't have to annotate each cell.
  useEffect(() => {
    const table = tableRef.current;
    if (!table) return;
    const labels = columns.map(labelText);
    for (const row of Array.from(table.tBodies[0]?.rows ?? [])) {
      let col = 0;
      for (const cell of Array.from(row.cells)) {
        const span = cell.colSpan || 1;
        const label = labels[col] || "";
        if (label) cell.setAttribute("data-label", label);
        else cell.removeAttribute("data-label");
        col += span;
      }
    }
  });

  // Read persisted widths after mount so server and client markup agree.
  // Page-provided defaults are the base; any column the user has resized
  // (persisted in localStorage) overrides its default.
  useEffect(
    () => setWidths({ ...defaultWidths, ...load(id) }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [id]
  );

  const onMove = useCallback(
    (e: MouseEvent) => {
      const d = drag.current;
      if (!d) return;
      const next = Math.max(MIN_WIDTH, d.startW + (e.clientX - d.startX));
      setWidths((w) => ({ ...w, [d.index]: next }));
    },
    []
  );

  const onUp = useCallback(() => {
    if (!drag.current) return;
    drag.current = null;
    document.body.style.cursor = "";
    setWidths((w) => {
      save(id, w);
      return w;
    });
  }, [id]);

  useEffect(() => {
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, [onMove, onUp]);

  const startDrag = (index: number) => (e: React.MouseEvent) => {
    e.preventDefault();
    const current = widths[index] ?? headRefs.current[index]?.offsetWidth ?? 120;
    drag.current = { index, startX: e.clientX, startW: current };
    document.body.style.cursor = "col-resize";
  };

  const reset = () => {
    setWidths({});
    save(id, {});
  };

  return (
    <table ref={tableRef} className="resizable-table w-full text-sm" style={{ tableLayout: "fixed" }}>
      <thead className="bg-muted text-muted-foreground">
        <tr>
          {columns.map((label, i) => (
            <th
              key={i}
              ref={(el) => {
                headRefs.current[i] = el;
              }}
              className={`relative select-none px-4 py-3 ${
                rawColumns.includes(i) ? "text-left" : "text-center"
              }`}
              style={widths[i] ? { width: widths[i] } : undefined}
            >
              {label}
              {i < columns.length - 1 && !rawColumns.includes(i) && (
                <span
                  role="separator"
                  aria-orientation="vertical"
                  title="Потяните, чтобы изменить ширину. Двойной клик — сбросить все."
                  onMouseDown={startDrag(i)}
                  onDoubleClick={reset}
                  className="absolute right-0 top-0 h-full w-1.5 cursor-col-resize hover:bg-primary/40"
                />
              )}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>{children}</tbody>
    </table>
  );
}
