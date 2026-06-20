#!/usr/bin/env python3
"""Collect A8/A93 project-overview history and Wayback construction records."""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import time
from collections import defaultdict
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "raw"
CURRENT_OVERVIEW = "https://www.autobahn.de/planen-bauen/projektuebersicht"
WAYBACK_CDX = "https://web.archive.org/cdx/search/cdx"
START_YEAR = 2023
END_YEAR = 2026
COLLECTED_AT = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

ROAD_FILTERS = {"A8": "syscat58", "A93": "syscat120"}
ROAD_PATTERN = {
    "A8": re.compile(r"(^|[/_.-])a[- ]?8($|[/_.-])", re.I),
    "A93": re.compile(r"(^|[/_.-])a[- ]?93($|[/_.-])", re.I),
}
CONSTRUCTION_TERMS = re.compile(
    r"(bau|erneuer|sanier|instand|asphalt|fahrbahn|fahrdeck|decke|brueck|brück|"
    r"laerm|lärm|erhalt|ausbau|umbau|anlage|schutzwand|talbruecke|viadukt|"
    r"aufstieg|enztal|saalhaupt|pfaffenstein|mangfall|eichelbach|rohrdorfer|"
    r"saalach|traun)",
    re.I,
)
EXCLUDE_TERMS = re.compile(
    r"(eichenprozessionsspinner|notfalluebung|fahrkalender|schnellladepark|"
    r"autobahnmeisterei|karriere)",
    re.I,
)

OVERVIEW_SNAPSHOTS = [
    (
        "A93",
        "2024-06-20",
        "20240620094749",
        "https://www.autobahn.de/planen-bauen/projektuebersicht?"
        "tx_kesearch_pi1%5Bfilter_1_534%5D=syscat120",
    ),
    (
        "A8",
        "2024-12-02",
        "20241202101129",
        "https://www.autobahn.de/planen-bauen/projektuebersicht?"
        "tx_kesearch_pi1%5Bfilter_1_526%5D=syscat58",
    ),
    (
        "A93",
        "2024-12-03",
        "20241203164320",
        "https://www.autobahn.de/planen-bauen/projektuebersicht?"
        "tx_kesearch_pi1%5Bfilter_1_534%5D=syscat120",
    ),
    (
        "A8",
        "2025-03-27",
        "20250327093816",
        "https://www.autobahn.de/planen-bauen/projektuebersicht?"
        "tx_kesearch_pi1%5Bfilter_1_526%5D=syscat58",
    ),
    (
        "A93",
        "2025-05-19",
        "20250519134127",
        "https://www.autobahn.de/planen-bauen/projektuebersicht?"
        "tx_kesearch_pi1%5Bfilter_1_534%5D=syscat120",
    ),
    (
        "A8",
        "2025-09-17",
        "20250917201323",
        "https://www.autobahn.de/planen-bauen/projektuebersicht?"
        "tx_kesearch_pi1%5Bfilter_1_526%5D=syscat58",
    ),
    (
        "A93",
        "2025-09-17",
        "20250917195447",
        "https://www.autobahn.de/planen-bauen/projektuebersicht?"
        "tx_kesearch_pi1%5Bfilter_1_534%5D=syscat120",
    ),
    (
        "A93",
        "2026-01-21",
        "20260121211420",
        "https://www.autobahn.de/planen-bauen/projektuebersicht?"
        "tx_kesearch_pi1%5Bfilter_1_534%5D=syscat120",
    ),
]

LEGACY_PLANS = [
    (
        "A8",
        "A8 Achenmühle – Bernauer Berg",
        "planning",
        "20230207090654",
        "https://www.autobahn.de/suedbayern/planfeststellungsverfahren/"
        "laufende-planfeststellungsverfahren/a8-achenmuehle-bernauer-berg",
    ),
    (
        "A8",
        "A8 Anschlussstelle Dachau",
        "planning",
        "20230207072328",
        "https://www.autobahn.de/suedbayern/planfeststellungsverfahren/"
        "laufende-planfeststellungsverfahren/a8-as-dachau",
    ),
    (
        "A8",
        "Sechsstreifiger Ausbau AS Rosenheim – Achenmühle",
        "planning",
        "20230207091622",
        "https://www.autobahn.de/suedbayern/planfeststellungsverfahren/"
        "laufende-planfeststellungsverfahren/a8-as-rosenheim-as-achenmuehle",
    ),
    (
        "A8",
        "Lärmvorsorge Valley und Bauwerkserneuerungen",
        "planning",
        "20230207080458",
        "https://www.autobahn.de/suedbayern/planfeststellungsverfahren/"
        "laufende-planfeststellungsverfahren/a8-laermvorsorge-valley-und-bauwerkserneuerungen",
    ),
    (
        "A8",
        "Nachträgliche Lärmvorsorge Weyarn",
        "planning",
        "20230207092758",
        "https://www.autobahn.de/suedbayern/planfeststellungsverfahren/"
        "laufende-planfeststellungsverfahren/a8-nachtraegliche-laermvorsorge-weyarn",
    ),
]

HISTORICAL_EVENTS = [
    (
        "A8",
        "20230528191907",
        "https://www.autobahn.de/die-autobahn/verkehrsmeldungen/detail/"
        "a8-/-as-kirchheim-ost-bis-as-aichelberg-fahrtrichtung-muenchen-"
        "neuer-asphalt-auf-der-autobahn-und-ausbau-der-as-aichelberg",
    ),
    (
        "A8",
        "20230519150306",
        "https://www.autobahn.de/die-autobahn/aktuelles/detail/"
        "a8-ersatzneubau-der-bruecke-ueber-die-b466-bei-muehlhausen-im-taele-"
        "verkehrsfreigabe-und-nachmittag-der-offenen-bruecke",
    ),
    (
        "A8",
        "20230607021721",
        "https://www.autobahn.de/west/aktuelles/detail/"
        "a8-grundhafte-erneuerung-zwischen-neunkirchen-oberstadt-und-"
        "autobahnkreuz-neunkirchen-beginnt",
    ),
    (
        "A8",
        "20230607012328",
        "https://www.autobahn.de/west/verkehrsmeldungen/detail/"
        "a8-erneuerung-zwischen-dillingen-mitte-und-autobahndreieck-saarlouis-"
        "vollsperrung-aufgehoben",
    ),
    (
        "A8",
        "20230607013013",
        "https://www.autobahn.de/west/verkehrsmeldungen/detail/"
        "a8-ersatzneubau-der-landertalbruecke-bei-neunkirchen-oberstadt-"
        "weiterer-umbau-der-verkehrssicherung",
    ),
    (
        "A8",
        "20230607023915",
        "https://www.autobahn.de/west/verkehrsmeldungen/detail/"
        "a8-sanierung-der-anschlussstelle-dillingen-sued",
    ),
    (
        "A8",
        "20230328043857",
        "https://www.autobahn.de/suedbayern/verkehrsmeldungen/detail/a8-mangfallbruecke",
    ),
    (
        "A93",
        "20230328101532",
        "https://www.autobahn.de/nordbayern/verkehrsmeldungen/detail/"
        "a93-beginn-des-ersatzneubaus-der-eichelbachbruecke",
    ),
    (
        "A93",
        "20230508134337",
        "https://www.autobahn.de/nordbayern/verkehrsmeldungen/detail/"
        "a93-baubeginn-fuer-die-fahrbahnerneuerung-und-brueckeninstandsetzung-"
        "zwischen-den-anschlussstellen-weiden-nord-und-weiden-sued",
    ),
    (
        "A93",
        "20230613144918",
        "https://www.autobahn.de/nordbayern/verkehrsmeldungen/detail/"
        "a93-deckenerneuerung-zwischen-den-anschlussstellen-schwarzenfeld-und-"
        "schwandorf-sued-in-fahrtrichtung-weiden",
    ),
]

EVENT_TITLE_OVERRIDES = {
    "https://www.autobahn.de/suedbayern/verkehrsmeldungen/detail/a8-mangfallbruecke":
        "A8 Mangfallbrücke",
    "https://www.autobahn.de/nordbayern/verkehrsmeldungen/detail/"
    "a93-beginn-des-ersatzneubaus-der-eichelbachbruecke":
        "A93 Beginn des Ersatzneubaus der Eichelbachbrücke",
}


def fetch(url: str, retries: int = 4) -> str:
    request = Request(url, headers={"User-Agent": "Autobahn-Hackathon-Archive-Collector/1.0"})
    error: Exception | None = None
    for attempt in range(retries):
        try:
            with urlopen(request, timeout=120) as response:
                return response.read().decode("utf-8", errors="replace")
        except Exception as exc:
            error = exc
            if attempt + 1 < retries:
                time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Could not fetch {url}: {error}")


def wayback_raw_url(timestamp: str, original: str) -> str:
    return f"https://web.archive.org/web/{timestamp}id_/{original}"


def wayback_view_url(timestamp: str, original: str) -> str:
    return f"https://web.archive.org/web/{timestamp}/{original}"


def write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


class ProjectCardParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.cards: list[dict[str, str]] = []
        self.card: dict[str, str] | None = None
        self.depth = 0
        self.capture = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        classes = values.get("class", "").split()
        if tag == "div" and "result-list-item-type-tx_autobahnprojects_domain_model_project" in classes:
            self.card = {"title": "", "status": "", "url": "", "tags": ""}
            self.depth = 1
            return
        if self.card is None:
            return
        if tag == "div":
            self.depth += 1
        if tag == "h3":
            self.capture = "title"
        elif tag == "span" and "badge" in classes:
            self.capture = "status"
        elif tag == "a" and "stretched-link" in classes:
            self.card["url"] = values.get("href", "")
            if values.get("title"):
                self.card["title"] = values["title"]
        elif tag == "a" and "tag-item" in classes:
            self.capture = "tag"

    def handle_data(self, data: str) -> None:
        if self.card is None or not self.capture:
            return
        text = " ".join(data.split())
        if not text:
            return
        if self.capture == "tag":
            self.card["tags"] = "|".join(filter(None, [self.card["tags"], text]))
        else:
            self.card[self.capture] = " ".join(filter(None, [self.card[self.capture], text]))

    def handle_endtag(self, tag: str) -> None:
        if self.card is None:
            return
        if tag in {"h3", "span", "a"}:
            self.capture = ""
        if tag == "div":
            self.depth -= 1
            if self.depth == 0:
                self.cards.append(self.card)
                self.card = None


class ArticleMetaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.description = ""
        self.published_date = ""
        self.modified_date = ""
        self.h1 = ""
        self.capture_h1 = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        if tag == "meta":
            prop = values.get("property") or values.get("name") or values.get("itemprop")
            content = values.get("content", "")
            if prop == "og:title":
                self.title = content
            elif prop in {"og:description", "description"} and not self.description:
                self.description = content
            elif prop == "datePublished":
                self.published_date = content
            elif prop == "dateModified":
                self.modified_date = content
        elif tag == "h1" and not self.h1:
            self.capture_h1 = True

    def handle_data(self, data: str) -> None:
        if self.capture_h1:
            self.h1 += " ".join(data.split())

    def handle_endtag(self, tag: str) -> None:
        if tag == "h1":
            self.capture_h1 = False


def parse_cards(document: str) -> list[dict[str, str]]:
    parser = ProjectCardParser()
    parser.feed(document)
    return parser.cards


def normalize_text(value: str) -> str:
    return " ".join(html.unescape(value or "").split())


def parse_article(document: str) -> dict[str, str]:
    parser = ArticleMetaParser()
    parser.feed(document)
    title = normalize_text(parser.h1 or parser.title)
    return {
        "title": title,
        "description": normalize_text(parser.description),
        "published_date": parser.published_date[:10],
        "modified_date": parser.modified_date[:10],
    }


def detect_roads(url: str) -> list[str]:
    path = unquote(urlparse(url).path)
    return [road for road, pattern in ROAD_PATTERN.items() if pattern.search(path)]


def classify_archive_url(url: str) -> str:
    path = unquote(urlparse(url).path).lower()
    if EXCLUDE_TERMS.search(path):
        return ""
    if "/planen-bauen/projekt/" in path or "/projekte/detail/" in path:
        return "project"
    if "/planfeststellungsverfahren/" in path:
        return "planning"
    if "/baustellenmeldung/" in path:
        return "construction_notice"
    if "/verkehrsmeldung/" in path or "/verkehrsmeldungen/detail/" in path:
        return "construction_notice" if CONSTRUCTION_TERMS.search(path) else ""
    if "/aktuelles/" in path or "/presse/" in path:
        return "project_update" if CONSTRUCTION_TERMS.search(path) else ""
    return "construction_notice" if CONSTRUCTION_TERMS.search(path) else ""


def canonical_url(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse(("https", "www.autobahn.de", parsed.path.rstrip("/"), "", "", ""))


def load_or_fetch_cdx(year: int, refresh: bool) -> list[list[str]]:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_DIR / f"cdx_{year}.json"
    if not path.exists() or refresh:
        params = {
            "url": "autobahn.de/*",
            "from": str(year),
            "to": str(year),
            "output": "json",
            "filter": ["statuscode:200", "mimetype:text/html", "original:.*(a8|A8|a93|A93).*"],
            "fl": "timestamp,original,digest",
            "collapse": "urlkey",
        }
        query_parts = [
            ("url", params["url"]),
            ("from", params["from"]),
            ("to", params["to"]),
            ("output", "json"),
            ("filter", "statuscode:200"),
            ("filter", "mimetype:text/html"),
            ("filter", "original:.*(a8|A8|a93|A93).*"),
            ("fl", params["fl"]),
            ("collapse", params["collapse"]),
        ]
        path.write_text(fetch(f"{WAYBACK_CDX}?{urlencode(query_parts)}"), encoding="utf-8")
    data = json.loads(path.read_text(encoding="utf-8"))
    return data[1:] if data and data[0][0] == "timestamp" else data


def collect_archive_records(refresh: bool) -> list[dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for year in range(START_YEAR, END_YEAR + 1):
        for timestamp, original, digest in load_or_fetch_cdx(year, refresh):
            roads = detect_roads(original)
            kind = classify_archive_url(original)
            if not roads or not kind:
                continue
            url = canonical_url(original)
            row = records.setdefault(
                url.lower(),
                {
                    "roads": set(),
                    "record_kind": kind,
                    "original_url": url,
                    "first_capture": timestamp,
                    "last_capture": timestamp,
                    "capture_count": 0,
                    "first_digest": digest,
                },
            )
            row["roads"].update(roads)
            row["first_capture"] = min(row["first_capture"], timestamp)
            row["last_capture"] = max(row["last_capture"], timestamp)
            row["capture_count"] += 1
            if kind in {"project", "planning"}:
                row["record_kind"] = kind

    output = []
    for row in records.values():
        timestamp = row["first_capture"]
        output.append(
            {
                "roads": "|".join(sorted(row["roads"])),
                "record_kind": row["record_kind"],
                "original_url": row["original_url"],
                "first_capture_timestamp": timestamp,
                "first_capture_date": f"{timestamp[:4]}-{timestamp[4:6]}-{timestamp[6:8]}",
                "last_capture_timestamp": row["last_capture"],
                "capture_count": row["capture_count"],
                "wayback_url": wayback_view_url(timestamp, row["original_url"]),
                "review_status": "candidate_url_filtered",
            }
        )
    return sorted(output, key=lambda row: (row["roads"], row["first_capture_timestamp"], row["original_url"]))


def collect_overview_observations() -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    for road, observed_date, timestamp, original in OVERVIEW_SNAPSHOTS:
        document = fetch(wayback_raw_url(timestamp, original))
        for card in parse_cards(document):
            if "fahrkalender" in card["url"].lower():
                continue
            observations.append(
                {
                    "observed_date": observed_date,
                    "road": road,
                    "title": card["title"],
                    "status": card["status"],
                    "project_url": canonical_url(card["url"]),
                    "source_type": "wayback_project_overview",
                    "source_url": wayback_view_url(timestamp, original),
                }
            )

    observed_date = datetime.now().date().isoformat()
    for road, category in ROAD_FILTERS.items():
        for page in (1, 2):
            params = [("tx_kesearch_pi1[filter_1]", category)]
            if page > 1:
                params.append(("tx_kesearch_pi1[page]", str(page)))
            url = f"{CURRENT_OVERVIEW}?{urlencode(params)}"
            cards = parse_cards(fetch(url))
            if page > 1 and not cards:
                continue
            for card in cards:
                if "fahrkalender" in card["url"].lower():
                    continue
                observations.append(
                    {
                        "observed_date": observed_date,
                        "road": road,
                        "title": card["title"],
                        "status": card["status"],
                        "project_url": canonical_url(card["url"]),
                        "source_type": "current_project_overview",
                        "source_url": url,
                    }
                )
            if len(cards) < 12:
                break

    unique = {
        (
            row["observed_date"],
            row["road"],
            row["project_url"],
            row["status"],
        ): row
        for row in observations
    }
    return sorted(unique.values(), key=lambda row: (row["observed_date"], row["road"], row["project_url"]))


def aggregate_projects(
    observations: list[dict[str, Any]],
    archive_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    archive_by_url = {row["original_url"]: row for row in archive_records}
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in observations:
        grouped[(row["road"], row["project_url"])].append(row)

    projects: list[dict[str, Any]] = []
    for (road, project_url), rows in grouped.items():
        rows.sort(key=lambda row: row["observed_date"])
        latest = rows[-1]
        archive = archive_by_url.get(project_url, {})
        projects.append(
            {
                "project_id": project_url.rsplit("/", 1)[-1],
                "road": road,
                "title": latest["title"],
                "record_type": "project_overview",
                "latest_status": latest["status"],
                "first_overview_observation": rows[0]["observed_date"],
                "last_overview_observation": rows[-1]["observed_date"],
                "archive_first_capture": archive.get("first_capture_date", ""),
                "observation_count": len(rows),
                "status_history": "|".join(
                    f"{row['observed_date']}:{row['status']}"
                    for row in rows
                    if row["status"]
                ),
                "project_url": project_url,
                "description": "",
                "latest_source_url": latest["source_url"],
                "evidence_level": "project_overview_observed",
            }
        )

    for road, title, record_type, timestamp, original in LEGACY_PLANS:
        project_url = canonical_url(original)
        projects.append(
            {
                "project_id": project_url.rsplit("/", 1)[-1],
                "road": road,
                "title": title,
                "record_type": record_type,
                "latest_status": "Planfeststellungsverfahren",
                "first_overview_observation": "",
                "last_overview_observation": "",
                "archive_first_capture": f"{timestamp[:4]}-{timestamp[4:6]}-{timestamp[6:8]}",
                "observation_count": 1,
                "status_history": f"{timestamp[:4]}-{timestamp[4:6]}-{timestamp[6:8]}:Planfeststellungsverfahren",
                "project_url": project_url,
                "description": "",
                "latest_source_url": wayback_view_url(timestamp, original),
                "evidence_level": "legacy_planning_page",
            }
        )

    unique = {(row["road"], row["project_id"]): row for row in projects}
    output = sorted(unique.values(), key=lambda row: (row["road"], row["title"]))
    for row in output:
        if row["record_type"] != "project_overview":
            continue
        try:
            detail = parse_article(fetch(row["project_url"]))
            row["description"] = detail["description"]
        except RuntimeError:
            row["description"] = ""
    return output


def collect_historical_events() -> list[dict[str, Any]]:
    rows = []
    for index, (road, timestamp, original) in enumerate(HISTORICAL_EVENTS, start=1):
        document = fetch(wayback_raw_url(timestamp, original))
        meta = parse_article(document)
        event_date = meta["published_date"] or f"{timestamp[:4]}-{timestamp[4:6]}-{timestamp[6:8]}"
        fallback_title = EVENT_TITLE_OVERRIDES.get(
            original,
            original.rsplit("/", 1)[-1].replace("-", " "),
        )
        rows.append(
            {
                "event_id": f"HE-{index:03d}",
                "road": road,
                "event_date": event_date,
                "title": meta["title"] or fallback_title,
                "description": meta["description"],
                "record_type": "historical_construction_event",
                "original_url": canonical_url(original),
                "archive_timestamp": timestamp,
                "wayback_url": wayback_view_url(timestamp, original),
                "date_source": "page_datePublished" if meta["published_date"] else "archive_capture",
            }
        )
    return sorted(rows, key=lambda row: (row["event_date"], row["road"], row["title"]))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh-cdx", action="store_true", help="Redownload Wayback CDX indexes")
    args = parser.parse_args()
    ROOT.mkdir(exist_ok=True)

    archive_records = collect_archive_records(args.refresh_cdx)
    observations = collect_overview_observations()
    projects = aggregate_projects(observations, archive_records)
    historical_events = collect_historical_events()

    write_csv(
        ROOT / "archive_records.csv",
        [
            "roads",
            "record_kind",
            "original_url",
            "first_capture_timestamp",
            "first_capture_date",
            "last_capture_timestamp",
            "capture_count",
            "wayback_url",
            "review_status",
        ],
        archive_records,
    )
    write_csv(
        ROOT / "overview_observations.csv",
        [
            "observed_date",
            "road",
            "title",
            "status",
            "project_url",
            "source_type",
            "source_url",
        ],
        observations,
    )
    write_csv(
        ROOT / "projects.csv",
        [
            "project_id",
            "road",
            "title",
            "record_type",
            "latest_status",
            "first_overview_observation",
            "last_overview_observation",
            "archive_first_capture",
            "observation_count",
            "status_history",
            "project_url",
            "description",
            "latest_source_url",
            "evidence_level",
        ],
        projects,
    )
    write_csv(
        ROOT / "historical_events.csv",
        [
            "event_id",
            "road",
            "event_date",
            "title",
            "description",
            "record_type",
            "original_url",
            "archive_timestamp",
            "wayback_url",
            "date_source",
        ],
        historical_events,
    )
    print(
        f"Wrote {len(projects)} projects, {len(observations)} overview observations, "
        f"{len(historical_events)} curated historical events and "
        f"{len(archive_records)} Wayback candidate records."
    )


if __name__ == "__main__":
    main()
