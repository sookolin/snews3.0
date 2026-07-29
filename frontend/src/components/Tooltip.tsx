"use client";

import { useRef, useState, type ReactNode } from "react";

interface Props {
  content: string;
  children: ReactNode;
  side?: "top" | "bottom" | "left" | "right";
}

/**
 * Lightweight tooltip that matches the panel's design system.
 * Use as: <Tooltip content="Описание"><button>…</button></Tooltip>
 */
export function Tooltip({ content, children, side = "top" }: Props) {
  const [visible, setVisible] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);

  const posClass =
    side === "bottom"
      ? "top-full mt-1.5 left-1/2 -translate-x-1/2"
      : side === "left"
      ? "right-full mr-1.5 top-1/2 -translate-y-1/2"
      : side === "right"
      ? "left-full ml-1.5 top-1/2 -translate-y-1/2"
      : "bottom-full mb-1.5 left-1/2 -translate-x-1/2";

  return (
    <span
      ref={ref}
      className="relative inline-flex"
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={() => setVisible(false)}
      onFocus={() => setVisible(true)}
      onBlur={() => setVisible(false)}
    >
      {children}
      {visible && content && (
        <span
          role="tooltip"
          className={`pointer-events-none absolute z-50 whitespace-nowrap rounded-md
                      border border-border bg-card px-2.5 py-1.5 text-xs font-medium
                      text-foreground shadow-md animate-in ${posClass}`}
        >
          {content}
        </span>
      )}
    </span>
  );
}
