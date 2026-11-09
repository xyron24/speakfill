"use client";

import { useEffect, useState } from "react";

export default function HealthPage() {
  const [body, setBody] = useState("loading…");
  const [ok, setOk] = useState<boolean | null>(null);

  useEffect(() => {
    fetch("/api/healthz")
      .then((r) => {
        setOk(r.ok);
        return r.text();
      })
      .then(setBody)
      .catch((e) => {
        setOk(false);
        setBody(String(e));
      });
  }, []);

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-slate-950 text-slate-100">
      <h1 className="text-2xl font-bold">System health</h1>
      <p className="text-sm text-slate-400">browser → Caddy → FastAPI</p>
      <span
        className={`rounded px-3 py-1 text-sm font-medium ${
          ok === null ? "bg-slate-700" : ok ? "bg-emerald-600" : "bg-red-600"
        }`}
      >
        {ok === null ? "checking…" : ok ? "API reachable" : "API unreachable"}
      </span>
      <pre className="max-w-xl overflow-auto rounded bg-slate-900 p-4 text-xs">{body}</pre>
      <a className="text-sm text-indigo-400 hover:underline" href="/">
        ← back
      </a>
    </main>
  );
}
