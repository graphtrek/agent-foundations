"""Web tools: DuckDuckGo search for the coordinator, page fetching for the
page-researcher subagents.

``fetch_page`` only reads public http(s) pages: every hop of a redirect chain
is checked so the model cannot be steered to local or private network
addresses (SSRF), and the page is size- and time-limited.
"""

import ipaddress
import socket
import time
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from ddgs import DDGS
from langchain.tools import tool

SEARCH_RESULTS = 8
# DuckDuckGo rate-limits single backends at random, so try several in turn.
SEARCH_BACKENDS = ("auto", "lite", "html", "auto")
SEARCH_RETRY_PAUSE_SECONDS = 1.5
FETCH_TIMEOUT_SECONDS = 10.0
MAX_REDIRECTS = 3
MAX_PAGE_BYTES = 1_000_000
MAX_PAGE_CHARS = 6000
USER_AGENT = "Mozilla/5.0 (compatible; agent-foundations-research/1.0)"
_SKIPPED_TAGS = {"script", "style", "noscript", "svg", "head", "nav", "footer", "form", "template"}
_BLOCK_TAGS = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "tr", "section", "article"}


class _TextExtractor(HTMLParser):
    """Visible text of an HTML page, without scripts, navigation and styles."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIPPED_TAGS:
            self._skip += 1
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIPPED_TAGS and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip and data.strip():
            self.parts.append(data.strip() + " ")


def html_to_text(html: str) -> str:
    extractor = _TextExtractor()
    extractor.feed(html)
    lines = (" ".join(line.split()) for line in "".join(extractor.parts).splitlines())
    return "\n".join(line for line in lines if line)


def check_public_url(url: str) -> str | None:
    """``None`` when ``url`` is a public http(s) address, else the reason it is refused."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return "only http(s) links can be read"
    try:
        addresses = {info[4][0] for info in socket.getaddrinfo(parsed.hostname, parsed.port or 443)}
    except OSError:
        return "the host cannot be resolved"
    if not all(ipaddress.ip_address(a).is_global for a in addresses):
        return "the host is not a public address"
    return None


def read_page(url: str) -> str:
    """Download one public page and return its readable text (raises ``ValueError`` /
    ``httpx.HTTPError`` on anything that cannot be read)."""
    with httpx.Client(
        timeout=FETCH_TIMEOUT_SECONDS, headers={"User-Agent": USER_AGENT}, follow_redirects=False
    ) as client:
        for _ in range(MAX_REDIRECTS + 1):
            if (refusal := check_public_url(url)) is not None:
                raise ValueError(refusal)
            with client.stream("GET", url) as response:
                if response.is_redirect:
                    url = urljoin(url, response.headers.get("location", ""))
                    continue
                response.raise_for_status()
                kind = response.headers.get("content-type", "text/html").split(";")[0].strip()
                if kind not in ("text/html", "application/xhtml+xml", "text/plain"):
                    raise ValueError(f"unsupported content type {kind}")
                body = b""
                for chunk in response.iter_bytes():
                    body += chunk
                    if len(body) >= MAX_PAGE_BYTES:
                        break
                text = body.decode(response.encoding or "utf-8", errors="replace")
                return text if kind == "text/plain" else html_to_text(text)
    raise ValueError("too many redirects")


@tool
def web_search(query: str) -> str:
    """Search the web with DuckDuckGo. Returns a numbered list of results, each with
    title, URL and a short snippet."""
    results: list[dict[str, Any]] = []
    for attempt, backend in enumerate(SEARCH_BACKENDS):
        if attempt:
            time.sleep(SEARCH_RETRY_PAUSE_SECONDS)
        try:
            results = DDGS().text(query, max_results=SEARCH_RESULTS, backend=backend)
        except Exception:  # rate limit, "No results found", network, provider change
            continue
        if results:
            break
    if not results:
        return (
            "The search returned no results (the search service may be rate-limiting). "
            "You may retry once with a different query; otherwise tell the user."
        )
    return "\n\n".join(
        f"{i}. {r.get('title', '').strip()}\n   URL: {r.get('href', '')}\n   {r.get('body', '').strip()}"
        for i, r in enumerate(results, start=1)
    )


@tool
def fetch_page(url: str) -> str:
    """Read one public web page and return its text content (shortened)."""
    try:
        text = read_page(url)
    except (ValueError, httpx.HTTPError) as exc:
        return f"The page could not be read: {exc}"
    if not text.strip():
        return "The page has no readable text."
    return text[:MAX_PAGE_CHARS]


def create_page_reader_tools(customer_id: str = "") -> list[Any]:
    """Tool group ``web``: what a page-researcher subagent gets (the customer id
    is unused - the tools are the same for everyone)."""
    return [fetch_page]
