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

  /** Yandex implicit-grant flow: token arrives in the URL fragment. */
  const loginYandex = () => {
    const clientId = process.env.NEXT_PUBLIC_YANDEX_CLIENT_ID;
    if (!clientId) {
      setError("Не задан NEXT_PUBLIC_YANDEX_CLIENT_ID");
      return;
    }
    const redirect = `${window.location.origin}/login`;
    window.location.href =
      `https://oauth.yandex.ru/authorize?response_type=token&client_id=${clientId}` +
      `&redirect_uri=${encodeURIComponent(redirect)}`;
  };

  /** VK implicit-grant flow: token arrives in the URL fragment. */
  const loginVK = () => {
    const clientId = process.env.NEXT_PUBLIC_VK_CLIENT_ID;
    if (!clientId) {
      setError("Не задан NEXT_PUBLIC_VK_CLIENT_ID (см. docs/AUTH.md)");
      return;
    }
    const redirect = `${window.location.origin}/login`;
    window.location.href =
      `https://oauth.vk.com/authorize?client_id=${clientId}&display=page` +
      `&redirect_uri=${encodeURIComponent(redirect)}` +
      `&scope=email&response_type=token&v=5.199`;
  };

  /**
   * Telegram Login Widget.
   *
   * The widget needs the bot username and a domain authorised in BotFather
   * (``/setdomain``). It calls ``window.onTelegramAuth`` with signed user data,
   * which we forward to the backend for HMAC verification.
   */
  const loginTelegram = () => {
    const botUser = process.env.NEXT_PUBLIC_TELEGRAM_BOT_USERNAME;
    if (!botUser) {
      setError("Не задан NEXT_PUBLIC_TELEGRAM_BOT_USERNAME (см. docs/AUTH.md)");
      return;
    }
    const container = document.getElementById("tg-login-widget");
    if (!container) return;
    if (container.childElementCount > 0) {
      setError("Нажмите кнопку Telegram ниже, чтобы подтвердить вход");
      return;
    }
    // Inject the official widget button; it handles the popup itself.
    const s = document.createElement("script");
    s.async = true;
    s.src = "https://telegram.org/js/telegram-widget.js?22";
    s.setAttribute("data-telegram-login", botUser);
    s.setAttribute("data-size", "large");
    s.setAttribute("data-userpic", "false");
    s.setAttribute("data-request-access", "write");
    s.setAttribute("data-onauth", "onTelegramAuth(user)");
    container.appendChild(s);
    setError("Нажмите появившуюся кнопку «Log in with Telegram»");
  };

  // Handle OAuth redirects (Yandex/VK) and expose the Telegram callback.
  useEffect(() => {
    if (typeof window === "undefined") return;

    // Telegram widget calls this global with the signed user object.
    (window as unknown as { onTelegramAuth?: (u: unknown) => void }).onTelegramAuth = (user) => {
      if (user) exchange("telegram", user);
      else setError("Вход через Telegram отменён");
    };

    const hash = window.location.hash;
    if (hash.includes("access_token=")) {
      const params = new URLSearchParams(hash.slice(1));
      const token = params.get("access_token");
      if (token) {
        window.history.replaceState({}, "", window.location.pathname);
        // VK returns user_id (and optionally email); Yandex does not.
        const vkUserId = params.get("user_id");
        if (vkUserId) {
          exchange("vk", {
            access_token: token,
            user_id: Number(vkUserId),
            email: params.get("email"),
          });
        } else {
          exchange("yandex", { access_token: token });
        }
      }
    }
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
            <span className="bg-card px-2 text-xs text-muted-foreground">или войти через</span>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-2">
          <button type="button" className="btn-outline" onClick={loginYandex}>
            Яндекс
          </button>
          <button type="button" className="btn-outline" onClick={loginVK}>
            VK
          </button>
          <button type="button" className="btn-outline" onClick={loginTelegram}>
            Telegram
          </button>
        </div>
        {/* Telegram Login Widget renders its own button here as a fallback. */}
        <div id="tg-login-widget" className="flex justify-center" />
        <p className="text-center text-[11px] text-muted-foreground">
          Аккаунт должен быть привязан администратором (Telegram ID / Яндекс ID / VK ID).
        </p>
      </form>
    </div>
  );
}
