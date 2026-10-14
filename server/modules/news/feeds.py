"""Collect RSS/Atom feed items (stdlib XML + httpx)."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from xml.etree import ElementTree as ET

import httpx

logger = logging.getLogger(__name__)

_ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}
_MAX_ITEMS_PER_FEED = 15
_MAX_ITEMS_TOTAL = 40


@dataclass
class FeedItem:
    title: str
    link: str | None
    summary: str
    published: str | None
    source_url: str


def _strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", text).strip()


def _text(el: ET.Element | None) -> str:
    if el is None:
        return ""
    return "".join(el.itertext()).strip()


def _parse_date(raw: str | None) -> str | None:
    if not raw:
        return None
    text = raw.strip()
    try:
        if text.endswith("Z") or "+" in text[10:] or text.count("-") >= 2 and "T" in text:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            return dt.astimezone(timezone.utc).isoformat(timespec="seconds")
    except ValueError:
        pass
    try:
        dt = parsedate_to_datetime(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat(timespec="seconds")
    except (TypeError, ValueError, IndexError):
        return text


def _local(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def parse_feed_xml(content: bytes, source_url: str) -> list[FeedItem]:
    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        logger.warning("Feed XML parse failed for %s: %s", source_url, exc)
        return []

    root_tag = _local(root.tag).lower()
    items: list[FeedItem] = []

    if root_tag == "rss" or root_tag == "rdf":
        channel = root.find("channel")
        entries = channel.findall("item") if channel is not None else root.findall(".//item")
        for entry in entries[:_MAX_ITEMS_PER_FEED]:
            title = _text(entry.find("title")) or "Untitled"
            link = _text(entry.find("link")) or None
            desc = _text(entry.find("description")) or _text(entry.find("content:encoded"))
            # content:encoded may use namespace
            if not desc:
                for child in entry:
                    if _local(child.tag).lower() in ("description", "encoded", "summary"):
                        desc = _text(child)
                        break
            pub = _text(entry.find("pubDate")) or _text(entry.find("dc:date"))
            if not pub:
                for child in entry:
                    if _local(child.tag).lower() in ("pubdate", "date", "published"):
                        pub = _text(child)
                        break
            items.append(
                FeedItem(
                    title=title,
                    link=link,
                    summary=_strip_html(desc)[:800],
                    published=_parse_date(pub),
                    source_url=source_url,
                )
            )
        return items

    # Atom
    entries = root.findall("atom:entry", _ATOM_NS) or [
        e for e in root if _local(e.tag).lower() == "entry"
    ]
    for entry in entries[:_MAX_ITEMS_PER_FEED]:
        title = _text(entry.find("atom:title", _ATOM_NS)) or _text(
            next((c for c in entry if _local(c.tag).lower() == "title"), None)
        )
        link = None
        for link_el in entry.findall("atom:link", _ATOM_NS) or [
            c for c in entry if _local(c.tag).lower() == "link"
        ]:
            href = link_el.attrib.get("href")
            rel = link_el.attrib.get("rel", "alternate")
            if href and rel in ("alternate", ""):
                link = href
                break
            if href and link is None:
                link = href
        summary = _text(entry.find("atom:summary", _ATOM_NS)) or _text(
            entry.find("atom:content", _ATOM_NS)
        )
        if not summary:
            for child in entry:
                if _local(child.tag).lower() in ("summary", "content"):
                    summary = _text(child)
                    break
        pub = _text(entry.find("atom:updated", _ATOM_NS)) or _text(
            entry.find("atom:published", _ATOM_NS)
        )
        if not pub:
            for child in entry:
                if _local(child.tag).lower() in ("updated", "published"):
                    pub = _text(child)
                    break
        items.append(
            FeedItem(
                title=title or "Untitled",
                link=link,
                summary=_strip_html(summary)[:800],
                published=_parse_date(pub),
                source_url=source_url,
            )
        )
    return items


def _mock_feed(url: str) -> list[FeedItem]:
    """Synthetic items for PC smoke tests (`mock://topic-name`)."""
    label = url.split("://", 1)[-1] or "demo"
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return [
        FeedItem(
            title=f"{label.title()} headline one",
            link=f"https://example.invalid/{label}/1",
            summary=f"Demo summary for {label} item one.",
            published=now,
            source_url=url,
        ),
        FeedItem(
            title=f"{label.title()} headline two",
            link=f"https://example.invalid/{label}/2",
            summary=f"Demo summary for {label} item two.",
            published=now,
            source_url=url,
        ),
    ]


def fetch_feed(url: str, *, timeout: float = 15.0) -> list[FeedItem]:
    if url.startswith("mock://"):
        return _mock_feed(url)
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            resp = client.get(
                url,
                headers={"User-Agent": "PersonalAIssistent/0.1 (+news-collector)"},
            )
            resp.raise_for_status()
            return parse_feed_xml(resp.content, url)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Feed fetch failed for %s: %s", url, exc)
        return []


def collect_feeds(urls: list[str]) -> tuple[list[FeedItem], list[dict[str, Any]]]:
    """Fetch all feeds; return items + per-source status."""
    all_items: list[FeedItem] = []
    statuses: list[dict[str, Any]] = []
    for url in urls:
        items = fetch_feed(url)
        statuses.append({"url": url, "item_count": len(items), "ok": len(items) > 0})
        all_items.extend(items)
        if len(all_items) >= _MAX_ITEMS_TOTAL:
            break
    return all_items[:_MAX_ITEMS_TOTAL], statuses


def items_to_prompt_block(items: list[FeedItem]) -> str:
    lines: list[str] = []
    for i, item in enumerate(items, start=1):
        bit = f"{i}. {item.title}"
        if item.published:
            bit += f" ({item.published})"
        if item.summary:
            bit += f" — {item.summary[:280]}"
        if item.link:
            bit += f" <{item.link}>"
        lines.append(bit)
    return "\n".join(lines)


def items_as_jsonable(items: list[FeedItem]) -> list[dict[str, Any]]:
    return [
        {
            "title": i.title,
            "link": i.link,
            "summary": i.summary,
            "published": i.published,
            "source_url": i.source_url,
        }
        for i in items
    ]
