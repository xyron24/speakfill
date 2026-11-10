"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import {
  ApiError,
  api,
  errorMessage,
  type AnswerResult,
  type SessionState,
} from "../../../lib/api";
import { playUrl, stopPlayback } from "../../../lib/audio";
import { browserSpeechSupported, listenOnce } from "../../../lib/speech";
import AudioPlayButton from "../../../components/AudioPlayButton";
import ConfirmBar from "../../../components/ConfirmBar";
import FormPreview from "../../../components/FormPreview";
import HistoryThread, { type HistoryItem } from "../../../components/HistoryThread";
import PhotoUpload from "../../../components/PhotoUpload";
import ProgressBar from "../../../components/ProgressBar";
import VoiceRecorder from "../../../components/VoiceRecorder";

export const dynamic = "force-dynamic";

type Banner = { kind: "info" | "warn" | "error"; text: string } | null;

function InterviewInner() {
  const params = useParams();
  const sid = params.id as string;
  const search = useSearchParams();
  const router = useRouter();
  const isDemo = search.get("demo") === "1";

  const [server, setServer] = useState<SessionState | null>(null);
  const [fatal, setFatal] = useState("");
  const [turn, setTurn] = useState<AnswerResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [typedMode, setTypedMode] = useState(false);
  const [typedText, setTypedText] = useState("");
  const [banner, setBanner] = useState<Banner>(null);
  const [ask, setAsk] = useState<{ url: string | null; text: string }>({ url: null, text: "" });
  const [needTap, setNeedTap] = useState(false);
  const [showPhoto, setShowPhoto] = useState(search.get("photo") === "1");
  const [listening, setListening] = useState(false);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const historyId = useRef(0);
  const pushHistory = (role: HistoryItem["role"], text: string) => {
    historyId.current += 1;
    setHistory((h) => [...h.slice(-29), { id: historyId.current, role, text }]);
  };

  const load = useCallback(async () => {
    try {
      setServer(await api.getSession(sid));
    } catch (e) {
      setFatal(errorMessage(e));
    }
  }, [sid]);

  useEffect(() => {
    load();
  }, [load]);

  const fieldOrd = server?.current_field?.ord ?? 0;
  const fieldKey = server?.current_field?.key ?? "";
  const status = server?.status ?? "";

  // Fetch + autoplay the spoken question whenever the current field changes.
  useEffect(() => {
    if (!server?.current_field || server.status !== "active") return;
    const f = server.current_field;
    setTurn(null);
    setTypedText("");
    setBanner(null);
    setTypedMode(f.type === "email"); // typed-first field
    setNeedTap(false);
    pushHistory("assistant", f.prompt_text);
    let cancelled = false;
    api
      .promptAudio(server.template_id, f.ord, server.language)
      .then(({ audio_url, text }) => {
        if (cancelled) return;
        setAsk({ url: audio_url, text });
        playUrl(audio_url).catch(() => {
          if (!cancelled) setNeedTap(true); // browser wants a tap first
        });
      })
      .catch(() => {
        if (!cancelled) setAsk({ url: null, text: `${f.prompt_text} ${f.prompt_hint}` });
      });
    return () => {
      cancelled = true;
      stopPlayback();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fieldOrd, fieldKey, status]);

  useEffect(() => stopPlayback, []);

  const handleAnswer = (r: AnswerResult) => {
    if (r.typed_nudge) setTypedMode(true);
    if (r.transcript) pushHistory("user", r.transcript);
    pushHistory("assistant", r.next_prompt);
    if (r.needs_clarify) {
      setTurn(null);
      setBanner({ kind: "info", text: r.next_prompt });
      if (r.prompt_audio_url) playUrl(r.prompt_audio_url).catch(() => undefined);
      return;
    }
    setTurn(r);
    setBanner(null);
    if (r.prompt_audio_url) playUrl(r.prompt_audio_url).catch(() => undefined);
  };

  const submitText = async () => {
    const text = typedText.trim();
    if (!text || busy) return;
    setBusy(true);
    setBanner(null);
    try {
      handleAnswer(await api.answerText(sid, text));
    } catch (e) {
      setBanner({ kind: "error", text: errorMessage(e) });
    } finally {
      setBusy(false);
    }
  };

  const submitAudio = async (blob: Blob) => {
    setBusy(true);
    setBanner(null);
    try {
      handleAnswer(await api.answerAudio(sid, blob));
    } catch (e) {
      if (e instanceof ApiError && e.status === 502) {
        setBanner({
          kind: "warn",
          text: "The voice service is having trouble. Type your answer below, or try browser voice typing.",
        });
        setTypedMode(true);
      } else {
        setBanner({ kind: "error", text: errorMessage(e) });
      }
    } finally {
      setBusy(false);
    }
  };

  const doConfirm = async (accepted: boolean) => {
    setBusy(true);
    setBanner(null);
    try {
      const c = await api.confirm(sid, accepted);
      pushHistory("user", accepted ? "Yes" : "No");
      if (!accepted && c.next_prompt) pushHistory("assistant", c.next_prompt);
      setTurn(null);
      setTypedText("");
      await load();
      if (c.next_prompt && c.prompt_audio_url) playUrl(c.prompt_audio_url).catch(() => undefined);
    } catch (e) {
      setBanner({ kind: "error", text: errorMessage(e) });
    } finally {
      setBusy(false);
    }
  };

  const voiceConfirm = async (blob: Blob) => {
    setBusy(true);
    try {
      const c = await api.confirmAudio(sid, blob);
      setTurn(null);
      setTypedText("");
      await load();
      if (c.next_prompt && c.prompt_audio_url) playUrl(c.prompt_audio_url).catch(() => undefined);
    } catch (e) {
      if (e instanceof ApiError && e.status === 422) {
        setBanner({ kind: "warn", text: "Couldn't tell yes from no — please tap a button." });
      } else {
        setBanner({ kind: "error", text: errorMessage(e) });
      }
    } finally {
      setBusy(false);
    }
  };

  const browserVoice = async () => {
    setListening(true);
    setBanner(null);
    try {
      const text = await listenOnce(server?.language ?? "en");
      setTypedText(text);
      setBusy(true);
      try {
        handleAnswer(await api.answerText(sid, text)); // confirm step still catches mistakes
      } finally {
        setBusy(false);
      }
    } catch (e) {
      setBanner({ kind: "warn", text: errorMessage(e) });
    } finally {
      setListening(false);
    }
  };

  if (fatal) {
    return (
      <div className="mx-auto max-w-xl py-10">
        <p className="rounded-xl bg-red-50 p-4 font-bold text-red-800" role="alert">
          {fatal}
        </p>
        <a href="/" className="mt-4 inline-block font-bold text-teal-800 underline">
          ← Start over
        </a>
      </div>
    );
  }

  if (!server) return <p className="py-10 text-center text-slate-600">Loading your form…</p>;

  if (server.status === "review") {
    return (
      <div className="mx-auto max-w-xl py-10 text-center">
        <h1 className="text-3xl font-extrabold text-slate-950">All fields answered.</h1>
        <p className="mt-2 text-lg text-slate-600">
          Review everything, hear it read aloud, and get your PDF.
        </p>
        <button
          type="button"
          onClick={() => router.push(`/s/${sid}/review`)}
          className="mt-6 min-h-[56px] w-full rounded-xl bg-teal-700 text-lg font-bold text-white hover:bg-teal-800"
        >
          Continue to review →
        </button>
      </div>
    );
  }

  if (server.status === "done") {
    router.push(`/s/${sid}/done`);
    return <p className="py-10 text-center text-slate-600">Opening your finished form…</p>;
  }

  const field = server.current_field;
  const total = server.answers.length || 12;

  return (
    <div>
      {isDemo && (
        <p className="mb-4 rounded-xl bg-amber-100 p-3 text-center font-bold text-amber-900">
          Guided demo — two fields are already filled. Answer this one by voice.
        </p>
      )}
      <div className="grid gap-6 lg:grid-cols-5">
        <div className="space-y-4 lg:col-span-3">
          <ProgressBar current={server.current_ord} total={total} />

          <section aria-label="Current question" className="rounded-xl border border-slate-300 bg-white p-5">
            <h1 className="text-2xl font-extrabold leading-snug text-slate-950">
              {field?.prompt_text}
            </h1>
            {field?.prompt_hint && (
              <p className="mt-1 text-base text-slate-600">{field.prompt_hint}</p>
            )}
            {field?.options && (
              <ul className="mt-3 flex flex-wrap gap-2" aria-label="Choices">
                {field.options.map((o) => (
                  <li
                    key={o.key}
                    className="rounded-full border border-slate-300 bg-slate-50 px-3 py-1.5 text-sm font-semibold text-slate-700"
                  >
                    {o.label}
                  </li>
                ))}
              </ul>
            )}
            <div className="mt-3">
              {needTap ? (
                <button
                  type="button"
                  onClick={() => {
                    setNeedTap(false);
                    if (ask.url) playUrl(ask.url).catch(() => setNeedTap(true));
                  }}
                  className="min-h-[52px] w-full rounded-xl bg-amber-500 px-5 text-lg font-bold text-slate-950 hover:bg-amber-400"
                >
                  Tap to hear the question
                </button>
              ) : (
                <AudioPlayButton small url={ask.url} label="Replay question" />
              )}
            </div>
          </section>

          <HistoryThread items={history} />

          {turn ? (
            <ConfirmBar
              answer={turn}
              busy={busy}
              onConfirm={doConfirm}
              onVoiceConfirm={voiceConfirm}
            />
          ) : (
            <section aria-label="Your answer" className="rounded-xl border border-slate-300 bg-white p-5 max-lg:sticky max-lg:bottom-2 max-lg:shadow-xl max-lg:z-10">
              {typedMode ? (
                <div>
                  <label className="block text-sm font-bold text-slate-800" htmlFor="typed-answer">
                    Type your answer
                  </label>
                  <textarea
                    id="typed-answer"
                    value={typedText}
                    onChange={(e) => setTypedText(e.target.value)}
                    rows={field?.type === "longtext" ? 3 : 2}
                    disabled={busy}
                    placeholder="Type here…"
                    className="mt-1 block w-full rounded-lg border-2 border-slate-300 px-3 py-2 text-lg disabled:opacity-50"
                  />
                  <div className="mt-2 flex gap-2">
                    <button
                      type="button"
                      onClick={submitText}
                      disabled={busy || !typedText.trim()}
                      className="min-h-[52px] flex-1 rounded-xl bg-teal-700 text-lg font-bold text-white hover:bg-teal-800 disabled:opacity-40"
                    >
                      {busy ? "Sending…" : "Send"}
                    </button>
                    <button
                      type="button"
                      onClick={() => setTypedMode(false)}
                      className="min-h-[52px] rounded-xl border-2 border-slate-300 px-4 font-bold text-slate-700"
                    >
                      Use mic
                    </button>
                  </div>
                </div>
              ) : (
                <div>
                  <VoiceRecorder onBlob={submitAudio} disabled={busy} />
                  <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
                    <button
                      type="button"
                      onClick={() => setTypedMode(true)}
                      className="text-base font-bold text-teal-800 underline"
                    >
                      Type instead
                    </button>
                    {browserSpeechSupported() && (
                      <button
                        type="button"
                        onClick={browserVoice}
                        disabled={listening || busy}
                        className="text-base font-bold text-teal-800 underline disabled:opacity-40"
                      >
                        {listening ? "Listening in browser…" : "Browser voice typing"}
                      </button>
                    )}
                  </div>
                </div>
              )}
              {busy && (
                <p className="mt-2 text-sm font-bold text-slate-600" role="status">
                  Working…
                </p>
              )}
            </section>
          )}

          {banner && (
            <p
              role={banner.kind === "error" ? "alert" : "status"}
              className={`rounded-xl p-4 font-medium ${
                banner.kind === "error"
                  ? "bg-red-50 text-red-800"
                  : banner.kind === "warn"
                    ? "bg-amber-50 text-amber-900"
                    : "bg-sky-50 text-sky-900"
              }`}
            >
              {banner.text}
            </p>
          )}

          <div>
            <button
              type="button"
              onClick={() => setShowPhoto((v) => !v)}
              aria-expanded={showPhoto}
              className="text-base font-bold text-teal-800 underline"
            >
              {showPhoto ? "Hide photo upload" : "Have a paper form? Photograph it"}
            </button>
            {showPhoto && (
              <div className="mt-2">
                <PhotoUpload sessionId={sid} onDone={load} />
              </div>
            )}
          </div>
        </div>

        <div className="lg:col-span-2">
          <div className="lg:sticky lg:top-4">
            <FormPreview answers={server.answers} currentOrd={server.current_ord} />
          </div>
        </div>
      </div>
    </div>
  );
}

export default function InterviewPage() {
  return (
    <Suspense fallback={<p className="py-10 text-center text-slate-600">Loading…</p>}>
      <InterviewInner />
    </Suspense>
  );
}
