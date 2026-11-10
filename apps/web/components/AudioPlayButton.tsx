"use client";

import { useState } from "react";
import { playUrl, stopPlayback } from "../lib/audio";

export default function AudioPlayButton({
  url,
  label,
  small,
}: {
  url: string | null;
  label: string;
  small?: boolean;
}) {
  const [playing, setPlaying] = useState(false);
  if (!url) return null;
  const toggle = async () => {
    if (playing) {
      stopPlayback();
      setPlaying(false);
      return;
    }
    setPlaying(true);
    try {
      await playUrl(url);
    } catch {
      /* user gesture required or load failed; button simply stops */
    } finally {
      setPlaying(false);
    }
  };
  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={playing ? "Stop" : label}
      className={`inline-flex items-center gap-2 rounded-full font-semibold transition-colors ${
        small ? "px-3 py-1.5 text-sm" : "min-h-[48px] px-5 text-base"
      } ${playing ? "bg-amber-500 text-slate-950" : "bg-teal-700 text-white hover:bg-teal-800"}`}
    >
      <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
        {playing ? (
          <rect x="3" y="2.5" width="10" height="11" rx="1.5" />
        ) : (
          <path d="M4 2.3v11.4c0 .8.9 1.3 1.6.9l8.4-5.7c.6-.4.6-1.4 0-1.8L5.6 1.4c-.7-.4-1.6.1-1.6.9z" />
        )}
      </svg>
      {playing ? "Stop" : label}
    </button>
  );
}
