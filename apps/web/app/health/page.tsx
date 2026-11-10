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
    <div className="mx-auto max-w-xl py-6">
      <h1 className="text-2xl font-extrabold text-slate-950">System health</h1>
      <p className="mt-1 text-slate-600">browser → Caddy → API</p>
      <p
        className={`mt-3 inline-block rounded-full px-3 py-1 text-sm font-bold text-white ${
          ok === null ? "bg-slate-500" : ok ? "bg-teal-700" : "bg-red-600"
        }`}
      >
        {ok === null ? "checking…" : ok ? "API reachable" : "API unreachable"}
      </p>
      <pre className="mt-3 max-w-xl overflow-auto rounded-xl bg-slate-900 p-4 text-xs text-slate-100">
        {body}
      </pre>
      <a className="mt-3 inline-block font-bold text-teal-800 underline" href="/">
        ← back
      </a>
    </div>
  );
}
