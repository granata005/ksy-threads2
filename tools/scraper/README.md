# Threads scraper для корпуса вдохновения

Берёт список handle'ов из `run.py`, открывает их публичные профили на `threads.com`, скроллит до ~100 постов, перехватывает GraphQL-ответы и достаёт текст + лайки/реплаи/репосты. Потом отбирает топ N% по лайкам и пишет один маркдаун-файл с цитатами в `cycles/2026-05/inspiration-corpus.md`.

Скрипт **не логинится**. Работает только с публичными постами.

## Установка

Нужен Python 3.11+. Изнутри корня проекта (`ksy-threads2/`):

```bash
python -m venv .venv
source .venv/bin/activate         # Windows: .venv\Scripts\activate
pip install -r tools/scraper/requirements.txt
playwright install chromium
```

## Запуск

```bash
python tools/scraper/run.py
```

Скрипт открывает 4 профиля, скроллит каждый до ~100 постов (или до потолка `MAX_SCROLLS`), пишет:

- `cycles/2026-05/inspiration-corpus.md` — финальный корпус с топ-20% по лайкам, готовый к чтению;
- `tools/scraper/raw/<handle>.json` — сырой дамп всех собранных постов (на случай переразбора и для дебага).

Папка `raw/` в `.gitignore`, в репо не пушится.

## Конфигурация

Меняется в верхней части `run.py`:

| Переменная | Значение по умолчанию | Что делает |
|---|---|---|
| `HANDLES` | 4 хендла | список аккаунтов для обхода |
| `MAX_POSTS_PER_HANDLE` | 100 | потолок до сортировки |
| `TOP_PERCENT` | 0.20 | какую долю по лайкам оставить (0.20 = 20%) |
| `MAX_SCROLLS` | 30 | сколько раз листать; если постов мало — увеличить |
| `SCROLL_PAUSE_MS` | 1500 | пауза между скроллами в мс |

## Если Playwright ругается «Executable doesn't exist at …chrome-headless-shell»

Это бывает, когда установленная версия Playwright ждёт другую версию Chromium, чем та, что у вас на диске (например, в управляемом окружении вроде Codespaces или corporate-сборки уже лежит готовый Chromium). Два варианта:

1. Обычный путь: `playwright install chromium` — скачает нужную версию.
2. Указать путь к существующему бинарю через переменную окружения:
   ```bash
   CHROMIUM_PATH=/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell python tools/scraper/run.py
   ```
   Подходит и `chromium-XXXX/chrome-linux/chrome`, и `chromium_headless_shell-XXXX/chrome-linux/headless_shell`.

## Если собрано 0 постов

Threads регулярно меняет схему GraphQL-ответов. Эвристика парсинга в `extract_posts()` ищет в JSON-узлах поля `caption.text` + `like_count` + `pk/id`. Если этих полей в ответах больше нет — функция вернёт пусто.

Что делать:

1. Открыть `tools/scraper/raw/<handle>.json` — он будет пуст.
2. Открыть профиль в браузере с DevTools → Network → отфильтровать по `graphql` → посмотреть, какие поля сейчас в ответе.
3. Поправить `extract_posts()` под актуальную схему.

Альтернатива на случай совсем глухой защиты: запустить с `headless=False` в `chromium.launch()`, чтобы посмотреть глазами что происходит. Если профиль требует кликнуть «Continue without account» — добавить шаг через `page.get_by_text(...).click()` после `page.goto`.

## Этика

- Скрейпим только публично доступные посты, не логинимся, не обходим капчи.
- Запускаем разово, при обновлении корпуса вдохновения; не на регулярной основе.
- Скрипт ничего не публикует и не модифицирует на стороне Threads.
- Читать соглашение `threads.com/terms` перед регулярным использованием.

## Зависимости

- [Playwright Python](https://playwright.dev/python/) — headless Chromium с перехватом сетевых ответов.
- Heavy lifting (Stealth-патчи, прокси) при необходимости можно добавить по образцу [Zeeshanahmad4/Threads-Scraper](https://github.com/Zeeshanahmad4/Threads-Scraper) — оттуда же взята общая идея «Playwright + listen-on-response».
