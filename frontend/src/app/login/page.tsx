"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { login } from "@/lib/api";
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

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted p-4">
      <form onSubmit={submit} className="card w-full max-w-sm space-y-4 p-8">
        <div className="flex items-center justify-center gap-2">
          <ImageIcon className="h-7 w-7 text-primary" />
          <span className="text-xl font-semibold">CityNews</span>
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
      </form>
    </div>
  );
}
