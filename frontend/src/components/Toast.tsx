"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { AlertTriangle, CheckCircle2, Info, X, XCircle } from "lucide-react";

export type ToastKind = "success" | "error" | "warning" | "info";

interface Toast {
  id: number;
  kind: ToastKind;
  message: string;
}

interface ToastApi {
  show: (message: string, kind?: ToastKind) => void;
  success: (message: string) => void;
  error: (message: string) => void;
  warning: (message: string) => void;
  info: (message: string) => void;
}

const ToastContext = createContext<ToastApi | null>(null);

/** How long a toast stays on screen. */
const LIFETIME_MS = 3000;

/** Per-kind colour so the action type is readable at a glance. */
const STYLES: Record<ToastKind, { ring: string; bg: string; text: string; Icon: typeof Info }> = {
  success: {
    bg: "bg-emerald-500/85",
    ring: "ring-emerald-300/60",
    text: "text-white",
    Icon: CheckCircle2,
  },
  error: {
    bg: "bg-rose-500/85",
    ring: "ring-rose-300/60",
    text: "text-white",
    Icon: XCircle,
  },
  warning: {
    bg: "bg-amber-500/85",
    ring: "ring-amber-300/60",
    text: "text-white",
    Icon: AlertTriangle,
  },
  info: {
    bg: "bg-slate-800/85",
    ring: "ring-slate-400/50",
    text: "text-white",
    Icon: Info,
  },
};

/**
 * Toast host: a centered stack at the top of the viewport.
 *
 * Each toast lives for 3s and can be dismissed earlier by clicking it. The
 * stack is a flex column, so when the first toast leaves the others slide up
 * on their own — no manual offset bookkeeping for any number of toasts.
 */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextId = useRef(1);

  const dismiss = useCallback((id: number) => {
    setToasts((list) => list.filter((t) => t.id !== id));
  }, []);

  const show = useCallback((message: string, kind: ToastKind = "info") => {
    const text = (message || "").trim();
    if (!text) return;
    const id = nextId.current++;
    setToasts((list) => [...list, { id, kind, message: text }]);
  }, []);

  const api = useMemo<ToastApi>(
    () => ({
      show,
      success: (m: string) => show(m, "success"),
      error: (m: string) => show(m, "error"),
      warning: (m: string) => show(m, "warning"),
      info: (m: string) => show(m, "info"),
    }),
    [show]
  );

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div
        className="pointer-events-none fixed left-1/2 top-4 z-[100] flex w-full max-w-sm -translate-x-1/2 flex-col items-center gap-2 px-3"
        role="region"
        aria-label="Уведомления"
      >
        {toasts.map((t) => (
          <ToastCard key={t.id} toast={t} onDismiss={dismiss} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

function ToastCard({ toast, onDismiss }: { toast: Toast; onDismiss: (id: number) => void }) {
  const [visible, setVisible] = useState(false);
  const style = STYLES[toast.kind];

  useEffect(() => {
    // Mount → next frame → animate in, so the transition actually runs.
    const raf = requestAnimationFrame(() => setVisible(true));
    const timer = setTimeout(() => onDismiss(toast.id), LIFETIME_MS);
    return () => {
      cancelAnimationFrame(raf);
      clearTimeout(timer);
    };
  }, [toast.id, onDismiss]);

  return (
    <button
      type="button"
      onClick={() => onDismiss(toast.id)}
      title="Скрыть"
      aria-live="polite"
      className={`pointer-events-auto flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm shadow-lg ring-1 backdrop-blur-sm transition-all duration-200 ${
        style.bg
      } ${style.ring} ${style.text} ${
        visible ? "translate-y-0 opacity-100" : "-translate-y-2 opacity-0"
      }`}
    >
      <style.Icon className="h-4 w-4 shrink-0" />
      <span className="min-w-0 flex-1 break-words leading-snug">{toast.message}</span>
      <X className="h-3.5 w-3.5 shrink-0 opacity-70" />
    </button>
  );
}

/** Access the toast API. Falls back to no-ops outside the provider. */
export function useToast(): ToastApi {
  const ctx = useContext(ToastContext);
  if (ctx) return ctx;
  const noop = () => undefined;
  return { show: noop, success: noop, error: noop, warning: noop, info: noop };
}
