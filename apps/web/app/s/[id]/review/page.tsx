"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api, errorMessage, type Review } from "../../../../lib/api";
import AudioPlayButton from "../../../../components/AudioPlayButton";

export const dynamic = "force-dynamic";

const SOURCE_STYLES: Record<string, string> = {
  voice: "bg-teal-700 text-white",
  photo: "bg-sky-700 text-white",
  typed: "bg-slate-600 text-white",
  demo: "bg-amber-600 text-white",
};

export default function ReviewPage() {
  const params = useParams();
  const sid = params.id as string;
  const router = useRouter();
  const [review, setReview] = useState<Review | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<"export" | "restart" | null>(null);
  const [editingOrd, setEditingOrd] = useState<number | null>(null);

  const load = useCallback(async () => {
    try {
      setReview(await api.getReview(sid));
    } catch (e) {
      setError(errorMessage(e));
    }
  }, [sid]);

  useEffect(() => {
    load();
  }, [load]);

  const edit = async (ord: number) => {
    setEditingOrd(ord);
    try {
      await api.goto(sid, ord);
      router.push(`/s/${sid}`);
    } catch (e) {
      setError(errorMessage(e));
      setEditingOrd(null);
    }
  };

  const doExport = async () => {
    setBusy("export");
    setError("");
    try {
      await api.exportSession(sid);
      router.push(`/s/${sid}/done`);
    } catch (e) {
      setError(errorMessage(e));
      setBusy(null);
    }
  };

  const restart = async () => {
    setBusy("restart");
    try {
      await api.restart(sid);
      router.push(`/s/${sid}`);
    } catch (e) {
      setError(errorMessage(e));
      setBusy(null);
    }
  };

  if (error && !review) {
    return (
      <p className="mx-auto max-w-2xl rounded-xl bg-red-50 p-4 font-bold text-red-800" role="alert">
        {error}
      </p>
    );
  }
  if (!review) return <p className="py-10 text-center text-slate-600">Loading your form…</p>;

  const consentDeclined = review.block_reasons.some((r) => r.includes("consent"));

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <div>
        <h1 className="text-3xl font-extrabold tracking-tight text-slate-950">Review your form</h1>
        <p className="mt-1 text-slate-600">
          {review.template.name[review.language] ?? review.template.id} ·{" "}
          {review.fields.filter((f) => f.confirmed).length} of {review.fields.length} confirmed
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        <AudioPlayButton url={review.readback_audio_url} label="Read everything aloud" />
      </div>

      {review.blocked && (
        <div className="rounded-xl bg-amber-50 p-4" role="alert">
          <p className="font-bold text-amber-900">
            {consentDeclined
              ? "You declined the declaration, so this form can't be submitted."
              : "This form isn't ready to submit yet."}
          </p>
          {!consentDeclined && (
            <ul className="mt-1 list-disc pl-5 text-amber-900">
              {review.block_reasons.map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
          )}
          {consentDeclined && (
            <button
              type="button"
              onClick={restart}
              disabled={busy !== null}
              className="mt-3 min-h-[52px] w-full rounded-xl bg-amber-500 text-lg font-bold text-slate-950 disabled:opacity-40"
            >
              {busy === "restart" ? "Restarting…" : "Start over"}
            </button>
          )}
        </div>
      )}

      <ol className="divide-y divide-slate-200 rounded-xl border border-slate-300 bg-white">
        {review.fields.map((f) => (
          <li key={f.key} className="flex items-start gap-3 px-4 py-3">
            <div className="min-w-0 flex-1">
              <p className="text-sm font-bold text-slate-800">{f.label}</p>
              <p className="break-words text-lg font-medium text-slate-950">
                {f.readable ?? "—"}
              </p>
              <p className="mt-1 flex flex-wrap items-center gap-2 text-xs">
                {f.source && (
                  <span
                    className={`rounded-full px-2 py-0.5 font-bold uppercase ${SOURCE_STYLES[f.source] ?? "bg-slate-500 text-white"}`}
                  >
                    {f.source}
                  </span>
                )}
                {f.confirmed ? (
                  <span className="font-bold uppercase text-teal-700">confirmed</span>
                ) : (
                  <span className="font-bold uppercase text-amber-700">needs answer</span>
                )}
              </p>
            </div>
            <button
              type="button"
              onClick={() => edit(f.ord)}
              disabled={editingOrd !== null}
              className="min-h-[44px] shrink-0 rounded-lg border-2 border-slate-300 px-4 font-bold text-slate-700 hover:bg-slate-100 disabled:opacity-40"
            >
              {editingOrd === f.ord ? "…" : "Edit"}
            </button>
          </li>
        ))}
      </ol>

      {error && (
        <p className="rounded-xl bg-red-50 p-3 text-sm font-bold text-red-800" role="alert">
          {error}
        </p>
      )}

      <button
        type="button"
        onClick={doExport}
        disabled={busy !== null || !review.can_export}
        className="min-h-[56px] w-full rounded-xl bg-teal-700 text-lg font-bold text-white hover:bg-teal-800 disabled:opacity-40"
      >
        {busy === "export" ? "Creating your PDF…" : "Finish — get my PDF"}
      </button>
      <a href={`/s/${sid}`} className="block text-center font-bold text-teal-800 underline">
        ← Back to questions
      </a>
    </div>
  );
}
