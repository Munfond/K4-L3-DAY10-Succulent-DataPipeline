import logging
import re
from dataclasses import asdict, dataclass
from pathlib import Path

import requests

from core.config import Settings
from core.utils import normalize_whitespace, read_json, write_json

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PaperRecord:
    paper_id: str
    title: str
    summary: str
    authors: list[str]
    categories: list[str]
    primary_category: str
    published: str
    updated: str
    abs_url: str
    pdf_url: str
    comment: str


def parse_crossref_payload(payload: dict | list) -> list[PaperRecord]:
    """Parse Crossref API payload or list of items into PaperRecord instances."""
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        items = payload.get("message", {}).get("items")
        if items is None:
            items = payload.get("items", [])
    else:
        items = []

    records: list[PaperRecord] = []
    for item in items:
        if not isinstance(item, dict):
            continue

        paper_id = normalize_whitespace(str(item.get("DOI") or item.get("paper_id") or ""))
        if not paper_id:
            continue

        title_raw = item.get("title", "")
        if isinstance(title_raw, list):
            title_str = title_raw[0] if title_raw else ""
        else:
            title_str = str(title_raw)
        title = normalize_whitespace(title_str)

        abstract_raw = item.get("abstract") or item.get("summary") or ""
        abstract_clean = re.sub(r"<[^>]+>", " ", str(abstract_raw))
        summary = normalize_whitespace(abstract_clean)

        authors: list[str] = []
        author_field = item.get("author") or item.get("authors") or []
        if isinstance(author_field, list):
            for a in author_field:
                if isinstance(a, dict):
                    given = normalize_whitespace(str(a.get("given", "")))
                    family = normalize_whitespace(str(a.get("family", "")))
                    name = f"{given} {family}".strip()
                    if name:
                        authors.append(name)
                elif isinstance(a, str) and a.strip():
                    authors.append(normalize_whitespace(a))
        elif isinstance(author_field, str) and author_field.strip():
            authors.append(normalize_whitespace(author_field))

        categories: list[str] = []
        cat_field = item.get("subject") or item.get("categories") or []
        if isinstance(cat_field, list):
            for c in cat_field:
                if isinstance(c, str) and c.strip():
                    categories.append(normalize_whitespace(c))
        elif isinstance(cat_field, str) and cat_field.strip():
            categories.append(normalize_whitespace(cat_field))

        primary_category = item.get("primary_category") or (categories[0] if categories else "General")

        published = ""
        pub_field = item.get("published")
        if isinstance(pub_field, dict):
            date_parts = pub_field.get("date-parts", [[]])
            if date_parts and date_parts[0]:
                dp = date_parts[0]
                if len(dp) >= 3:
                    published = f"{int(dp[0]):04d}-{int(dp[1]):02d}-{int(dp[2]):02d}"
                elif len(dp) == 2:
                    published = f"{int(dp[0]):04d}-{int(dp[1]):02d}-01"
                elif len(dp) == 1:
                    published = f"{int(dp[0]):04d}-01-01"
        elif isinstance(pub_field, str):
            published = pub_field[:10]

        if not published:
            created = item.get("created", {})
            if isinstance(created, dict):
                if "date-parts" in created and created["date-parts"]:
                    dp = created["date-parts"][0]
                    if len(dp) >= 3:
                        published = f"{int(dp[0]):04d}-{int(dp[1]):02d}-{int(dp[2]):02d}"
                elif "date-time" in created:
                    published = str(created["date-time"])[:10]

        updated = item.get("updated") or published
        abs_url = item.get("URL") or item.get("abs_url") or f"https://doi.org/{paper_id}"
        pdf_url = item.get("pdf_url") or abs_url
        comment = item.get("comment") or f"Crossref record {paper_id}"

        records.append(
            PaperRecord(
                paper_id=paper_id,
                title=title,
                summary=summary,
                authors=authors,
                categories=categories,
                primary_category=primary_category,
                published=published,
                updated=updated,
                abs_url=abs_url,
                pdf_url=pdf_url,
                comment=comment,
            )
        )
    return records


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Fetch records from Crossref REST API with robust offline snapshot fallback."""
    if settings.refresh_source:
        try:
            url = "https://api.crossref.org/works"
            params = {
                "query": settings.source_query,
                "filter": settings.source_filter,
                "rows": settings.max_results,
            }
            headers = {"User-Agent": "RAG-Observability-Lab/1.0 (mailto:student@lab.edu)"}
            response = requests.get(url, params=params, headers=headers, timeout=10)
            if response.status_code == 200:
                payload = response.json()
                write_json(settings.paths.raw_api_response, payload)
                records = parse_crossref_payload(payload)
                write_json(settings.paths.raw_records_json, [asdict(r) for r in records])
                return records
            logger.warning(
                f"Crossref API returned status {response.status_code}. Falling back to local offline snapshot."
            )
        except Exception as exc:
            logger.warning(f"Crossref API request failed: {exc}. Falling back to local offline snapshot.")

    # Offline fallback mechanism
    if settings.paths.raw_records_json.exists():
        try:
            records = load_raw_records(settings.paths.raw_records_json)
            if records:
                return records
        except Exception as exc:
            logger.warning(f"Failed to load records from {settings.paths.raw_records_json}: {exc}")

    if settings.paths.raw_api_response.exists():
        try:
            payload = read_json(settings.paths.raw_api_response)
            records = parse_crossref_payload(payload)
            write_json(settings.paths.raw_records_json, [asdict(r) for r in records])
            return records
        except Exception as exc:
            logger.warning(f"Failed to parse payload from {settings.paths.raw_api_response}: {exc}")

    raise FileNotFoundError(
        f"Unable to fetch records: live API unavailable and no valid raw snapshot found at "
        f"{settings.paths.raw_records_json} or {settings.paths.raw_api_response}."
    )


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Load JSON snapshot and map into list of PaperRecord."""
    if not path.exists():
        raise FileNotFoundError(f"Raw records file not found at: {path}")
    payload = read_json(path)
    if isinstance(payload, list):
        if payload and isinstance(payload[0], dict) and "paper_id" in payload[0]:
            return [PaperRecord(**item) for item in payload]
    return parse_crossref_payload(payload)

