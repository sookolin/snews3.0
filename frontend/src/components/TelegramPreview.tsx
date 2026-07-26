"use client";

export interface PreviewButton {
  text: string;
  url: string;
  color?: string;
}

export interface PreviewMedia {
  url?: string;
  type?: string;
  spoiler?: boolean;
}

export interface TelegramPreviewProps {
  channelName?: string;
  channelAvatar?: string | null;
  title?: string;
  text?: string;
  media?: PreviewMedia[];
  buttons?: PreviewButton[][];
  locationTitle?: string | null;
  views?: number;
}

const REACTIONS = ["❤️", "🔥", "👍", "🎉"];

const BTN_COLOR: Record<string, string> = {
  primary: "bg-blue-600 text-white",
  success: "bg-green-600 text-white",
  danger: "bg-red-600 text-white",
  // legacy aliases
  blue: "bg-blue-600 text-white",
  green: "bg-green-600 text-white",
  red: "bg-red-600 text-white",
};

/** iOS-style Telegram channel message preview. */
export function TelegramPreview({
  channelName = "Канал",
  channelAvatar,
  title,
  text,
  media = [],
  buttons = [],
  locationTitle,
  views = 0,
}: TelegramPreviewProps) {
  const enabledMedia = media.filter((m) => m.url);
  const initial = channelName.trim().charAt(0).toUpperCase() || "S";
  const time = new Date().toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });

  return (
    <div className="ios-tg">
      {/* iOS status bar + nav header */}
      <div className="ios-tg-nav">
        <div className="ios-tg-back">‹ Назад</div>
        <div className="ios-tg-navtitle">
          <div
            className="ios-tg-navavatar"
            style={channelAvatar ? { backgroundImage: `url(${channelAvatar})` } : undefined}
          >
            {!channelAvatar && initial}
          </div>
          <div className="leading-tight text-center">
            <div className="text-[13px] font-semibold">{channelName}</div>
            <div className="text-[11px] text-black/40 dark:text-white/40">канал</div>
          </div>
        </div>
        <div className="w-12" />
      </div>

      {/* Chat area */}
      <div className="ios-tg-chat">
        <div className="ios-tg-bubble">
          {enabledMedia.length > 0 && (
            <div className={`ios-tg-album album-${Math.min(enabledMedia.length, 4)}`}>
              {enabledMedia.slice(0, 4).map((m, i) => (
                <div key={i} className="ios-tg-cell">
                  {m.type?.startsWith("video") ? (
                    <video src={m.url} muted />
                  ) : (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={m.url} alt="" className={m.spoiler ? "ios-tg-spoiler" : ""} />
                  )}
                  {m.spoiler && <div className="ios-tg-spoiler-badge">Спойлер</div>}
                  {i === 3 && enabledMedia.length > 4 && (
                    <div className="ios-tg-more">+{enabledMedia.length - 4}</div>
                  )}
                </div>
              ))}
            </div>
          )}

          <div className="ios-tg-body">
            {title && <div className="ios-tg-title">{title}</div>}
            {text && (
              <div className="ios-tg-text" dangerouslySetInnerHTML={{ __html: text }} />
            )}
            {locationTitle && (
              <div className="ios-tg-loc">
                <span>📍</span> {locationTitle}
              </div>
            )}
            <div className="ios-tg-meta">
              {views > 0 && <span className="ios-tg-views">👁 {views}</span>}
              <span className="ios-tg-time">{time}</span>
            </div>
          </div>

          {/* reactions */}
          <div className="ios-tg-reactions">
            {REACTIONS.map((r) => (
              <span key={r} className="ios-tg-reaction">
                <span>{r}</span>
                <span className="ios-tg-reaction-count">0</span>
              </span>
            ))}
          </div>
        </div>

        {/* inline buttons (below bubble) */}
        {buttons.length > 0 && (
          <div className="ios-tg-buttons">
            {buttons.map((row, i) => (
              <div key={i} className="flex gap-1.5">
                {row.map((b, j) => (
                  <div
                    key={j}
                    className={`ios-tg-btn ${b.color ? BTN_COLOR[b.color] ?? "" : ""}`}
                  >
                    {b.text || "Кнопка"}
                  </div>
                ))}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* comments bar */}
      <div className="ios-tg-comments">💬 Прокомментировать</div>
    </div>
  );
}
