"use client";

import { useEffect, useRef, useState } from "react";
import { prefersReducedMotion } from "../lib/audio";

const MAX_SECONDS = 30;

function pickMime(): string {
  if (typeof MediaRecorder === "undefined") return "";
  const opts = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"];
  return opts.find((m) => MediaRecorder.isTypeSupported(m)) ?? "";
}

/**
 * Press-and-hold (or toggle) voice recorder with level meter, 30 s cap,
 * and a helpful mic-denied state. Calls onBlob with the finished clip.
 */
export default function VoiceRecorder({
  onBlob,
  disabled,
  compact,
  holdToTalk,
}: {
  onBlob: (blob: Blob) => void;
  disabled?: boolean;
  compact?: boolean;
  holdToTalk?: boolean;
}) {
  const [recording, setRecording] = useState(false);
  const [denied, setDenied] = useState(false);
  const [unsupported, setUnsupported] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const recRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const audioPartsRef = useRef<Blob[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const barRef = useRef<HTMLDivElement | null>(null);
  const rafRef = useRef<number>(0);
  const ctxRef = useRef<AudioContext | null>(null);

  const cleanup = () => {
    cancelAnimationFrame(rafRef.current);
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = null;
    ctxRef.current?.close().catch(() => undefined);
    ctxRef.current = null;
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    recRef.current = null;
  };

  useEffect(() => cleanup, []);

  const stop = (submit: boolean) => {
    const rec = recRef.current;
    if (!rec) return;
    rec.onstop = () => {
      const mime = rec.mimeType || "audio/webm";
      const blob = new Blob(audioPartsRef.current, { type: mime.split(";")[0] });
      cleanup();
      setRecording(false);
      setSeconds(0);
      if (submit && blob.size > 0) onBlob(blob);
    };
    try {
      rec.stop();
    } catch {
      cleanup();
      setRecording(false);
    }
  };

  const start = async () => {
    if (recording || disabled) return;
    if (typeof MediaRecorder === "undefined" || !navigator.mediaDevices?.getUserMedia) {
      setUnsupported(true);
      return;
    }
    setDenied(false);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      audioPartsRef.current = [];
      const rec = new MediaRecorder(stream, pickMime() ? { mimeType: pickMime() } : undefined);
      recRef.current = rec;
      rec.ondataavailable = (e) => {
        if (e.data.size > 0) audioPartsRef.current.push(e.data);
      };
      rec.start(250);
      setRecording(true);
      setSeconds(0);
      const t0 = Date.now();
      timerRef.current = setInterval(() => {
        const s = Math.floor((Date.now() - t0) / 1000);
        setSeconds(s);
        if (s >= MAX_SECONDS) stop(true); // auto-submit at cap
      }, 250);
      // Level meter (skipped animation when reduced motion is preferred).
      if (!prefersReducedMotion()) {
        try {
          const Ctx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
          const ctx = new Ctx();
          ctxRef.current = ctx;
          const src = ctx.createMediaStreamSource(stream);
          const analyser = ctx.createAnalyser();
          analyser.fftSize = 256;
          src.connect(analyser);
          const data = new Uint8Array(analyser.frequencyBinCount);
          const tick = () => {
            analyser.getByteFrequencyData(data);
            const avg = data.reduce((a, b) => a + b, 0) / data.length / 255;
            if (barRef.current) barRef.current.style.width = `${Math.min(100, avg * 220)}%`;
            rafRef.current = requestAnimationFrame(tick);
          };
          tick();
        } catch {
          /* meter is decorative; recording works without it */
        }
      }
    } catch {
      setDenied(true);
    }
  };

  if (unsupported) {
    return (
      <p className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm font-medium text-amber-900">
        Voice recording isn&apos;t supported in this browser. Please type your answer instead.
      </p>
    );
  }

  if (denied && !recording) {
    return (
      <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
        <p className="font-bold">Microphone blocked.</p>
        <p className="mt-1">
          Tap the lock/tune icon in the address bar, allow the microphone, then try again — or just
          type your answer below.
        </p>
        <button
          type="button"
          onClick={() => setDenied(false)}
          className="mt-2 min-h-[44px] rounded-lg bg-amber-500 px-4 font-bold text-slate-950"
        >
          Try again
        </button>
      </div>
    );
  }

  const size = compact ? "h-12 w-12" : "h-20 w-20";
  return (
    <div className="flex items-center gap-3">
      <button
        type="button"
        disabled={disabled}
        aria-label={recording ? "Stop recording" : holdToTalk ? "Hold to talk" : "Start recording"}
        aria-pressed={recording}
        onClick={() => (recording ? stop(true) : start())}
        onMouseDown={holdToTalk && !recording ? start : undefined}
        onMouseUp={holdToTalk && recording ? () => stop(true) : undefined}
        onTouchStart={holdToTalk && !recording ? start : undefined}
        onTouchEnd={holdToTalk && recording ? () => stop(true) : undefined}
        className={`${size} shrink-0 rounded-full transition-colors disabled:opacity-40 ${
          recording ? "animate-pulse bg-red-600" : "bg-teal-700 hover:bg-teal-800"
        } flex items-center justify-center text-white`}
      >
        <svg width={compact ? 20 : 30} height={compact ? 20 : 30} viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <rect x="9" y="2.5" width="6" height="11" rx="3" fill="currentColor" />
          <path d="M5.5 11v1.5a6.5 6.5 0 0 0 13 0V11" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          <line x1="12" y1="18.5" x2="12" y2="21.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        </svg>
      </button>
      <div className="min-w-0 flex-1">
        {recording ? (
          <>
            <p className="text-sm font-bold text-red-700">
              Listening… {seconds}s / {MAX_SECONDS}s
            </p>
            <div className="mt-1 h-2 overflow-hidden rounded-full bg-slate-200">
              <div ref={barRef} className="h-full rounded-full bg-red-500" style={{ width: "5%" }} />
            </div>
            <button
              type="button"
              onClick={() => stop(false)}
              className="mt-1 text-sm font-semibold text-slate-600 underline"
            >
              Cancel
            </button>
          </>
        ) : (
          <p className="text-sm font-medium text-slate-600">
            {holdToTalk ? "Hold the button and speak" : "Tap the mic and speak your answer"}
          </p>
        )}
      </div>
    </div>
  );
}
