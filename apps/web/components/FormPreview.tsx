import type { AnswerState } from "../lib/api";

const LABELS: Record<string, string> = {
  full_name: "Full name",
  date_of_birth: "Date of birth",
  gender: "Gender",
  phone: "Phone",
  email: "Email",
  university: "University",
  course_of_study: "Course",
  year_of_study: "Year",
  cgpa: "CGPA",
  family_income: "Income",
  need_statement: "Need statement",
  consent: "Consent",
};

function display(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "object") {
    const v = value as Record<string, unknown>;
    if ("value" in v) return `${v.value}${v.scale === "percent" ? "%" : ""}`;
    return JSON.stringify(value);
  }
  return String(value);
}

export default function FormPreview({
  answers,
  currentOrd,
}: {
  answers: AnswerState[];
  currentOrd: number;
}) {
  const done = answers.filter((a) => a.confirmed).length;
  return (
    <section aria-label="Form progress" className="rounded-xl border border-slate-300 bg-white">
      <div className="border-b border-slate-200 px-4 py-3">
        <h2 className="text-base font-bold text-slate-900">Your form</h2>
        <p className="text-sm text-slate-600">
          {done} of {answers.length} confirmed
        </p>
      </div>
      <ol className="max-h-[420px] divide-y divide-slate-100 overflow-y-auto px-4 py-2">
        {answers.map((a) => {
          const active = a.ord === currentOrd && !a.confirmed;
          return (
            <li key={a.key} className={`flex items-start gap-2 py-2 ${active ? "rounded-lg bg-amber-50 px-1" : ""}`}>
              <span
                aria-hidden="true"
                className={`mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full ${
                  a.confirmed ? "bg-teal-600" : a.pending ? "bg-amber-500" : "bg-slate-300"
                }`}
              />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-bold text-slate-800">{LABELS[a.key] ?? a.key}</p>
                <p className="truncate text-sm text-slate-600">{display(a.value)}</p>
              </div>
              {a.confirmed && (
                <span className="shrink-0 text-xs font-bold uppercase text-teal-700">done</span>
              )}
              {!a.confirmed && a.pending && (
                <span className="shrink-0 text-xs font-bold uppercase text-amber-700">check</span>
              )}
            </li>
          );
        })}
      </ol>
    </section>
  );
}
