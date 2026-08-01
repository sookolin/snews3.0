"use client";

/**
 * Web Push helpers for the admin PWA.
 *
 * iOS only exposes the Push API to sites added to the home screen, so
 * `pushState().supported` is false in plain Safari — the cabinet shows an
 * instruction instead of a toggle in that case.
 */

import { api } from "./api";

const SW_PATH = "/sw.js";

/** Convert the server's base64url VAPID key to the Uint8Array the API wants. */
function urlBase64ToUint8Array(base64: string): Uint8Array {
  const padded = (base64 + "=".repeat((4 - (base64.length % 4)) % 4))
    .replace(/-/g, "+")
    .replace(/_/g, "/");
  const raw = window.atob(padded);
  const out = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out;
}

function supported(): boolean {
  return (
    typeof window !== "undefined" &&
    "serviceWorker" in navigator &&
    "PushManager" in window &&
    "Notification" in window
  );
}

async function registration(): Promise<ServiceWorkerRegistration> {
  return navigator.serviceWorker.register(SW_PATH);
}

/** Whether push can work here and whether this device is already subscribed. */
export async function pushState(): Promise<{ supported: boolean; subscribed: boolean }> {
  if (!supported()) return { supported: false, subscribed: false };
  try {
    const reg = await registration();
    const sub = await reg.pushManager.getSubscription();
    return { supported: true, subscribed: sub !== null };
  } catch {
    return { supported: false, subscribed: false };
  }
}

/** Ask for permission, subscribe the device and register it on the server. */
export async function subscribePush(): Promise<void> {
  if (!supported()) throw new Error("Браузер не поддерживает push-уведомления");
  const permission = await Notification.requestPermission();
  if (permission !== "granted") throw new Error("Уведомления запрещены в настройках браузера");

  const { key } = await api<{ key: string }>("/profile/push/key");
  const reg = await registration();
  const sub =
    (await reg.pushManager.getSubscription()) ??
    (await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(key),
    }));

  const json = sub.toJSON() as { endpoint?: string; keys?: Record<string, string> };
  await api("/profile/push", {
    method: "POST",
    body: JSON.stringify({ endpoint: json.endpoint, keys: json.keys ?? {} }),
  });
}

/** Ask the server to send a test push to every registered device.
 *
 * Bypasses the per-event preferences so the user can confirm delivery works
 * regardless of which events they enabled. Returns the human-readable result
 * message from the backend. */
export async function sendTestPush(): Promise<string> {
  const r = await api<{ detail: string }>("/profile/push/test", { method: "POST" });
  return r.detail;
}

/** Regenerate the server VAPID key pair (super-admin only).
 *
 * Recovers from a corrupt/mismatched key. All existing subscriptions are
 * invalidated server-side, so this also unsubscribes the current device and
 * re-subscribes it against the freshly generated key. */
export async function resetPushKeys(): Promise<string> {
  const r = await api<{ detail: string }>("/profile/push/reset", { method: "POST" });
  // Old local subscription is now bound to a dead key — drop and recreate it.
  try {
    await unsubscribePush();
    await subscribePush();
  } catch {
    /* the user can re-enable manually if re-subscribe fails */
  }
  return r.detail;
}

/** Drop this device locally and on the server. */
export async function unsubscribePush(): Promise<void> {
  if (!supported()) return;
  const reg = await registration();
  const sub = await reg.pushManager.getSubscription();
  const endpoint = sub?.endpoint;
  if (sub) await sub.unsubscribe();
  await api(`/profile/push${endpoint ? `?endpoint=${encodeURIComponent(endpoint)}` : ""}`, {
    method: "DELETE",
  });
}
