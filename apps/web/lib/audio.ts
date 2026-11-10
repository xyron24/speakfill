/* Single-track audio playback: starting a clip always stops the previous one. */

let current: HTMLAudioElement | null = null;

export function stopPlayback(): void {
  if (current) {
    current.pause();
    current = null;
  }
}

/** Resolves when playback ends; rejects if blocked (caller shows tap-to-play). */
export function playUrl(url: string): Promise<void> {
  stopPlayback();
  return new Promise((resolve, reject) => {
    const el = new Audio(url);
    current = el;
    el.onended = () => {
      if (current === el) current = null;
      resolve();
    };
    el.onerror = () => {
      if (current === el) current = null;
      reject(new Error("audio failed to play"));
    };
    el.play().catch(reject);
  });
}

export function prefersReducedMotion(): boolean {
  return (
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}
