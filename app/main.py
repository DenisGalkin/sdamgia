from __future__ import annotations

import asyncio
import re
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates


BASE_URL = "https://rus-ege.sdamgia.ru"
VARIANT_URL = f"{BASE_URL}/test"
TASK_URL_PATTERN = re.compile(r"^/problem/?$")
ANSWER_PATTERN = re.compile(r"^\s*Ответ\s*:\s*(.+?)\s*$", re.IGNORECASE | re.DOTALL)
VARIANT_ITEM_PATTERN = re.compile(
    r"<div\b[^>]*\bclass\s*=\s*[\"'][^\"']*\bprob_num\b[^\"']*[\"'][^>]*>"
    r"\s*(?P<number>.*?)\s*</div>(?P<body>.*?)"
    r"(?=(?:<hr>)?\s*<div\b[^>]*\bclass\s*=\s*[\"'][^\"']*\bprob_num\b[^\"']*[\"'][^>]*>|\Z)",
    re.IGNORECASE | re.DOTALL,
)
HREF_PATTERN = re.compile(r"href\s*=\s*([\"'])(?P<href>.*?)\1", re.IGNORECASE | re.DOTALL)
APP_DIR = Path(__file__).resolve().parent


@dataclass(slots=True)
class CacheEntry:
    value: str
    expires_at: float


class TtlCache:
    def __init__(self, max_size: int = 2048) -> None:
        self.max_size = max_size
        self._items: dict[str, CacheEntry] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> str | None:
        now = time.monotonic()
        async with self._lock:
            entry = self._items.get(key)
            if entry is None:
                return None
            if entry.expires_at <= now:
                self._items.pop(key, None)
                return None
            return entry.value

    async def set(self, key: str, value: str, ttl: int) -> None:
        now = time.monotonic()
        async with self._lock:
            if len(self._items) >= self.max_size:
                expired = [k for k, v in self._items.items() if v.expires_at <= now]
                for expired_key in expired:
                    self._items.pop(expired_key, None)
                if len(self._items) >= self.max_size:
                    oldest_key = min(self._items, key=lambda k: self._items[k].expires_at)
                    self._items.pop(oldest_key, None)
            self._items[key] = CacheEntry(value, now + ttl)


cache = TtlCache()
request_limit = asyncio.Semaphore(6)


async def fetch_html(client: httpx.AsyncClient, url: str, *, ttl: int) -> str:
    cached = await cache.get(url)
    if cached is not None:
        return cached

    async with request_limit:
        response = await client.get(url)
        response.raise_for_status()
        html = response.text
    await cache.set(url, html, ttl)
    return html


def task_id_from_href(href: str) -> str | None:
    parsed = urlparse(urljoin(BASE_URL, href))
    if parsed.scheme not in {"http", "https"} or parsed.netloc != "rus-ege.sdamgia.ru":
        return None
    if not TASK_URL_PATTERN.match(parsed.path):
        return None
    task_id = parse_qs(parsed.query).get("id", [""])[0]
    return task_id if task_id.isdigit() else None


def parse_variant(html: str) -> list[dict[str, str]]:
    tasks: list[dict[str, str]] = []

    # Only the first task is wrapped in `.prob_list`; later tasks begin with an
    # `<hr>` followed by `.prob_num`. Split the raw source at those repeated
    # number markers instead of relying on the inconsistent outer wrappers.
    for item in VARIANT_ITEM_PATTERN.finditer(html):
        number = BeautifulSoup(item.group("number"), "html.parser").get_text(" ", strip=True)
        task_id = next(
            (
                task_id_from_href(match.group("href"))
                for match in HREF_PATTERN.finditer(item.group("body"))
                if task_id_from_href(match.group("href"))
            ),
            None,
        )
        if number and task_id:
            tasks.append(
                {
                    "number": number,
                    "task_id": task_id,
                    "url": f"{BASE_URL}/problem?id={task_id}",
                }
            )

    return tasks


def clean_answer(text: str) -> str | None:
    normalized = " ".join(text.replace("\u00ad", "").replace("\xa0", " ").split())
    match = ANSWER_PATTERN.match(normalized)
    return match.group(1).strip() if match else None


def parse_answer(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")

    # SDAMGIA stores the canonical short answer in this hidden block. Targeting it
    # avoids unrelated "Ответ:" examples that can appear in handbook content.
    for node in soup.select(".prob_maindiv .answer, .answer"):
        answer = clean_answer(node.get_text(" ", strip=True))
        if answer:
            return answer

    # Conservative fallback for older pages where the answer is inside a solution.
    for node in soup.select(".prob_maindiv .solution span, .prob_maindiv .solution b"):
        answer = clean_answer(node.get_text(" ", strip=True))
        if answer:
            return answer
    return None


async def answer_for_task(
    client: httpx.AsyncClient, task: dict[str, str]
) -> dict[str, str | None]:
    try:
        html = await fetch_html(client, task["url"], ttl=86_400)
        answer = parse_answer(html)
    except Exception:
        # A single unavailable or malformed task must not abort the variant.
        answer = None
    return {**task, "answer": answer}


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.client = httpx.AsyncClient(
        timeout=httpx.Timeout(15.0, connect=8.0),
        follow_redirects=True,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; SDAMGIAAnswerFetcher/1.0)",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "ru,en;q=0.8",
        },
        limits=httpx.Limits(max_connections=8, max_keepalive_connections=6),
    )
    yield
    await app.state.client.aclose()


app = FastAPI(title="SDAMGIA Answers", docs_url=None, redoc_url=None, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
templates = Jinja2Templates(directory=APP_DIR / "templates")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/api/answers/{variant_number}")
async def get_answers(variant_number: str, request: Request):
    if not variant_number.isdigit() or len(variant_number) > 12:
        raise HTTPException(status_code=422, detail="Enter a valid test number")

    client: httpx.AsyncClient = request.app.state.client
    try:
        response_html = await fetch_html(
            client,
            f"{VARIANT_URL}?id={variant_number}&nt=True&pub=False",
            ttl=300,
        )
    except httpx.HTTPStatusError as exc:
        status = 404 if exc.response.status_code == 404 else 502
        raise HTTPException(status_code=status, detail="Test could not be loaded") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="SDAMGIA is temporarily unavailable") from exc

    tasks = parse_variant(response_html)
    if not tasks:
        raise HTTPException(status_code=404, detail="No tasks found for this test")

    answers = await asyncio.gather(*(answer_for_task(client, task) for task in tasks))
    return {"variant": variant_number, "answers": answers}


@app.get("/health")
async def health():
    return {"status": "ok"}
