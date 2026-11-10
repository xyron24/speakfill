import "./globals.css";
import Logo from "../components/Logo";

export const metadata = {
  title: "SpeakFill — Speak. Confirm. Done.",
  description: "Voice-first, multilingual form filling. Speak your answers, confirm each field, get a filled PDF.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-100 text-slate-950 antialiased">
        <header className="border-b border-slate-200 bg-white">
          <div className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-3">
            <a href="/" className="flex items-center gap-3" aria-label="SpeakFill home">
              <Logo />
              <span>
                <span className="block text-xl font-extrabold leading-tight tracking-tight">
                  SpeakFill
                </span>
                <span className="block text-xs font-semibold text-teal-800">
                  Speak. Confirm. Done.
                </span>
              </span>
            </a>
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
        <footer className="mx-auto max-w-6xl px-4 pb-8 pt-2">
          <p className="text-sm text-slate-500">
            SpeakFill — voice-first forms for everyone. Built for HackGlobal 2026.
          </p>
        </footer>
      </body>
    </html>
  );
}
