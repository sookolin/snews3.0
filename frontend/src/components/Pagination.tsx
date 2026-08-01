"use client";

import { useRef, useState } from "react";
import { ChevronDown, ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from "lucide-react";

/** Page-size options offered in every paginated table. */
export const PAGE_SIZES = [20, 50, 100, 200];

interface Props {
  page: number;
  size: number;
  total: number;
  onPage: (page: number) => void;
  onSize: (size: number) => void;
  /** ``top`` renders above the table (no top margin), ``bottom`` below it. */
  position?: "top" | "bottom";
}

/**
 * Page-size selector + page stepping. Rendered both above and below every
 * table so long lists can be paged without scrolling back down.
 * Resets to page 1 whenever the size changes so the offset stays valid.
 */
export function Pagination({ page, size, total, onPage, onSize, position = "bottom" }: Props) {
  const pages = Math.max(1, Math.ceil(total / size));
  const from = total === 0 ? 0 : (page - 1) * size + 1;
  const to = Math.min(page * size, total);

  const [inputVal, setInputVal] = useState("");
  const [open, setOpen] = useState(false);
  const dropRef = useRef<HTMLDivElement>(null);

  const goToPage = (raw: string) => {
    const n = parseInt(raw, 10);
    if (!isNaN(n) && n >= 1 && n <= pages) onPage(n);
  };

  return (
    <div
      className={`flex flex-wrap items-center justify-between gap-3 text-sm ${
        position === "top" ? "mb-3" : "mt-3"
      }`}
    >
      <div className="flex items-center gap-2 text-muted-foreground">
        <span className="whitespace-nowrap">На странице</span>

        {/* Dropdown button — same pill style as city/status filters */}
        <div ref={dropRef} className="relative">
          <button
            type="button"
            className={`flex items-center gap-1.5 rounded-md border px-3 py-1 text-sm font-medium transition-colors ${
              open
                ? "border-primary bg-primary text-primary-foreground"
                : "border-border bg-card text-foreground hover:border-primary/50"
            }`}
            onClick={() => setOpen((v) => !v)}
            onBlur={(e) => {
              if (!dropRef.current?.contains(e.relatedTarget as Node)) setOpen(false);
            }}
          >
            {size}
            <ChevronDown className={`h-3.5 w-3.5 transition-transform ${open ? "rotate-180" : ""}`} />
          </button>

          {open && (
            <div className="absolute left-0 top-full z-50 mt-1 min-w-[72px] overflow-hidden rounded-lg border border-border bg-card shadow-md">
              {PAGE_SIZES.map((s) => (
                <button
                  key={s}
                  type="button"
                  className={`w-full px-4 py-1.5 text-left text-sm transition-colors hover:bg-muted ${
                    s === size ? "font-semibold text-primary" : "text-foreground"
                  }`}
                  onMouseDown={(e) => {
                    e.preventDefault(); // keep focus on trigger so onBlur fires after
                    onSize(s);
                    onPage(1);
                    setOpen(false);
                  }}
                >
                  {s}
                </button>
              ))}
            </div>
          )}
        </div>

        <span className="whitespace-nowrap">
          {from}–{to} из {total}
        </span>
      </div>

      <div className="flex items-center gap-1.5">
        {/* First page */}
        <button
          className="btn-icon"
          title="Первая страница"
          disabled={page <= 1}
          onClick={() => onPage(1)}
        >
          <ChevronsLeft className="h-4 w-4" />
        </button>
        {/* Previous page */}
        <button
          className="btn-icon"
          title="Предыдущая страница"
          disabled={page <= 1}
          onClick={() => onPage(page - 1)}
        >
          <ChevronLeft className="h-4 w-4" />
        </button>

        {/* Direct page input */}
        <div className="flex items-center gap-1">
          <input
            className="input h-8 w-14 text-center text-sm"
            type="number"
            min={1}
            max={pages}
            placeholder={String(page)}
            value={inputVal}
            onChange={(e) => setInputVal(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                goToPage(inputVal);
                setInputVal("");
              }
            }}
            onBlur={() => {
              if (inputVal) goToPage(inputVal);
              setInputVal("");
            }}
            title="Перейти к странице"
          />
          <span className="whitespace-nowrap text-muted-foreground">/ {pages}</span>
        </div>

        {/* Next page */}
        <button
          className="btn-icon"
          title="Следующая страница"
          disabled={page >= pages}
          onClick={() => onPage(page + 1)}
        >
          <ChevronRight className="h-4 w-4" />
        </button>
        {/* Last page */}
        <button
          className="btn-icon"
          title="Последняя страница"
          disabled={page >= pages}
          onClick={() => onPage(pages)}
        >
          <ChevronsRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
