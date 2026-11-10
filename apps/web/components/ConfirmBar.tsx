"use client";

import type { AnswerResult } from "../lib/api";
import AudioPlayButton from "./AudioPlayButton";
import VoiceRecorder from "./VoiceRecorder";

export default function ConfirmBar({
  answer,
  onConfirm,
  onVoiceConfirm,
  busy,
}: {
  answer: AnswerResult;
  onConfirm: (accepted: boolean) => void;
  onVoiceConfirm: (blob: Blob) => void;
  busy: boolean;
}) {
  return (
    <div className="rounded-xl border-2 border-teal-600 bg-teal-50 p-4">
      <p className="text-sm font-bold uppercase tracking-wide text-teal-800">Please confirm</p>
      <p className="mt-1 text-xl font-bold text-slate-950">
        &ldquo;{answer.readable || "(empty)"}&rdquo;
      </p>
      {answer.transcript && (
        <p className="mt-1 text-sm text-slate-600">
          Heard: <span className="font-medium">{answer.transcript}</span>
        </p>
      )}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <button
          type="button"
          disabled={busy}
          onClick={() => onConfirm(true)}
          className="min-h-[52px] flex-1 rounded-xl bg-teal-700 px-6 text-lg font-bold text-white hover:bg-teal-800 disabled:opacity-40"
        >
          Yes, correct
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => onConfirm(false)}
          className="min-h-[52px] flex-1 rounded-xl border-2 border-slate-400 bg-white px-6 text-lg font-bold text-slate-800 hover:bg-slate-100 disabled:opacity-40"
        >
          No, redo
        </button>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-3 border-t border-teal-200 pt-3">
        <AudioPlayButton small url={answer.prompt_audio_url} label="Replay" />
        <div className="flex items-center gap-2">
          <VoiceRecorder compact onBlob={onVoiceConfirm} disabled={busy} />
          <span className="text-sm font-medium text-slate-600">or say yes / no</span>
        </div>
      </div>
    </div>
  );
}
