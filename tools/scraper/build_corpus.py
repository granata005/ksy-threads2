#!/usr/bin/env python3
"""Build cycles/2026-05/inspiration-corpus.md from raw scraper dumps."""
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "tools" / "scraper" / "raw"
OUT = ROOT / "cycles" / "2026-05" / "inspiration-corpus.md"

PROFILES = ["lomakin.psy", "tatyana__fisher_", "ilya._latypov", "polina_pomogaet"]


SLIDE_RE = re.compile(r"\s*\n\s*\d+\s*\n\s*/\s*\n\s*\d+\s*$")


def clean_text(text: str) -> str:
    t = text or ""
    t = SLIDE_RE.sub("", t)
    return t.rstrip()


def quote_block(text: str) -> str:
    lines = clean_text(text).split("\n")
    return "\n".join(f"> {ln}" if ln else ">" for ln in lines)


def render_profile(handle: str, posts: list[dict]) -> str:
    posts_sorted = sorted(posts, key=lambda p: (p.get("like_count", 0), p.get("reply_count", 0)), reverse=True)
    n = len(posts_sorted)
    top_k = max(1, math.ceil(n * 0.2)) if n else 0
    top = posts_sorted[:top_k]

    out = [f"## @{handle}", f"_Собрано: {n} постов. В корпус: топ-{top_k} (20%) по лайкам._", ""]
    for i, p in enumerate(top, 1):
        out.append(
            f"### {i}. лайков: {p.get('like_count', 0)} · реплаев: {p.get('reply_count', 0)} · репостов: {p.get('reshare_count', 0)}"
        )
        out.append(f"[ссылка]({p['url']})")
        out.append("")
        out.append(quote_block(p.get("text", "")))
        out.append("")
    return "\n".join(out)


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    parts = [
        "# Корпус вдохновения: топ-посты по лайкам",
        "",
        "> Собрано через Playwright MCP с публичных профилей. Топ-20% по лайкам, до 100 постов на профиль до отбора.",
        "",
    ]
    for handle in PROFILES:
        path = RAW / f"{handle}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        parts.append(render_profile(handle, data["posts"]))
    OUT.write_text("\n".join(parts), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
