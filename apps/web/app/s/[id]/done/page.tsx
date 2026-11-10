"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, errorMessage, type ExportResult } from "../../../../lib/api";
import FeedbackWidget from "../../../../components/FeedbackWidget";

export const dynamic = "force-dynamic";

export default function DonePage() {
  const params = useParams();
  const sid = params.id as string;
  const [result, setResult] = useState<ExportResult | null>(null);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    // Idempotent: returns the existing submission when nothing changed.
    api
      .exportSession(sid)
      .then(setResult)
      .catch((e) => setError(errorMessage(e)));
  }, [sid]);

  const copy = async () => {
    if (!result) return;
    try {
      await navigator.clipboard.writeText(result.share_text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setError("Copy failed — long-press the text to copy it manually.");
    }
  };

  if (error) {
    return (
      <div className="mx-auto max-w-xl space-y-3 py-6">
        <p className="rounded-xl bg-red-50 p-4 font-bold text-red-800" role="alert">
          {error}
        </p>
        <a href={`/s/${sid}/review`} className="font-bold text-teal-800 underline">
          ← Back to review
        </a>
      </div>
    );
  }

  if (!result) return <p className="py-10 text-center text-slate-600">Preparing your PDF…</p>;

  const wa = `https://wa.me/?text=${encodeURIComponent(result.share_text)}`;
  const x = `https://twitter.com/intent/tweet?text=${encodeURIComponent(result.share_text)}`;
  const li = `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(result.pdf_url)}`;

  return (
    <div className="mx-auto max-w-xl space-y-5">
      <div className="text-center">
        <p className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-teal-700 text-3xl font-extrabold text-white">
          ✓
        </p>
        <h1 className="mt-3 text-3xl font-extrabold tracking-tight text-slate-950">
          Your form is ready.
        </h1>
        <p className="mt-1 text-lg text-slate-600">
          Download it, print it, or submit it wherever it&apos;s needed.
        </p>
      </div>

      <a
        href={result.pdf_url}
        download
        className="block min-h-[56px] rounded-xl bg-teal-700 px-6 py-4 text-center text-lg font-bold text-white hover:bg-teal-800"
      >
        Download filled PDF
      </a>

      <div className="rounded-xl border border-slate-300 bg-white p-4">
        <h2 className="font-bold text-slate-900">Tell a friend who wrestles with forms</h2>
        <p className="mt-1 rounded-lg bg-slate-50 p-3 text-sm text-slate-700">{result.share_text}</p>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <a
            href={wa}
            target="_blank"
            rel="noreferrer"
            className="min-h-[48px] rounded-lg bg-slate-900 px-3 py-3 text-center font-bold text-white"
          >
            WhatsApp
          </a>
          <a
            href={x}
            target="_blank"
            rel="noreferrer"
            className="min-h-[48px] rounded-lg bg-slate-900 px-3 py-3 text-center font-bold text-white"
          >
            Post on X
          </a>
          <a
            href={li}
            target="_blank"
            rel="noreferrer"
            className="min-h-[48px] rounded-lg bg-slate-900 px-3 py-3 text-center font-bold text-white"
          >
            LinkedIn
          </a>
          <button
            type="button"
            onClick={copy}
            className="min-h-[48px] rounded-lg border-2 border-slate-300 px-3 font-bold text-slate-800"
          >
            {copied ? "Copied!" : "Copy text"}
          </button>
        </div>
      </div>

      <FeedbackWidget sessionId={sid} />

      <a href="/" className="block text-center font-bold text-teal-800 underline">
        Fill another form →
      </a>
    </div>
  );
}
