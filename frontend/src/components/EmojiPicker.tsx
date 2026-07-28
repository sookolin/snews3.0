"use client";

const PRESET = [
  "🔥", "⚡️", "📰", "🚨", "🏙", "🚗", "👮", "🌧", "⚠️", "✅", "📢", "🎉",
  "🏆", "💥", "🌟", "❗️", "📌", "🕐", "💰", "🏗", "🚌", "🩺", "🎓", "⚽️",
];

/** Compact emoji picker: preset buttons + free-form input. */
export function EmojiPicker({
  value,
  onChange,
  label = "Эмодзи",
}: {
  value: string;
  onChange: (v: string) => void;
  label?: string;
}) {
  return (
    <div>
      <div className="mb-1 flex items-center gap-2">
        <span className="text-sm font-medium">{label}</span>
        <input
          className="input w-20 text-center"
          value={value}
          maxLength={8}
          onChange={(e) => onChange(e.target.value)}
        />
        {value && (
          <button type="button" className="text-xs text-muted-foreground underline" onClick={() => onChange("")}>
            очистить
          </button>
        )}
      </div>
      <div className="flex flex-wrap gap-1">
        {PRESET.map((em) => (
          <button
            key={em}
            type="button"
            className={`rounded-md border px-2 py-1 text-lg transition-colors ${
              value === em ? "border-primary bg-primary/10" : "border-border hover:bg-muted"
            }`}
            onClick={() => onChange(em)}
          >
            {em}
          </button>
        ))}
      </div>
    </div>
  );
}
