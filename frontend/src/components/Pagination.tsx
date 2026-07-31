"use client";

import { useState } from "react";
import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from "lucide-react";

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
        <select
          className="input w-[92px] cursor-pointer"
          value={size}
          onChange={(e) => {
            onSize(Number(e.target.value));
            onPage(1);
          }}
        >
          {PAGE_SIZES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
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
