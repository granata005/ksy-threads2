"""
Threads scraper for the Ksy content-strategy project.

For each handle in HANDLES, opens the public profile on threads.com,
scrolls until ~MAX_POSTS_PER_HANDLE posts are visible, intercepts GraphQL
JSON responses, and extracts post text + engagement counts. Then keeps
the top TOP_PERCENT by like_count and writes them to OUTPUT_PATH as a
single markdown corpus file.

Run:
    pip install -r requirements.txt
    playwright install chromium
    python tools/scraper/run.py

The script does not log in. It only reads public pages.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from playwright.sync_api import Response, sync_playwright


HANDLES = [
    "lomakin.psy",
    "tatyana__fisher_",
    "ilya._latypov",
    "polina_pomogaet",
]

MAX_POSTS_PER_HANDLE = 100
TOP_PERCENT = 0.20
SCROLL_PAUSE_MS = 1500
MAX_SCROLLS = 30
OUTPUT_PATH = Path("cycles/2026-05/inspiration-corpus.md")
RAW_DUMP_DIR = Path("tools/scraper/raw")


@dataclass
class Post:
    handle: str
    post_id: str
    code: str
    url: str
    text: str
    like_count: int
    reply_count: int
    reshare_count: int
    quote_count: int
    taken_at: int | None


def extract_posts(payload: dict, handle: str) -> list[Post]:
    """Walk a Threads GraphQL JSON tree and pull post-shaped nodes.

    Threads schema changes; this is intentionally a duck-typed search:
    a node is a post if it has `caption.text`, `like_count` and an id.
    """
    found: dict[str, Post] = {}

    def walk(node):
        if isinstance(node, dict):
            caption = node.get("caption")
            text = caption.get("text") if isinstance(caption, dict) else None
            like_count = node.get("like_count")
            pid = node.get("pk") or node.get("id")
            code = node.get("code") or pid

            if text and like_count is not None and pid:
                tpai = node.get("text_post_app_info") or {}
                reply_count = tpai.get("direct_reply_count", 0) or 0
                reshare_count = (
                    tpai.get("reshare_count")
                    or node.get("reshare_count")
                    or 0
                )
                quote_count = tpai.get("quote_count", 0) or 0
                ts = node.get("taken_at")
                url = f"https://www.threads.com/@{handle}/post/{code}"
                found[str(pid)] = Post(
                    handle=handle,
                    post_id=str(pid),
                    code=str(code),
                    url=url,
                    text=text.strip(),
                    like_count=int(like_count),
                    reply_count=int(reply_count),
                    reshare_count=int(reshare_count),
                    quote_count=int(quote_count),
                    taken_at=int(ts) if ts else None,
                )

            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(payload)
    return list(found.values())


def scrape_handle(handle: str) -> list[Post]:
    print(f"[{handle}] starting", flush=True)
    collected: dict[str, Post] = {}

    def on_response(response: Response):
        url = response.url
        if "graphql" not in url.lower() and "/api/" not in url:
            return
        ct = response.headers.get("content-type", "")
        if "json" not in ct:
            return
        try:
            data = response.json()
        except Exception:
            return
        try:
            posts = extract_posts(data, handle)
        except Exception as exc:
            print(f"  parse error on {url}: {exc}", flush=True)
            return
        for p in posts:
            if p.post_id not in collected:
                collected[p.post_id] = p

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
            locale="ru-RU",
        )
        page = ctx.new_page()
        page.on("response", on_response)

        page.goto(
            f"https://www.threads.com/@{handle}",
            wait_until="domcontentloaded",
            timeout=60_000,
        )
        page.wait_for_timeout(2_500)

        for i in range(MAX_SCROLLS):
            if len(collected) >= MAX_POSTS_PER_HANDLE:
                break
            page.mouse.wheel(0, 4_000)
            page.wait_for_timeout(SCROLL_PAUSE_MS)
            print(
                f"  scroll {i + 1}/{MAX_SCROLLS} — collected {len(collected)} posts",
                flush=True,
            )

        browser.close()

    RAW_DUMP_DIR.mkdir(parents=True, exist_ok=True)
    dump_path = RAW_DUMP_DIR / f"{handle}.json"
    dump_path.write_text(
        json.dumps(
            [asdict(p) for p in collected.values()],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(
        f"[{handle}] done — {len(collected)} posts -> {dump_path}",
        flush=True,
    )
    return list(collected.values())


def render_corpus(by_handle: dict[str, list[Post]]) -> str:
    out: list[str] = []
    out.append("# Корпус вдохновения: топ-посты по лайкам")
    out.append("")
    out.append(
        "> Собрано автоматически (`tools/scraper/run.py`) с публичных профилей Threads. "
        f"Топ-{int(TOP_PERCENT * 100)}% постов по лайкам с каждого аккаунта. "
        f"До {MAX_POSTS_PER_HANDLE} постов на профиль до отбора."
    )
    out.append("")
    out.append(
        "**Что с этим делать:** читать как референс по голосу, длине, формату хука, структуре поста. "
        "Не копировать. Записывать наблюдения в `foundation/lessons.md` по итогам разбора."
    )
    out.append("")

    for handle, posts in by_handle.items():
        out.append(f"## @{handle}")
        out.append("")
        if not posts:
            out.append("_Не удалось получить посты._")
            out.append("")
            continue

        ranked = sorted(posts, key=lambda p: p.like_count, reverse=True)
        keep = max(1, round(len(ranked) * TOP_PERCENT))
        top = ranked[:keep]

        out.append(
            f"_Собрано: {len(posts)} постов. В корпус: топ-{keep} "
            f"({int(TOP_PERCENT * 100)}%) по лайкам._"
        )
        out.append("")

        for i, p in enumerate(top, 1):
            out.append(
                f"### {i}. лайков: {p.like_count} · реплаев: {p.reply_count} · "
                f"репостов: {p.reshare_count}"
            )
            out.append("")
            out.append(f"[{p.url}]({p.url})")
            out.append("")
            for line in p.text.splitlines():
                out.append(f"> {line}" if line.strip() else ">")
            out.append("")

    return "\n".join(out)


def main():
    by_handle: dict[str, list[Post]] = {}
    for h in HANDLES:
        try:
            by_handle[h] = scrape_handle(h)
        except Exception as exc:
            print(f"[{h}] FAILED: {exc}", flush=True)
            by_handle[h] = []

    output = render_corpus(by_handle)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(output, encoding="utf-8")
    print(f"Wrote corpus to {OUTPUT_PATH}", flush=True)


if __name__ == "__main__":
    main()
