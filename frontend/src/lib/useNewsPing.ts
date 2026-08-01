"use client";

import { useEffect, useRef } from "react";
import useSWR from "swr";
import { fetcher } from "@/lib/api";

interface CountResponse {
  total: number;
}

/** Play a short two-tone ping (identical to BellButton.playPing). */
function playPing() {
  try {
    const ctx = new (
      window.AudioContext ??
      (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext
    )();
    const play = (freq: number, start: number, dur: number) => {
      const osc  = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.frequency.value = freq;
      osc.type = "sine";
      gain.gain.setValueAtTime(0.18, ctx.currentTime + start);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + start + dur);
      osc.start(ctx.currentTime + start);
      osc.stop(ctx.currentTime + start + dur);
    };
    play(880,  0,    0.12);
    play(1100, 0.13, 0.10);
  } catch {
    // Audio blocked or unsupported — silently skip.
  }
}

/**
 * Polls the pending-news count every 30 s and plays a ping whenever the
 * number increases (i.e. new items were parsed and are waiting for moderation).
 */
export function useNewsPing() {
  const prev = useRef<number | null>(null);

  const { data } = useSWR<CountResponse>(
    "/news?status=pending&size=1",
    fetcher,
    { refreshInterval: 30_000, revalidateOnFocus: false },
  );

  useEffect(() => {
    if (data == null) return;
    const total = data.total;
    if (prev.current !== null && total > prev.current) {
      playPing();
    }
    prev.current = total;
  }, [data]);
}
