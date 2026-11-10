/* Browser-native speech recognition fallback (Chrome/Edge) when server STT is down. */

export function browserSpeechSupported(): boolean {
  if (typeof window === "undefined") return false;
  const w = window as unknown as Record<string, unknown>;
  return Boolean(w.SpeechRecognition || w.webkitSpeechRecognition);
}

/** Listens once and resolves with the transcript; rejects on error/unsupported. */
export function listenOnce(language: string, timeoutMs = 15000): Promise<string> {
  return new Promise((resolve, reject) => {
    const w = window as unknown as Record<string, new () => {
      lang: string;
      interimResults: boolean;
      onresult: ((ev: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null;
      onerror: ((ev: { error: string }) => void) | null;
      onend: (() => void) | null;
      start: () => void;
      stop: () => void;
    }>;
    const Ctor = w.SpeechRecognition || w.webkitSpeechRecognition;
    if (!Ctor) {
      reject(new Error("browser speech recognition not supported"));
      return;
    }
    const rec = new Ctor();
    rec.lang = language === "hi" ? "hi-IN" : "en-US";
    rec.interimResults = false;
    let settled = false;
    const done = (fn: () => void) => {
      if (!settled) {
        settled = true;
        clearTimeout(timer);
        try {
          rec.stop();
        } catch {
          /* already stopped */
        }
        fn();
      }
    };
    const timer = setTimeout(() => done(() => reject(new Error("listening timed out"))), timeoutMs);
    rec.onresult = (ev) => {
      const text = ev.results[0]?.[0]?.transcript ?? "";
      done(() => (text ? resolve(text) : reject(new Error("nothing heard"))));
    };
    rec.onerror = (ev) => done(() => reject(new Error(`microphone error: ${ev.error}`)));
    rec.onend = () => done(() => reject(new Error("nothing heard")));
    try {
      rec.start();
    } catch (e) {
      done(() => reject(e instanceof Error ? e : new Error("could not start listening")));
    }
  });
}
