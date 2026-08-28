"""Fetch public SUSU international-student pages and publish them via the local API.

Only www.susu.ru HTML that is already public. No login, search, admin, or news
interviews. Respects robots disallow paths. Intended for a one-time staff corpus
load so students can ask in Telegram.
"""

from __future__ import annotations

import json
import re
import time
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

import httpx

API_BASE = "http://127.0.0.1:8001"
USER_AGENT = "UniAssist/1.0 (official public page snapshot for staff corpus)"
REQUEST_DELAY_SECONDS = 5.0
MIN_BODY_CHARS = 400

SEED_URLS = (
    "https://www.susu.ru/en/programmes-international-students",
    "https://www.susu.ru/en/education/english-taught-programmes",
    "https://www.susu.ru/en/webform/apply-now",
    "https://www.susu.ru/en/programs/education-programs-foreign-students/government-scholarship",
    "https://www.susu.ru/en/international-relations-0/international-office/degree-recognition/en",
    "https://www.susu.ru/en/campus-life/association-international-students-and-alumni",
    "https://www.susu.ru/en/programs/education-programs-foreign-students/admission-trajectory",
    "https://www.susu.ru/en/programs/education-programs-foreign-students/when-you-arrive",
    "https://www.susu.ru/en/who-can-enter-territory-russian-federation",
    "https://www.susu.ru/en/preparatory-department-international-applicants",
    "https://www.susu.ru/en/programs/education-programs-foreign-students",
)

PATH_ALLOW = (
    "international",
    "foreign-student",
    "english-taught",
    "government-scholarship",
    "degree-recognition",
    "preparatory",
    "admission-trajectory",
    "when-you-arrive",
    "apply-now",
    "programmes-international",
    "education-programs-foreign",
    "who-can-enter",
    "association-international",
)

PATH_DENY = (
    "/admin/",
    "/user/login",
    "/user/logout",
    "/user/register",
    "/search/",
    "/comment/",
    "/news/",
    "/node/add",
)

MAX_PAGES = 18


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip = 0
        self._chunks: list[str] = []
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip += 1
        if tag == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._skip:
            self._skip -= 1
        if tag == "title":
            self._in_title = False
        if tag in {"p", "div", "li", "h1", "h2", "h3", "br", "tr"}:
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        text = " ".join(data.split())
        if not text:
            return
        if self._in_title and not self.title:
            self.title = text
        self._chunks.append(text)

    def text(self) -> str:
        joined = " ".join(self._chunks)
        joined = re.sub(r"[ \t]+", " ", joined)
        joined = re.sub(r"\n{3,}", "\n\n", joined)
        lines = [line.strip() for line in joined.splitlines()]
        return "\n".join(line for line in lines if line)


def _allowed(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    host = parsed.netloc.lower()
    if host not in {"www.susu.ru", "susu.ru"}:
        return False
    path = parsed.path or "/"
    lowered = path.lower()
    if any(deny in lowered for deny in PATH_DENY):
        return False
    if not any(token in lowered for token in PATH_ALLOW):
        return False
    return True


def _fetch(url: str) -> tuple[str, bytes]:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=30) as response:  # noqa: S310
        final = response.geturl()
        body = response.read()
    return final, body


def _extract(html: bytes) -> tuple[str, str]:
    parser = _TextExtractor()
    parser.feed(html.decode("utf-8", errors="replace"))
    title = parser.title.replace(" | South Ural State University", "").strip()
    body = parser.text()
    # Drop repeated chrome that often appears on Drupal pages.
    for noise in (
        "South Ural State University",
        "Personal account",
        "Search form",
    ):
        body = body.replace(noise, "\n")
    body = re.sub(r"\n{3,}", "\n\n", body).strip()
    return title, body


def _filename_for(url: str, index: int) -> str:
    slug = urlparse(url).path.strip("/").replace("/", "_") or f"page_{index}"
    slug = re.sub(r"[^a-zA-Z0-9._-]", "_", slug)[:80]
    return f"susu_international_{index:02d}_{slug}.txt"


def _snapshot_bytes(title: str, url: str, body: str) -> bytes:
    retrieved = datetime.now(UTC).date().isoformat()
    text = (
        f"{title}\n\n"
        f"Official source URL: {url}\n"
        f"Retrieved: {retrieved}\n"
        "Source: South Ural State University public website (www.susu.ru)\n"
        "Audience: international students and applicants\n\n"
        f"{body}\n"
    )
    return text.encode("utf-8")


def _upload_and_publish(
    client: httpx.Client, title: str, url: str, content: bytes, filename: str
) -> str:
    response = client.post(
        f"{API_BASE}/documents/upload",
        data={
            "title": title,
            "source": "South Ural State University official website",
            "source_url": url,
            "version": datetime.now(UTC).date().isoformat(),
            "notes": "Public international-student page snapshot from www.susu.ru",
        },
        files={"file": (filename, content, "text/plain")},
        timeout=60.0,
    )
    response.raise_for_status()
    payload = response.json()
    document_id = payload["document"]["document_id"]
    if payload.get("duplicate"):
        return f"duplicate {document_id}"
    published = client.post(f"{API_BASE}/documents/{document_id}/publish", timeout=60.0)
    if published.status_code >= 400:
        return (
            f"publish_failed {document_id} {published.status_code} "
            f"{published.text[:200]}"
        )
    body = published.json()
    return (
        f"published {document_id} indexed={body.get('indexed')} "
        f"chunks={body.get('chunks_indexed')}"
    )


def main() -> None:
    queued: list[str] = []
    seen: set[str] = set()
    for seed in SEED_URLS:
        if _allowed(seed) and seed not in seen:
            queued.append(seed)
            seen.add(seed)

    snapshots: list[tuple[str, str, bytes]] = []
    while queued and len(snapshots) < MAX_PAGES:
        url = queued.pop(0)
        print(f"fetch {url}")
        try:
            final, raw = _fetch(url)
        except (HTTPError, URLError, TimeoutError) as exc:
            print(f"skip {url}: {exc}")
            time.sleep(REQUEST_DELAY_SECONDS)
            continue
        if not _allowed(final):
            print(f"skip disallowed redirect {final}")
            time.sleep(REQUEST_DELAY_SECONDS)
            continue
        title, body = _extract(raw)
        if len(body) < MIN_BODY_CHARS:
            print(f"skip thin page {final} ({len(body)} chars)")
        else:
            title = (title or final)[:180]
            snapshots.append((title, final, _snapshot_bytes(title, final, body)))
        # Discover a few extra same-section links from the HTML.
        for match in re.findall(
            r'href=["\']([^"\']+)["\']', raw.decode("utf-8", errors="ignore")
        ):
            candidate = urljoin(final, match).split("#", 1)[0]
            if _allowed(candidate) and candidate not in seen and len(seen) < MAX_PAGES:
                seen.add(candidate)
                queued.append(candidate)
        time.sleep(REQUEST_DELAY_SECONDS)

    out_dir = Path("data") / "imports" / "susu_international"
    out_dir.mkdir(parents=True, exist_ok=True)
    client = httpx.Client(trust_env=False)
    results: list[str] = []
    try:
        for index, (title, url, content) in enumerate(snapshots, start=1):
            filename = _filename_for(url, index)
            (out_dir / filename).write_bytes(content)
            print(f"publish {title}")
            outcome = _upload_and_publish(client, title, url, content, filename)
            results.append(f"{title} | {url} | {outcome}")
    finally:
        client.close()

    report = out_dir / "ingest_report.json"
    report.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"done pages={len(snapshots)} report={report}")


if __name__ == "__main__":
    main()
