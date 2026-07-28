"use client";

import type { ReactNode } from "react";
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

/** Styled native select with a custom chevron. */
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
  return (
    <div className={`relative ${className}`}>
      <select
        className="input appearance-none pr-9"
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
      >
        {children}
      </select>
      <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
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
