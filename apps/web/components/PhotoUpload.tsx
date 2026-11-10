"use client";

import { useEffect, useRef, useState } from "react";
import { api, errorMessage, type JobResult } from "../lib/api";

const MAX_BYTES = 8 * 1024 * 1024;

export default function PhotoUpload({
  sessionId,
  onDone,
}: {
  sessionId: string;
  onDone: () => void;
}) {
  const [status, setStatus] = useState<"idle" | "uploading" | "working" | "done" | "error">("idle");
  const [message, setMessage] = useState("");
  const [mapped, setMapped] = useState(0);
  const [unknown, setUnknown] = useState(0);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(
    () => () => {
      if (timer.current) clearInterval(timer.current);
    },
    []
  );

  const poll = (jobId: string) => {
    const started = Date.now();
    timer.current = setInterval(async () => {
      if (Date.now() - started > 30000) {
        if (timer.current) clearInterval(timer.current);
        setStatus("error");
        setMessage("Timed out waiting. Please try again.");
        return;
      }
      try {
        const job: JobResult = await api.getJob(jobId);
        if (job.status === "done") {
          if (timer.current) clearInterval(timer.current);
          setMapped(job.result?.fields.length ?? 0);
          setUnknown(job.result?.unknown.length ?? 0);
          setStatus("done");
          onDone();
        } else if (job.status === "failed") {
          if (timer.current) clearInterval(timer.current);
          setStatus("error");
          setMessage(job.error || "Could not read that photo. Try a clearer picture.");
        }
      } catch (e) {
        if (timer.current) clearInterval(timer.current);
        setStatus("error");
        setMessage(errorMessage(e));
      }
    }, 1000);
  };

  const onFile = async (file: File | undefined) => {
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      setStatus("error");
      setMessage("That file is not an image. Please choose a photo.");
      return;
    }
    if (file.size > MAX_BYTES) {
      setStatus("error");
      setMessage("Photo is larger than 8 MB. Please use a smaller one.");
      return;
    }
    setStatus("uploading");
    setMessage("");
    try {
      const { job_id } = await api.uploadPhoto(sessionId, file);
      setStatus("working");
      poll(job_id);
    } catch (e) {
      setStatus("error");
      setMessage(errorMessage(e));
    }
  };

  return (
    <div className="rounded-xl border border-slate-300 bg-white p-4">
      <h3 className="text-base font-bold text-slate-900">Photograph a paper form</h3>
      <p className="mt-1 text-sm text-slate-600">
        We&apos;ll pre-fill whatever the camera can read. You&apos;ll still confirm each field by voice.
      </p>
      {status === "done" ? (
        <p className="mt-3 rounded-lg bg-teal-50 p-3 text-sm font-bold text-teal-900">
          Pre-filled {mapped} field{mapped === 1 ? "" : "s"}
          {unknown > 0 ? ` (${unknown} line${unknown === 1 ? "" : "s"} couldn't be mapped)` : ""}. Now
          confirm each one below.
        </p>
      ) : (
        <label className="mt-3 flex min-h-[52px] cursor-pointer items-center justify-center gap-2 rounded-xl border-2 border-dashed border-slate-400 bg-slate-50 px-4 font-bold text-slate-800 hover:bg-slate-100">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <path d="M4 8h3l2-3h6l2 3h3v11H4V8z" strokeLinejoin="round" />
            <circle cx="12" cy="13" r="3.5" />
          </svg>
          {status === "uploading" || status === "working" ? "Reading photo…" : "Take or choose a photo"}
          <input
            type="file"
            accept="image/*"
            capture="environment"
            className="hidden"
            disabled={status === "uploading" || status === "working"}
            onChange={(e) => onFile(e.target.files?.[0])}
          />
        </label>
      )}
      {(status === "uploading" || status === "working") && (
        <p className="mt-2 text-sm font-medium text-slate-600" role="status">
          Reading your photo — this takes a few seconds…
        </p>
      )}
      {status === "error" && (
        <p className="mt-2 rounded-lg bg-red-50 p-3 text-sm font-bold text-red-800" role="alert">
          {message}
        </p>
      )}
    </div>
  );
}
