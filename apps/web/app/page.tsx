"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, errorMessage, type TemplateSummary } from "../lib/api";
import LanguageSwitch from "../components/LanguageSwitch";

const DEMO_ANSWERS = ["Aarav Sharma", "12th March 2004"];

export default function Home() {
  const router = useRouter();
  const [templates, setTemplates] = useState<TemplateSummary[]>([]);
  const [language, setLanguage] = useState("en");
  const [photoFirst, setPhotoFirst] = useState(false);
  const [busy, setBusy] = useState<"start" | "demo" | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.templates().then(setTemplates).catch((e) => setError(errorMessage(e)));
  }, []);

  const template = templates[0];

  const start = async () => {
    if (!template || busy) return;
    setBusy("start");
    setError("");
    try {
      const s = await api.createSession(template.id, language);
      router.push(`/s/${s.session_id}${photoFirst ? "?photo=1" : ""}`);
    } catch (e) {
      setError(errorMessage(e));
      setBusy(null);
    }
  };

  const demo = async () => {
    if (!template || busy) return;
    setBusy("demo");
    setError("");
    try {
      const s = await api.createSession(template.id, "en");
      for (const text of DEMO_ANSWERS) {
        const a = await api.answerText(s.session_id, text);
        if (a.needs_clarify) throw new Error("demo setup stumbled — please try Start instead");
        await api.confirm(s.session_id, true);
      }
      router.push(`/s/${s.session_id}?demo=1`);
    } catch (e) {
      setError(errorMessage(e));
      setBusy(null);
    }
  };

  return (
    <div className="grid gap-8 py-4 md:grid-cols-2 md:gap-12">
      <div>
        <h1 className="text-4xl font-extrabold leading-tight tracking-tight text-slate-950 md:text-5xl">
          Fill any form by speaking.
        </h1>
        <p className="mt-3 text-lg leading-relaxed text-slate-700">
          SpeakFill asks each question aloud in your language, understands your spoken answers,
          reads every field back for confirmation, and hands you a filled, ready-to-submit PDF.
        </p>

        <div className="mt-6 max-w-xs">
          <span className="mb-1 block text-sm font-bold text-slate-800">Your language</span>
          <LanguageSwitch value={language} onChange={setLanguage} />
        </div>

        <label className="mt-4 flex min-h-[48px] cursor-pointer items-center gap-3 text-base font-medium text-slate-800">
          <input
            type="checkbox"
            checked={photoFirst}
            onChange={(e) => setPhotoFirst(e.target.checked)}
            className="h-5 w-5 accent-teal-700"
          />
          I have a paper form — photograph it first
        </label>

        <div className="mt-4 flex flex-col gap-3 sm:flex-row">
          <button
            type="button"
            onClick={start}
            disabled={busy !== null || !template}
            className="min-h-[56px] flex-1 rounded-xl bg-teal-700 px-6 text-lg font-bold text-white hover:bg-teal-800 disabled:opacity-40"
          >
            {busy === "start" ? "Starting…" : "Start my form"}
          </button>
          <button
            type="button"
            onClick={demo}
            disabled={busy !== null || !template}
            className="min-h-[56px] flex-1 rounded-xl border-2 border-slate-800 bg-white px-6 text-lg font-bold text-slate-900 hover:bg-slate-100 disabled:opacity-40"
          >
            {busy === "demo" ? "Preparing…" : "▶ 60-second demo"}
          </button>
        </div>
        {error && (
          <p className="mt-3 rounded-lg bg-red-50 p-3 text-sm font-bold text-red-800" role="alert">
            {error}
          </p>
        )}
        {!template && !error && <p className="mt-3 text-sm text-slate-600">Loading…</p>}
      </div>

      <div className="space-y-6">
        <section aria-label="How it works" className="rounded-xl border border-slate-300 bg-white p-5">
          <h2 className="text-lg font-extrabold text-slate-900">How it works</h2>
          <ol className="mt-3 space-y-4">
            {[
              ["Speak", "Answer each question in your own words — English or Hindi. No typing needed."],
              ["Confirm", "SpeakFill reads every answer back. Say yes, or correct it on the spot."],
              ["Done", "Review the full form, hear it read aloud, and download your filled PDF."],
            ].map(([title, body], i) => (
              <li key={title} className="flex gap-3">
                <span
                  aria-hidden="true"
                  className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-teal-700 text-base font-extrabold text-white"
                >
                  {i + 1}
                </span>
                <div>
                  <p className="font-bold text-slate-900">{title}</p>
                  <p className="text-slate-600">{body}</p>
                </div>
              </li>
            ))}
          </ol>
        </section>

        {template && (
          <section aria-label="Available form" className="rounded-xl bg-slate-900 p-5 text-white">
            <p className="text-sm font-bold uppercase tracking-wider text-teal-300">Today&apos;s form</p>
            <p className="mt-1 text-xl font-extrabold">{template.name[language] ?? template.name.en}</p>
            <p className="mt-1 text-slate-300">
              {template.field_count} fields · about 5 minutes by voice · English and Hindi
            </p>
          </section>
        )}
      </div>
    </div>
  );
}
