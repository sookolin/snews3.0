"use client";

import {
  Children,
  isValidElement,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { Check, ChevronDown } from "lucide-react";

/** Styled checkbox with a label. */
export function Checkbox({
  checked,
  onChange,
  label,
  disabled,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label?: ReactNode;
  disabled?: boolean;
}) {
  return (
    <label className={`inline-flex cursor-pointer items-center gap-2 text-sm ${disabled ? "opacity-50" : ""}`}>
      <span className="relative inline-flex h-[18px] w-[18px] shrink-0 items-center justify-center">
        <input
          type="checkbox"
          className="peer sr-only"
          checked={checked}
          disabled={disabled}
          onChange={(e) => onChange(e.target.checked)}
        />
        <span
          className="absolute inset-0 rounded-[5px] border border-border bg-card transition-colors
                     peer-checked:border-primary peer-checked:bg-primary
                     peer-focus-visible:ring-2 peer-focus-visible:ring-primary/30"
        />
        {checked && <Check className="relative h-3 w-3 text-white" strokeWidth={3} />}
      </span>
      {label && <span>{label}</span>}
    </label>
  );
}

/** Styled radio group. */
export function RadioGroup<T extends string>({
  value,
  onChange,
  options,
  name,
}: {
  value: T;
  onChange: (v: T) => void;
  options: { value: T; label: string }[];
  name: string;
}) {
  return (
    <div className="flex flex-wrap gap-3">
      {options.map((o) => (
        <label key={o.value} className="inline-flex cursor-pointer items-center gap-2 text-sm">
          <span className="relative inline-flex h-[18px] w-[18px] shrink-0 items-center justify-center">
            <input
              type="radio"
              name={name}
              className="peer sr-only"
              checked={value === o.value}
              onChange={() => onChange(o.value)}
            />
            <span
              className="absolute inset-0 rounded-full border border-border bg-card transition-colors
                         peer-checked:border-primary peer-focus-visible:ring-2 peer-focus-visible:ring-primary/30"
            />
            {value === o.value && <span className="relative h-2 w-2 rounded-full bg-primary" />}
          </span>
          <span>{o.label}</span>
        </label>
      ))}
    </div>
  );
}

/**
 * Custom dropdown that keeps the native `<option>` children API, so existing
 * call sites need no changes: the options are read out of the children and
 * rendered as a themed listbox instead of the browser's own popup.
 */
export function Select({
  value,
  onChange,
  children,
  className = "",
  disabled,
}: {
  value: string | number;
  onChange: (v: string) => void;
  children: ReactNode;
  className?: string;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const boxRef = useRef<HTMLDivElement>(null);

  const options: { value: string; label: ReactNode; disabled?: boolean }[] = [];
  Children.forEach(children, (child) => {
    if (!isValidElement(child)) return;
    const props = child.props as { value?: string | number; children?: ReactNode; disabled?: boolean };
    options.push({
      value: String(props.value ?? ""),
      label: props.children ?? String(props.value ?? ""),
      disabled: props.disabled,
    });
  });

  const current = options.find((o) => o.value === String(value));

  // Close on outside click and on Escape.
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (!boxRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div ref={boxRef} className={`relative ${className}`}>
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen((v) => !v)}
        className="input flex w-full items-center justify-between gap-2 text-left disabled:cursor-not-allowed disabled:opacity-50"
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <span className="flex-1 truncate">{current?.label ?? ""}</span>
        <ChevronDown
          className={`h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-200 ${open ? "rotate-180" : ""}`}
        />
      </button>
      {open && (
        <div
          role="listbox"
          className="absolute z-50 mt-1 max-h-60 w-full origin-top overflow-y-auto rounded-lg border border-border
                     bg-card p-1 shadow-lg animate-in"
        >
          {options.map((o) => {
            const active = o.value === String(value);
            return (
              <button
                key={o.value}
                type="button"
                role="option"
                aria-selected={active}
                disabled={o.disabled}
                onClick={() => { onChange(o.value); setOpen(false); }}
                className={`flex w-full items-center justify-between gap-2 rounded-md px-2.5 py-1.5 text-left text-sm
                            transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${
                              active ? "bg-primary/10 font-medium text-primary" : "hover:bg-muted"
                            }`}
              >
                <span className="truncate">{o.label}</span>
                {active && <Check className="h-3.5 w-3.5 shrink-0" strokeWidth={3} />}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

/** Styled range slider showing the current value. */
export function Slider({
  value,
  onChange,
  min = 0,
  max = 100,
  step = 1,
  label,
  format,
}: {
  value: number;
  onChange: (v: number) => void;
  min?: number;
  max?: number;
  step?: number;
  label?: string;
  format?: (v: number) => string;
}) {
  return (
    <div>
      {label && (
        <div className="mb-1 flex items-center justify-between text-sm">
          <span className="font-medium">{label}</span>
          <span className="text-muted-foreground">{format ? format(value) : value}</span>
        </div>
      )}
      <input
        type="range"
        className="slider w-full"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </div>
  );
}

/** Toggle switch. */
export function Switch({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label?: ReactNode;
}) {
  return (
    <label className="inline-flex cursor-pointer items-center gap-2 text-sm">
      <span className="relative inline-flex h-5 w-9 shrink-0 items-center">
        <input
          type="checkbox"
          className="peer sr-only"
          checked={checked}
          onChange={(e) => onChange(e.target.checked)}
        />
        <span className="absolute inset-0 rounded-full bg-border transition-colors peer-checked:bg-primary" />
        <span
          className={`relative ml-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform ${
            checked ? "translate-x-4" : ""
          }`}
        />
      </span>
      {label && <span>{label}</span>}
    </label>
  );
}
