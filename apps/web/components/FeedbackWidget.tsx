"use client";

import { useState } from "react";
import { api, errorMessage } from "../lib/api";

const COUNTRIES = ["India", "United States", "Spain", "Germany", "UAE", "Kenya", "Nigeria", "Other"];

export default function FeedbackWidget({ sessionId }: { sessionId: string }) {
  const [country, setCountry] = useState("");
  const [rating, setRating] = useState(0);
  const [comment, setComment] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!country.trim() || rating === 0) {
      setError("Please pick your country and tap a star rating.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await api.submitFeedback(sessionId, country.trim(), rating, comment.trim() || undefined);
      setSent(true);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  if (sent) {
    return (
      <p className="rounded-xl bg-teal-50 p-4 text-center font-bold text-teal-900">
        Thank you! Your feedback helps us improve.
      </p>
    );
  }

  return (
    <div className="rounded-xl border border-slate-300 bg-white p-4">
      <h3 className="text-base font-bold text-slate-900">Quick feedback (30 seconds)</h3>
      <label className="mt-3 block text-sm font-bold text-slate-800">
        Country
        <input
          value={country}
          onChange={(e) => setCountry(e.target.value)}
          list="feedback-countries"
          placeholder="e.g. India"
          className="mt-1 block min-h-[48px] w-full rounded-lg border-2 border-slate-300 px-3 text-base font-normal"
        />
        <datalist id="feedback-countries">
          {COUNTRIES.map((c) => (
            <option key={c} value={c} />
          ))}
        </datalist>
      </label>
      <div className="mt-3">
        <span className="text-sm font-bold text-slate-800">Rating</span>
        <div className="mt-1 flex gap-1" role="radiogroup" aria-label="Rating out of 5">
          {[1, 2, 3, 4, 5].map((n) => (
            <button
              key={n}
              type="button"
              role="radio"
              aria-checked={rating === n}
              aria-label={`${n} star${n === 1 ? "" : "s"}`}
              onClick={() => setRating(n)}
              className="min-h-[48px] min-w-[48px] text-3xl leading-none"
            >
              <span className={n <= rating ? "text-amber-500" : "text-slate-300"}>★</span>
            </button>
          ))}
        </div>
      </div>
      <label className="mt-3 block text-sm font-bold text-slate-800">
        Comment <span className="font-normal text-slate-500">(optional)</span>
        <textarea
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          rows={2}
          placeholder="What worked? What didn't?"
          className="mt-1 block w-full rounded-lg border-2 border-slate-300 px-3 py-2 text-base font-normal"
        />
      </label>
      {error && (
        <p className="mt-2 text-sm font-bold text-red-700" role="alert">
          {error}
        </p>
      )}
      <button
        type="button"
        onClick={submit}
        disabled={busy}
        className="mt-3 min-h-[52px] w-full rounded-xl bg-teal-700 text-lg font-bold text-white hover:bg-teal-800 disabled:opacity-40"
      >
        {busy ? "Sending…" : "Send feedback"}
      </button>
    </div>
  );
}
