"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { login, setTokens } from "@/lib/api";
import { Image as ImageIcon, Send } from "lucide-react";

/** Minimal shape of the Telegram OIDC login library we use. */
interface TgAuthResult {
  id_token?: string;
  user?: unknown;
  error?: string;
}
interface TgLogin {
  auth: (
    opts: { client_id: number; scope?: string[]; lang?: string; nonce?: string },
    cb: (data: TgAuthResult | null) => void
  ) => void;
  open?: (cb: (data: TgAuthResult | null) => void) => void;
}

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

  /** Bot Client ID from @BotFather (Bot Settings → Web Login). */
  const clientId = Number(process.env.NEXT_PUBLIC_TELEGRAM_CLIENT_ID || "8975133163");

  /**
   * Telegram Login (new OIDC library).
   *
   * Loads ``oauth.telegram.org/js/telegram-login.js`` and opens the login popup
   * on demand. The callback returns an ``id_token`` (signed JWT) which we send
   * to the backend for verification. The site origin must be registered under
   * @BotFather → Bot Settings → Web Login → Allowed URLs.
   */
  const loginTelegram = () => {
    const TL = (window as unknown as { Telegram?: { Login?: TgLogin } }).Telegram?.Login;
    if (!TL) {
      setError("Telegram-логин ещё загружается, попробуйте ещё раз через секунду.");
      return;
    }
    setError(null);
    TL.auth({ client_id: clientId, scope: ["profile", "write"] }, (data) => {
      if (!data) {
        setError("Вход через Telegram отменён");
        return;
      }
      if (data.error) {
        setError(`Telegram: ${data.error}`);
        return;
      }
      if (data.id_token) exchange("telegram/oidc", { id_token: data.id_token });
      else setError("Telegram не вернул токен");
    });
  };

  useEffect(() => {
    if (typeof window === "undefined") return;

    setDiag({ host: window.location.hostname, bot: String(clientId) });

    // Load the OIDC login library once.
    if (!document.getElementById("tg-oidc-script")) {
      const s = document.createElement("script");
      s.id = "tg-oidc-script";
      s.async = true;
      s.src = "https://oauth.telegram.org/js/telegram-login.js?5";
      document.head.appendChild(s);
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
            <span className="bg-card px-2 text-xs text-muted-foreground">или войти через Telegram</span>
          </div>
        </div>

        {/* Official Telegram Login Widget button. */}
        <button
          type="button"
          className="btn-outline flex w-full items-center justify-center gap-2"
          onClick={loginTelegram}
        >
          <Send className="h-4 w-4" /> Войти через Telegram
        </button>
        <p className="text-center text-[11px] text-muted-foreground">
          Аккаунт должен быть привязан администратором по Telegram.
        </p>
        <p className="text-center text-[11px] text-muted-foreground/70">
          Origin этого сайта должен быть в @BotFather → Bot Settings → Web Login →
          Allowed URLs.
        </p>
        {diag && (
          <p className="text-center text-[10px] text-muted-foreground/60">
            Origin: <b>https://{diag.host || "—"}</b> · client_id: <b>{diag.bot}</b>
          </p>
        )}
      </form>
    </div>
  );
}
