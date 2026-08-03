"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { login, setTokens } from "@/lib/api";
import { Image as ImageIcon } from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [totp, setTotp] = useState("");
  const [needTotp, setNeedTotp] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  //: Diagnostics for the Telegram widget: the domain Telegram sees + the bot
  //: username baked into the bundle. Helps debug "Bot domain invalid".
  const [diag, setDiag] = useState<{ host: string; bot: string } | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(email, password, totp);
      router.push("/dashboard");
    } catch (err: any) {
      if (err.code === "2fa_required") {
        setNeedTotp(true);
        setError("Введите код двухфакторной аутентификации");
      } else {
        setError(err.message || "Ошибка входа");
      }
    } finally {
      setLoading(false);
    }
  };

  /** Exchange an OAuth/widget payload for our JWT pair. */
  const exchange = async (path: string, body: unknown) => {
    setError(null);
    const res = await fetch(`/api/v1/auth/${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const j = await res.json().catch(() => ({}));
      setError(j?.error?.message || "Не удалось войти");
      return;
    }
    const data = await res.json();
    setTokens(data.access_token, data.refresh_token);
    router.push("/dashboard");
  };

  /**
   * Telegram Login Widget.
   *
   * The widget needs the bot username and a domain authorised in BotFather
   * (``/setdomain``). It calls ``window.onTelegramAuth`` with signed user data,
   * which we forward to the backend for HMAC verification.
   */
  const loginTelegram = () => {
    // Username without a leading @ — Telegram rejects "@name".
    const botUser = (process.env.NEXT_PUBLIC_TELEGRAM_BOT_USERNAME || "").replace(/^@/, "").trim();
    if (!botUser) {
      setError("Не задан NEXT_PUBLIC_TELEGRAM_BOT_USERNAME (см. docs/AUTH.md)");
      return;
    }
    const container = document.getElementById("tg-login-widget");
    if (!container) return;
    if (container.childElementCount > 0) return;
    // Inject the official widget button; it handles the popup itself.
    // NOTE: Telegram shows "Bot domain invalid" here until the current site
    // domain is registered for the bot in @BotFather via /setdomain.
    const s = document.createElement("script");
    s.async = true;
    s.src = "https://telegram.org/js/telegram-widget.js?22";
    s.setAttribute("data-telegram-login", botUser);
    s.setAttribute("data-size", "large");
    s.setAttribute("data-userpic", "false");
    s.setAttribute("data-request-access", "write");
    s.setAttribute("data-onauth", "onTelegramAuth(user)");
    container.appendChild(s);
  };

  // Handle OAuth redirects (Yandex/VK) and expose the Telegram callback.
  useEffect(() => {
    if (typeof window === "undefined") return;

    // Telegram widget calls this global with the signed user object.
    (window as unknown as { onTelegramAuth?: (u: unknown) => void }).onTelegramAuth = (user) => {
      if (user) exchange("telegram", user);
      else setError("Вход через Telegram отменён");
    };

    // Record what the widget will use, so a domain/username mismatch is visible.
    setDiag({
      host: window.location.hostname,
      bot: (process.env.NEXT_PUBLIC_TELEGRAM_BOT_USERNAME || "").replace(/^@/, "").trim(),
    });

    // Auto-embed the official Telegram Login Widget button on mount.
    loginTelegram();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted p-4">
      <form onSubmit={submit} className="card w-full max-w-sm space-y-4 p-8">
        <div className="flex items-center justify-center gap-2">
          <ImageIcon className="h-7 w-7 text-primary" />
          <span className="text-xl font-semibold tracking-wide">SNEWS</span>
        </div>
        <p className="text-center text-sm text-muted-foreground">Панель администратора</p>

        {error && <p className="rounded-md bg-red-50 p-2 text-sm text-red-600">{error}</p>}

        <input
          className="input"
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <input
          className="input"
          type="password"
          placeholder="Пароль"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        {needTotp && (
          <input
            className="input"
            placeholder="Код 2FA"
            value={totp}
            onChange={(e) => setTotp(e.target.value)}
            maxLength={6}
          />
        )}
        <button className="btn-primary w-full" disabled={loading}>
          {loading ? "Вход…" : "Войти"}
        </button>

        <div className="relative py-2">
          <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-border" /></div>
          <div className="relative flex justify-center">
            <span className="bg-card px-2 text-xs text-muted-foreground">или войти через Telegram</span>
          </div>
        </div>

        {/* Official Telegram Login Widget button. */}
        <div id="tg-login-widget" className="flex justify-center" />
        <p className="text-center text-[11px] text-muted-foreground">
          Аккаунт должен быть привязан администратором по Telegram.
        </p>
        <p className="text-center text-[11px] text-muted-foreground/70">
          Если вместо кнопки — «Bot domain invalid»: в @BotFather → /setdomain укажите
          <b> только домен</b> (без https:// и без /login).
        </p>
        {diag && (
          <p className="text-center text-[10px] text-muted-foreground/60">
            Домен для /setdomain: <b>{diag.host || "—"}</b> · бот:{" "}
            <b>{diag.bot ? "@" + diag.bot : "не задан"}</b>
          </p>
        )}
      </form>
    </div>
  );
}
