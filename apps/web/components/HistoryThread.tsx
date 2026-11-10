"use client";

import { useEffect, useRef } from "react";

export interface HistoryItem {
  id: number;
  role: "assistant" | "user" | "system";
  text: string;
}

export default function HistoryThread({ items }: { items: HistoryItem[] }) {
  const boxRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const box = boxRef.current;
    if (box) box.scrollTop = box.scrollHeight;
  }, [items.length]);

  if (items.length === 0) return null;

  return (
    <section aria-label="Conversation so far">
      <div
        ref={boxRef}
        className="max-h-56 space-y-2 overflow-y-auto rounded-xl border border-slate-200 bg-slate-50 p-3"
      >
        {items.map((m) =>
          m.role === "user" ? (
            <div key={m.id} className="flex justify-end">
              <p className="max-w-[85%] rounded-2xl rounded-br-md bg-teal-700 px-3 py-2 text-sm font-medium text-white">
                {m.text}
              </p>
            </div>
          ) : (
            <div key={m.id} className="flex justify-start">
              <p className="max-w-[85%] rounded-2xl rounded-bl-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800">
                {m.text}
              </p>
            </div>
          )
        )}
      </div>
    </section>
  );
}
