"""Pre-generate + cache ALL static TTS audio (template prompts + system lines).

Run inside the api container (also runs in deploy.sh):
    python -m scripts.pregen_prompts
Reads templates_v1.json directly, so it works before/without DB seeding.
"""

import json
import os
import pathlib
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import tts  # noqa: E402
from app.vocab import STATIC_SYSTEM_LINES  # noqa: E402

TEMPLATE_PATH = (
    pathlib.Path(__file__).resolve().parent.parent / "app" / "data" / "templates_v1.json"
)


def collect() -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    tpl = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))
    for f in tpl["fields"]:
        for locale in ("en", "hi"):
            pairs.append((f["prompts"][locale]["ask"], locale))
            if f["prompts"][locale].get("hint"):
                pairs.append((f["prompts"][locale]["hint"], locale))
    for locale, lines in STATIC_SYSTEM_LINES.items():
        pairs.extend((line, locale) for line in lines)
    # Dedupe, preserve order, drop empties.
    seen, out = set(), []
    for text, locale in pairs:
        if text and (text, locale) not in seen:
            seen.add((text, locale))
            out.append((text, locale))
    return out


def main() -> None:
    pairs = collect()
    hits = misses = 0
    for text, locale in pairs:
        voice = tts.voice_for(locale)
        pre_exists = (tts.cache_dir() / f"{tts.cache_key(text, locale, voice)}.wav").exists()
        url = tts.speak(text, locale, voice)
        if pre_exists:
            hits += 1
        else:
            misses += 1
        print(f"  [{'HIT ' if pre_exists else 'MISS'}] {locale} {url}  ({text[:48]!r}…)")
    total_kb = sum(p.stat().st_size for p in tts.cache_dir().glob("*.wav")) / 1024
    print(f"done: {len(pairs)} lines, {hits} cache hits, {misses} syntheses, {total_kb:.0f} KB cached")


if __name__ == "__main__":
    main()
