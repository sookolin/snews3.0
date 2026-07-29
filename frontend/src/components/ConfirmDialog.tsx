"use client";

import { useEffect, useState } from "react";
import { Modal } from "@/components/Modal";

interface ConfirmOptions {
  title?: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  danger?: boolean;
}

let resolveCallback: ((value: boolean) => void) | null = null;

/** Drop-in replacement for native `confirm()`. Returns a Promise<boolean>. */
export function confirm(options: string | ConfirmOptions): Promise<boolean> {
  const opts = typeof options === "string" ? { message: options } : options;
  if (typeof window === "undefined") return Promise.resolve(false);
  window.dispatchEvent(new CustomEvent("snews:confirm", { detail: opts }));
  return new Promise<boolean>((resolve) => {
    resolveCallback = resolve;
  });
}

/**
 * Mount this component once (in Providers). It listens for the custom event
 * and renders the themed dialog instead of the browser's native confirm box.
 */
export function ConfirmDialog() {
  const [open, setOpen] = useState(false);
  const [opts, setOpts] = useState<Required<ConfirmOptions>>({
    title: "Подтвердите действие",
    message: "",
    confirmText: "Подтвердить",
    cancelText: "Отмена",
    danger: false,
  });

  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent<ConfirmOptions>).detail;
      setOpts({
        title: detail.title ?? "Подтвердите действие",
        message: detail.message,
        confirmText: detail.confirmText ?? "Подтвердить",
        cancelText: detail.cancelText ?? "Отмена",
        danger: detail.danger ?? false,
      });
      setOpen(true);
    };
    window.addEventListener("snews:confirm", handler);
    return () => window.removeEventListener("snews:confirm", handler);
  }, []);

  const answer = (value: boolean) => {
    resolveCallback?.(value);
    resolveCallback = null;
    setOpen(false);
  };

  return (
    <Modal open={open} onClose={() => answer(false)} title={opts.title}>
      <div className="space-y-4">
        <p className="text-sm leading-relaxed">{opts.message}</p>
        <div className="flex justify-end gap-2 border-t border-border pt-4">
          <button className="btn-outline" onClick={() => answer(false)}>
            {opts.cancelText}
          </button>
          <button
            className={opts.danger ? "btn-danger" : "btn-primary"}
            onClick={() => answer(true)}
          >
            {opts.confirmText}
          </button>
        </div>
      </div>
    </Modal>
  );
}
