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
  children: ReactNode;
}

/**
 * Table with centred headers and drag-resizable columns whose widths persist.
 * Rows are supplied by the caller as ``<tr>`` children, so each page keeps
 * full control over cell rendering.
 */
export function ResizableTable({ id, columns, rawColumns = [], children }: Props) {
  const [widths, setWidths] = useState<Record<number, number>>({});
  const drag = useRef<{ index: number; startX: number; startW: number } | null>(null);
  const headRefs = useRef<(HTMLTableCellElement | null)[]>([]);

  // Read persisted widths after mount so server and client markup agree.
  useEffect(() => setWidths(load(id)), [id]);

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
    <table className="w-full text-sm" style={{ tableLayout: "fixed" }}>
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
