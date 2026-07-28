"use client";

import { useEffect, useRef } from "react";
import {
  Bold, Italic, Underline, Strikethrough, Link2, Code, EyeOff, CornerDownLeft,
  Eraser, Quote,
} from "lucide-react";

interface Props {
  value: string;
  onChange: (html: string) => void;
  placeholder?: string;
}

/**
 * Lightweight rich-text editor producing Telegram-safe HTML.
 *
 * Formatting is applied to the current selection via ``document.execCommand``,
 * yielding <b>/<i>/<u>/<s>/<a> tags — exactly what Telegram accepts.
 */
export function RichTextEditor({ value, onChange, placeholder }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  /** HTML we last emitted upward — used to avoid clobbering the caret. */
  const lastEmitted = useRef<string>("");

  // Only push the external value in when it genuinely differs from what the
  // editor itself produced (otherwise we would wipe formatting/caret on every
  // parent re-render).
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (value !== lastEmitted.current && value !== el.innerHTML) {
      el.innerHTML = value || "";
      lastEmitted.current = value || "";
    }
  }, [value]);

  const emit = () => {
    const el = ref.current;
    if (!el) return;
    const html = el.innerHTML;
    lastEmitted.current = html;
    onChange(html);
  };

  const exec = (command: string, arg?: string) => {
    ref.current?.focus();
    document.execCommand(command, false, arg);
    emit();
  };

  /** Wrap the current selection in an arbitrary tag (spoiler/code). */
  const wrapSelection = (openTag: string, closeTag: string) => {
    const el = ref.current;
    if (!el) return;
    el.focus();
    const sel = window.getSelection();
    if (!sel || sel.rangeCount === 0 || sel.isCollapsed) return;
    const selected = sel.toString();
    document.execCommand("insertHTML", false, `${openTag}${selected}${closeTag}`);
    emit();
  };

  const addLink = () => {
    const url = window.prompt("Ссылка (URL):", "https://");
    if (url) exec("createLink", url);
  };

  return (
    <div>
      <div className="rte-toolbar">
        <button type="button" className="rte-btn" title="Жирный" onClick={() => exec("bold")}>
          <Bold className="h-3.5 w-3.5" />
        </button>
        <button type="button" className="rte-btn" title="Курсив" onClick={() => exec("italic")}>
          <Italic className="h-3.5 w-3.5" />
        </button>
        <button type="button" className="rte-btn" title="Подчёркнутый" onClick={() => exec("underline")}>
          <Underline className="h-3.5 w-3.5" />
        </button>
        <button type="button" className="rte-btn" title="Зачёркнутый" onClick={() => exec("strikeThrough")}>
          <Strikethrough className="h-3.5 w-3.5" />
        </button>
        <span className="mx-1 h-4 w-px bg-border" />
        <button type="button" className="rte-btn" title="Ссылка" onClick={addLink}>
          <Link2 className="h-3.5 w-3.5" />
        </button>
        <button type="button" className="rte-btn" title="Моноширинный" onClick={() => wrapSelection("<code>", "</code>")}>
          <Code className="h-3.5 w-3.5" />
        </button>
        <button type="button" className="rte-btn" title="Спойлер" onClick={() => wrapSelection('<span class="tg-spoiler">', "</span>")}>
          <EyeOff className="h-3.5 w-3.5" />
        </button>
        <button type="button" className="rte-btn" title="Цитата" onClick={() => wrapSelection("<blockquote>", "</blockquote>")}>
          <Quote className="h-3.5 w-3.5" />
        </button>
        <span className="mx-1 h-4 w-px bg-border" />
        <button type="button" className="rte-btn" title="Перенос строки" onClick={() => exec("insertHTML", "<br>")}>
          <CornerDownLeft className="h-3.5 w-3.5" />
        </button>
        <button type="button" className="rte-btn" title="Убрать форматирование" onClick={() => exec("removeFormat")}>
          <Eraser className="h-3.5 w-3.5" />
        </button>
      </div>
      <div
        ref={ref}
        className="rte-area"
        contentEditable
        suppressContentEditableWarning
        data-placeholder={placeholder}
        onInput={emit}
        onBlur={emit}
      />
    </div>
  );
}
