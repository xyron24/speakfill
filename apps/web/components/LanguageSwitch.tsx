"use client";

export default function LanguageSwitch({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  const btn = (v: string, label: string) => (
    <button
      key={v}
      type="button"
      onClick={() => onChange(v)}
      aria-pressed={value === v}
      className={`min-h-[44px] flex-1 px-5 text-base font-semibold transition-colors ${
        value === v ? "bg-teal-700 text-white" : "text-slate-700 hover:bg-slate-100"
      }`}
    >
      {label}
    </button>
  );
  return (
    <div
      role="group"
      aria-label="Language"
      className="flex overflow-hidden rounded-xl border-2 border-slate-300 bg-white"
    >
      {btn("en", "English")}
      {btn("hi", "हिंदी")}
    </div>
  );
}
