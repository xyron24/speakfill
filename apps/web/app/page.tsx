export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-slate-950 text-slate-100">
      <h1 className="text-4xl font-bold">🎙️ SpeakFill</h1>
      <p className="text-slate-400">Speak. Confirm. Done.</p>
      <a className="rounded bg-indigo-600 px-4 py-2 text-sm font-medium hover:bg-indigo-500" href="/health">
        Check system health →
      </a>
    </main>
  );
}
