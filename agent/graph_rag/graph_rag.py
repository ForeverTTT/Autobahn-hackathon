"""
Local Graph RAG backed by data_autobahn CSV tables.

This module intentionally does not materialize every forecast row as graph nodes.
It exposes a small Cypher-like query surface and pushes filters into the existing
date-partitioned PredictionDataLoader, keeping query cost bounded by one day of
traffic data in normal agent usage.
"""
import re
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

from ..tools.data_loader import DATA_DIR, PredictionDataLoader, prediction_loader, read_data_autobahn_csv, safe_int, safe_number

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False


class CypherQueryError(ValueError):
    """Raised when the local Cypher subset cannot be executed efficiently."""


class GraphRAG:
    """
    A virtual traffic knowledge graph with a constrained Cypher query interface.

    Supported labels:
    - Site: measurement station metadata derived from data_autobahn/合并表格，小时交通流量.csv
    - Road: road nodes derived from Site metadata
    - Forecast: hourly forecasts from data_autobahn/forecast_2026_2029.csv
    - Factor: date/road impact factors from data_autobahn daily CSV tables

    Supported query shape examples:
    - MATCH (s:Site {road: $road}) RETURN s LIMIT 10
    - MATCH (s:Site {site_id: $site_id})-[:HAS_FORECAST]->(f:Forecast {date: $date}) RETURN s, f ORDER BY f.hour
    - MATCH (f:Forecast) WHERE f.date = $date AND f.road = $road AND f.hour IN $hours RETURN f
    - MATCH (x:Factor {date: $date, road: $road}) RETURN x
    """

    NODE_PATTERN = re.compile(
        r"\((?P<alias>\w+)\s*:\s*(?P<label>\w+)(?:\s*\{(?P<props>[^}]*)\})?\)",
        re.IGNORECASE,
    )

    def __init__(self, loader: Optional[PredictionDataLoader] = None):
        self.loader = loader or prediction_loader
        self._initialized = False
        self._site_rows: List[Dict[str, Any]] = []
        self._site_by_id: Dict[str, Dict[str, Any]] = {}
        self._roads: List[str] = []
        self._weather_daily = None
        self._construction_daily = None
        self._holiday_daily = None
        self._event_daily = None

    async def initialize(self) -> bool:
        """Load small metadata/factor tables. Forecast rows stay lazy."""
        if self._initialized:
            return True

        if not HAS_PANDAS:
            raise ImportError("pandas is required for GraphRAG")

        self._load_site_meta()
        self._load_external_tables()
        self._initialized = True
        return True

    def _ensure_initialized(self) -> None:
        if not self._initialized:
            self._load_site_meta()
            self._load_external_tables()
            self._initialized = True

    def _load_site_meta(self) -> None:
        site_path = DATA_DIR / "合并表格，小时交通流量.csv"
        if site_path.exists():
            df = read_data_autobahn_csv(
                site_path,
                usecols=["road", "direction", "site_name", "bab_km", "longitude", "latitude"],
            ).drop_duplicates(subset=["road", "direction", "site_name"])
            df["site_id"] = df["road"].astype(str) + "_" + df["direction"].astype(str) + "_" + df["site_name"].astype(str)
            df["longitude"] = df["longitude"].apply(self._parse_number)
            df["latitude"] = df["latitude"].apply(self._parse_number)
            df["bab_km"] = df["bab_km"].apply(self._parse_number)
            self._site_rows = [self._site_node(row) for row in df.to_dict("records")]
        else:
            site_ids = self.loader.get_available_sites()
            self._site_rows = [
                self._site_node({
                    "site_id": site_id,
                    "road": site_id.split("_")[0],
                    "direction": site_id.split("_")[1] if "_" in site_id else "",
                    "site_name": site_id,
                })
                for site_id in site_ids
            ]

        self._site_by_id = {row["site_id"]: row for row in self._site_rows}
        self._roads = sorted({row.get("road") for row in self._site_rows if row.get("road")})

    def _load_external_tables(self) -> None:
        weather_path = DATA_DIR / "合并表格，weather日级.csv"
        construction_path = DATA_DIR / "合并表格，construction日级.csv"
        holiday_path = DATA_DIR / "合并表格，holiday日级.csv"
        event_path = DATA_DIR / "合并表格，special_events日级.csv"

        if weather_path.exists():
            self._weather_daily = read_data_autobahn_csv(weather_path)
            self._weather_daily["date"] = pd.to_datetime(self._weather_daily["date"]).dt.strftime("%Y-%m-%d")

        if construction_path.exists():
            self._construction_daily = read_data_autobahn_csv(construction_path)
            self._construction_daily["date"] = pd.to_datetime(self._construction_daily["date"]).dt.strftime("%Y-%m-%d")

        if holiday_path.exists():
            self._holiday_daily = read_data_autobahn_csv(holiday_path)
            self._holiday_daily["date"] = pd.to_datetime(self._holiday_daily["date"]).dt.strftime("%Y-%m-%d")

        if event_path.exists():
            self._event_daily = read_data_autobahn_csv(event_path)
            self._event_daily["date"] = pd.to_datetime(self._event_daily["date"]).dt.strftime("%Y-%m-%d")

    def query(self, cypher: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Alias for query_cypher."""
        return self.query_cypher(cypher, params)

    def query_cypher(self, cypher: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Execute a constrained, read-only Cypher-like query."""
        self._ensure_initialized()

        params = params or {}
        query = " ".join(cypher.strip().split())
        if not query.lower().startswith("match "):
            raise CypherQueryError("Only read-only MATCH queries are supported")

        nodes = self._parse_nodes(query, params)
        where_props = self._parse_where(query, params)
        for alias, props in where_props.items():
            nodes.setdefault(alias, {"label": "", "props": {}})["props"].update(props)

        labels = {node["label"].lower() for node in nodes.values()}

        if "forecast" in labels:
            rows = self._query_forecast_rows(nodes, query)
        elif "factor" in labels:
            rows = self._query_factor_rows(nodes, query)
        elif "site" in labels:
            rows = self._query_site_rows(nodes, query)
        elif "road" in labels:
            rows = self._query_road_rows(nodes, query)
        else:
            raise CypherQueryError(f"Unsupported labels: {sorted(labels)}")

        rows = self._order_rows(rows, query)
        rows = self._project_rows(rows, query)
        return self._limit_rows(rows, query, params)

    def get_statistics(self) -> Dict[str, Any]:
        self._ensure_initialized()
        start_date, end_date = self.loader.get_date_range()
        return {
            "backend": "local_table_graph",
            "cypher": "constrained_read_only_subset",
            "nodes": {
                "Road": len(self._roads),
                "Site": len(self._site_rows),
                "Forecast": "lazy_from_data_autobahn_forecast_csv",
                "Factor": "from_data_autobahn_daily_csv",
            },
            "relationships": [
                "(:Site)-[:ON_ROAD]->(:Road)",
                "(:Site)-[:HAS_FORECAST]->(:Forecast)",
                "(:Factor)-[:AFFECTS]->(:Road|:Site)",
            ],
            "forecast_date_range": {"start": start_date, "end": end_date},
            "roads": self._roads,
            "site_count": len(self._site_rows),
        }

    def query_factors(self, segment_id: str, date: str) -> Dict[str, Any]:
        self._ensure_initialized()
        road = self._infer_road(segment_id)
        return {
            "segment_id": segment_id,
            "road": road,
            "date": date,
            "factors": self._factor_nodes(date=date, road=road, site_id=segment_id),
        }

    def explain_congestion(self, segment_id: str, date: str, hour: int) -> Dict[str, Any]:
        self._ensure_initialized()
        road = self._infer_road(segment_id)
        records = self._forecast_records(date=date, road=road, site_id=segment_id, hours=[hour])
        if not records and road:
            records = self._forecast_records(date=date, road=road, hours=[hour])

        forecast = records[0] if records else None
        factors = self._factor_nodes(date=date, road=road, site_id=segment_id)

        reasons: List[str] = []
        if forecast:
            speed = forecast.get("v_kfz_pred", forecast.get("v_kfz_p50"))
            volume = forecast.get("kfz_h_p50")
            interval = forecast.get("interval_width")
            if volume is not None:
                reasons.append(f"Predicted median flow is {volume:.0f} vehicles/hour")
            if speed is not None:
                reasons.append(f"Predicted average speed is {speed:.1f} km/h")
            if interval is not None and interval > 250:
                reasons.append("Forecast uncertainty is elevated")

        for factor in factors:
            if factor.get("impact") in {"moderate", "high", "very_high"}:
                reasons.append(factor.get("description", factor.get("name", "External factor detected")))

        return {
            "segment_id": segment_id,
            "road": road,
            "date": date,
            "hour": hour,
            "forecast": forecast,
            "factors": factors,
            "reasons": reasons,
            "summary": "; ".join(reasons) if reasons else "No strong congestion driver found in local graph data.",
        }

    def get_user_relevant_info(self, user_type: str, date: str, road: str = "A8") -> Dict[str, Any]:
        records = self._forecast_records(date=date, road=road, hours=list(range(6, 22)))
        factors = self._factor_nodes(date=date, road=road)
        peak = max(records, key=lambda row: row.get("kfz_h_p50", 0), default=None)
        best = max(records, key=lambda row: row.get("v_kfz_pred", row.get("v_kfz_p50", 0)), default=None)
        return {
            "user_type": user_type,
            "date": date,
            "road": road,
            "peak_hour": peak.get("hour") if peak else None,
            "best_hour": best.get("hour") if best else None,
            "factors": factors,
            "records_considered": len(records),
        }

    def _query_forecast_rows(self, nodes: Dict[str, Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
        forecast_alias, forecast_props = self._props_for_label(nodes, "Forecast")
        site_alias, site_props = self._props_for_label(nodes, "Site")
        road_alias, road_props = self._props_for_label(nodes, "Road")

        props = dict(forecast_props)
        props.update({k: v for k, v in site_props.items() if k in {"site_id", "road", "direction"}})
        if "id" in site_props and "site_id" not in props:
            props["site_id"] = site_props["id"]
        if "id" in road_props and "road" not in props:
            props["road"] = road_props["id"]

        date = props.get("date")
        if not date:
            raise CypherQueryError("Forecast queries require a date predicate for performance")

        hours = props.get("hours")
        if "hour" in props:
            hours = props["hour"] if isinstance(props["hour"], list) else [props["hour"]]

        records = self._forecast_records(
            date=str(date),
            site_id=props.get("site_id"),
            road=props.get("road"),
            direction=props.get("direction"),
            hours=hours,
        )

        rows: List[Dict[str, Any]] = []
        for record in records:
            site = self._site_by_id.get(record.get("site_id"), self._site_node(record))
            row = {
                forecast_alias or "f": self._forecast_node(record),
                "f": self._forecast_node(record),
                "forecast": self._forecast_node(record),
                "s": site,
                "site": site,
                "r": self._road_node(record.get("road")),
                "road": self._road_node(record.get("road")),
            }
            if site_alias:
                row[site_alias] = site
            if road_alias:
                row[road_alias] = self._road_node(record.get("road"))
            rows.append(row)
        return rows

    def _query_factor_rows(self, nodes: Dict[str, Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
        alias, props = self._props_for_label(nodes, "Factor")
        date = props.get("date")
        if not date:
            raise CypherQueryError("Factor queries require a date predicate")
        road = props.get("road") or props.get("road_id")
        site_id = props.get("site_id") or props.get("segment_id")
        factors = self._factor_nodes(date=str(date), road=road, site_id=site_id)
        factor_alias = alias or "x"
        return [{factor_alias: factor, "x": factor, "factor": factor} for factor in factors]

    def _query_site_rows(self, nodes: Dict[str, Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
        alias, props = self._props_for_label(nodes, "Site")
        site_alias = alias or "s"
        sites = self._filter_nodes(self._site_rows, props)
        return [{site_alias: site, "s": site, "site": site} for site in sites]

    def _query_road_rows(self, nodes: Dict[str, Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
        alias, props = self._props_for_label(nodes, "Road")
        road_alias = alias or "r"
        roads = [self._road_node(road) for road in self._roads]
        roads = self._filter_nodes(roads, props)
        return [{road_alias: road, "r": road, "road": road} for road in roads]

    def _forecast_records(
        self,
        date: str,
        site_id: Optional[str] = None,
        road: Optional[str] = None,
        direction: Optional[str] = None,
        hours: Optional[Iterable[int]] = None,
    ) -> List[Dict[str, Any]]:
        hour_list = [int(hour) for hour in hours] if hours is not None else None
        records = self.loader.query(date=date, site_id=site_id, road=road, direction=direction, hours=hour_list)
        return [self._normalize_record(record) for record in records]

    def _factor_nodes(self, date: str, road: Optional[str] = None, site_id: Optional[str] = None) -> List[Dict[str, Any]]:
        factors: List[Dict[str, Any]] = []
        road = road or self._infer_road(site_id)

        weather = self._weather_factor(date)
        if weather:
            factors.append(weather)

        factors.extend(self._holiday_factors(date, road))
        factors.extend(self._construction_factors(date, road))
        factors.extend(self._event_factors(date, road))
        factors.extend(self._calendar_factors(date, road))
        return factors

    def _weather_factor(self, date: str) -> Optional[Dict[str, Any]]:
        if self._weather_daily is not None:
            rows = self._weather_daily[self._weather_daily["date"] == date]
            if len(rows) > 0:
                row = rows.iloc[0].to_dict()
                return {
                    "_label": "Factor",
                    "id": f"weather:{date}",
                    "type": "weather",
                    "date": date,
                    "name": "Daily weather",
                    "impact": self._weather_impact(row),
                    "description": self._weather_description(row),
                    "properties": row,
                }

        return None

    def _holiday_factors(self, date: str, road: Optional[str]) -> List[Dict[str, Any]]:
        if self._holiday_daily is None:
            return []
        rows = self._holiday_daily[self._holiday_daily["date"] == date]
        if len(rows) == 0:
            return []

        row = rows.iloc[0].to_dict()
        factors = []
        school_count = safe_int(row.get("school_holiday_count"))
        public_count = safe_int(row.get("public_holiday_count"))
        risk = row.get("window_risk_level")

        if public_count > 0:
            names = self._join_non_empty([
                row.get("public_names_DE_BY"),
                row.get("public_names_AT_SB"),
                row.get("public_names_AT_TI"),
            ])
            factors.append({
                "_label": "Factor",
                "id": f"holiday:public:{date}",
                "type": "public_holiday",
                "date": date,
                "road": road,
                "name": names or "Public holiday",
                "impact": "high" if public_count >= 2 else "moderate",
                "description": f"Public holiday in {public_count} region(s): {names}" if names else f"Public holiday in {public_count} region(s)",
                "properties": row,
            })

        if school_count > 0:
            names = self._join_non_empty([
                row.get("school_names_DE_BY"),
                row.get("school_names_AT_SB"),
                row.get("school_names_AT_TI"),
            ])
            factors.append({
                "_label": "Factor",
                "id": f"holiday:school:{date}",
                "type": "school_holiday",
                "date": date,
                "road": road,
                "name": names or "School holiday",
                "impact": "high" if school_count >= 2 else "moderate",
                "description": f"School holiday in {school_count} region(s): {names}" if names else f"School holiday in {school_count} region(s)",
                "properties": row,
            })

        if safe_int(row.get("in_traffic_window")) > 0:
            factors.append({
                "_label": "Factor",
                "id": f"holiday:traffic_window:{date}",
                "type": "holiday_traffic_window",
                "date": date,
                "road": road,
                "name": "Holiday traffic window",
                "impact": "high" if str(risk).lower() == "high" else "moderate",
                "description": f"Holiday traffic window active, direction={row.get('window_direction')}, risk={risk}",
                "properties": row,
            })

        return factors

    def _construction_factors(self, date: str, road: Optional[str]) -> List[Dict[str, Any]]:
        if self._construction_daily is None:
            return []
        rows = self._construction_daily[self._construction_daily["date"] == date]

        factors = []
        for row in rows.to_dict("records"):
            if not safe_int(row.get("has_construction")):
                continue
            if road == "A8" and not safe_int(row.get("has_a8_construction")):
                continue
            if road == "A93" and not safe_int(row.get("has_a93_construction")):
                continue

            road_count = row.get("a8_construction_count") if road == "A8" else row.get("a93_construction_count") if road == "A93" else row.get("construction_count")
            has_2_plus_0 = safe_int(row.get("has_2_plus_0")) > 0
            factors.append({
                "_label": "Factor",
                "id": f"construction:{date}:{road or 'all'}",
                "type": "construction",
                "date": date,
                "road": road,
                "name": "Active construction",
                "impact": "high" if has_2_plus_0 or safe_int(row.get("max_closed_lanes")) >= 2 else "moderate",
                "description": f"{road_count or row.get('construction_count', 0)} construction record(s); roads={row.get('active_roads', '')}; types={row.get('display_types', '')}",
                "properties": row,
                "active_sites": row.get("construction_titles"),
            })
        return factors

    def _event_factors(self, date: str, road: Optional[str]) -> List[Dict[str, Any]]:
        if self._event_daily is None:
            return []
        rows = self._event_daily[self._event_daily["date"] == date]
        if len(rows) == 0:
            return []

        factors = []
        for row in rows.to_dict("records"):
            if not safe_int(row.get("has_special_event")):
                continue
            if road == "A8" and not safe_int(row.get("affects_a8_ost")):
                continue
            if road == "A93" and not safe_int(row.get("affects_a93_sued")):
                continue

            impact_score = safe_int(row.get("impact_score"))
            impact = "high" if impact_score >= 3 else "moderate" if impact_score >= 2 else "low"
            factors.append({
                "_label": "Factor",
                "id": f"event:{date}:{road or 'all'}",
                "type": "special_event",
                "date": date,
                "road": road,
                "name": row.get("active_event_names") or "Special event",
                "impact": impact,
                "description": f"{row.get('active_event_count', 0)} event(s): {row.get('active_event_names', '')}; cities={row.get('active_event_cities', '')}",
                "properties": row,
            })
        return factors

    def _calendar_factors(self, date: str, road: Optional[str]) -> List[Dict[str, Any]]:
        dt = datetime.strptime(date, "%Y-%m-%d")
        factors = []
        if dt.weekday() == 4:
            factors.append(self._calendar_node(date, road, "friday_departure", "Friday departure traffic", "moderate"))
        elif dt.weekday() == 5:
            factors.append(self._calendar_node(date, road, "saturday_leisure", "Saturday leisure travel", "moderate"))
        elif dt.weekday() == 6:
            factors.append(self._calendar_node(date, road, "sunday_return", "Sunday return traffic", "moderate"))
        if dt.month in {7, 8}:
            factors.append(self._calendar_node(date, road, "summer_tourism", "Summer tourist traffic towards the Alps", "high"))
        return factors

    def _calendar_node(self, date: str, road: Optional[str], factor_type: str, description: str, impact: str) -> Dict[str, Any]:
        return {
            "_label": "Factor",
            "id": f"calendar:{date}:{factor_type}",
            "type": factor_type,
            "date": date,
            "road": road,
            "name": factor_type,
            "impact": impact,
            "description": description,
        }

    def _parse_nodes(self, query: str, params: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        nodes: Dict[str, Dict[str, Any]] = {}
        for match in self.NODE_PATTERN.finditer(query):
            alias = match.group("alias")
            nodes[alias] = {
                "label": match.group("label"),
                "props": self._parse_props(match.group("props") or "", params),
            }
        return nodes

    def _parse_props(self, props: str, params: Dict[str, Any]) -> Dict[str, Any]:
        parsed: Dict[str, Any] = {}
        if not props.strip():
            return parsed
        for item in props.split(","):
            if ":" not in item:
                continue
            key, value = item.split(":", 1)
            parsed[key.strip()] = self._resolve_value(value.strip(), params)
        return parsed

    def _parse_where(self, query: str, params: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        where_match = re.search(r"\bWHERE\b\s+(.*?)(?:\bRETURN\b|\bORDER\b|\bLIMIT\b|$)", query, re.IGNORECASE)
        if not where_match:
            return {}
        where = where_match.group(1)
        parsed: Dict[str, Dict[str, Any]] = {}
        conditions = re.split(r"\s+AND\s+", where, flags=re.IGNORECASE)
        for condition in conditions:
            in_match = re.match(r"(\w+)\.(\w+)\s+IN\s+(.+)", condition.strip(), re.IGNORECASE)
            eq_match = re.match(r"(\w+)\.(\w+)\s*=\s*(.+)", condition.strip(), re.IGNORECASE)
            if in_match:
                alias, prop, value = in_match.groups()
                parsed.setdefault(alias, {})[prop] = self._resolve_value(value, params)
            elif eq_match:
                alias, prop, value = eq_match.groups()
                parsed.setdefault(alias, {})[prop] = self._resolve_value(value, params)
        return parsed

    def _resolve_value(self, value: str, params: Dict[str, Any]) -> Any:
        value = value.strip().rstrip(")")
        if value.startswith("$"):
            return params.get(value[1:])
        if value.startswith("'") and value.endswith("'"):
            return value[1:-1]
        if value.startswith('"') and value.endswith('"'):
            return value[1:-1]
        if value.startswith("[") and value.endswith("]"):
            items = [item.strip() for item in value[1:-1].split(",") if item.strip()]
            return [self._resolve_value(item, params) for item in items]
        if re.match(r"^-?\d+$", value):
            return int(value)
        if re.match(r"^-?\d+\.\d+$", value):
            return float(value)
        return value

    def _props_for_label(self, nodes: Dict[str, Dict[str, Any]], label: str) -> Tuple[Optional[str], Dict[str, Any]]:
        for alias, node in nodes.items():
            if node.get("label", "").lower() == label.lower():
                return alias, dict(node.get("props", {}))
        return None, {}

    def _project_rows(self, rows: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
        return_match = re.search(r"\bRETURN\b\s+(.*?)(?:\bORDER\b|\bLIMIT\b|$)", query, re.IGNORECASE)
        if not return_match:
            return rows
        items = [item.strip() for item in return_match.group(1).split(",")]
        if len(items) == 1 and items[0] == "*":
            return rows

        count_match = re.match(r"count\((\w+)\)(?:\s+AS\s+(\w+))?", items[0], re.IGNORECASE)
        if count_match:
            key = count_match.group(2) or "count"
            return [{key: len(rows)}]

        projected = []
        for row in rows:
            out: Dict[str, Any] = {}
            for item in items:
                expr, alias = self._return_alias(item)
                if "." in expr:
                    node_alias, prop = expr.split(".", 1)
                    out[alias or prop] = row.get(node_alias, {}).get(prop)
                else:
                    out[alias or expr] = row.get(expr)
            projected.append(out)
        return projected

    def _return_alias(self, item: str) -> Tuple[str, Optional[str]]:
        parts = re.split(r"\s+AS\s+", item, flags=re.IGNORECASE)
        if len(parts) == 2:
            return parts[0].strip(), parts[1].strip()
        return item.strip(), None

    def _order_rows(self, rows: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
        order_match = re.search(r"\bORDER\s+BY\b\s+(\w+)\.(\w+)(?:\s+(ASC|DESC))?", query, re.IGNORECASE)
        if not order_match:
            return rows
        alias, prop, direction = order_match.groups()
        reverse = (direction or "ASC").upper() == "DESC"
        return sorted(rows, key=lambda row: row.get(alias, {}).get(prop, 0), reverse=reverse)

    def _limit_rows(self, rows: List[Dict[str, Any]], query: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        limit_match = re.search(r"\bLIMIT\b\s+(\$?\w+)", query, re.IGNORECASE)
        if not limit_match:
            return rows
        raw = limit_match.group(1)
        limit = params.get(raw[1:], len(rows)) if raw.startswith("$") else int(raw)
        return rows[: int(limit)]

    def _filter_nodes(self, nodes: List[Dict[str, Any]], props: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not props:
            return nodes
        filtered = []
        for node in nodes:
            keep = True
            for key, value in props.items():
                node_value = node.get(key)
                if key == "id" and node_value is None:
                    node_value = node.get("site_id") or node.get("road")
                if isinstance(value, list):
                    keep = node_value in value
                else:
                    keep = node_value == value
                if not keep:
                    break
            if keep:
                filtered.append(node)
        return filtered

    def _normalize_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        normalized = dict(record)
        if "sv_h_pred" in normalized and "sv_h_p50" not in normalized:
            normalized["sv_h_p50"] = normalized["sv_h_pred"]
        if "v_kfz_pred" in normalized and "v_kfz_p50" not in normalized:
            normalized["v_kfz_p50"] = normalized["v_kfz_pred"]
        return normalized

    def _parse_number(self, value: Any) -> Optional[float]:
        if value is None or pd.isna(value):
            return None
        try:
            return float(str(value).replace(",", "."))
        except ValueError:
            return None

    def _join_non_empty(self, values: List[Any]) -> str:
        items = []
        for value in values:
            if value is None or pd.isna(value):
                continue
            text = str(value).strip()
            if text:
                items.append(text)
        return "; ".join(dict.fromkeys(items))

    def _site_node(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return {"_label": "Site", **row, "id": row.get("site_id")}

    def _road_node(self, road: Optional[str]) -> Dict[str, Any]:
        return {"_label": "Road", "id": road, "road": road, "name": road}

    def _forecast_node(self, record: Dict[str, Any]) -> Dict[str, Any]:
        return {"_label": "Forecast", **record}

    def _infer_road(self, segment_id: Optional[str]) -> Optional[str]:
        if not segment_id:
            return None
        if segment_id in self._site_by_id:
            return self._site_by_id[segment_id].get("road")
        if segment_id.startswith("A8"):
            return "A8"
        if segment_id.startswith("A93"):
            return "A93"
        return None

    def _weather_impact(self, row: Dict[str, Any]) -> str:
        observed = safe_int(row.get("has_observed_weather")) > 0
        has_ice_risk = safe_int(row.get("has_ice_risk")) > 0 if observed else safe_number(row.get("ice_risk_prob")) > 0.25
        snowfall = safe_number(row.get("snowfall_mm")) if observed else 0.0
        precip = safe_number(row.get("precip_mm")) if observed else safe_number(row.get("precip_mm_p90"))
        low_vis = safe_number(row.get("low_vis_hours")) if observed else safe_number(row.get("low_vis_hours_mean"))
        if has_ice_risk or snowfall > 5:
            return "high"
        if precip > 10 or low_vis >= 3:
            return "moderate"
        return "low"

    def _weather_description(self, row: Dict[str, Any]) -> str:
        observed = safe_int(row.get("has_observed_weather")) > 0
        precip = safe_number(row.get("precip_mm")) if observed else safe_number(row.get("precip_mm_mean"))
        snowfall = safe_number(row.get("snowfall_mm")) if observed else 0.0
        low_vis = safe_number(row.get("low_vis_hours")) if observed else safe_number(row.get("low_vis_hours_mean"))
        return (
            f"Weather ({row.get('weather_source', 'unknown')}): {precip:.1f} mm rain, "
            f"{snowfall:.1f} mm snow, "
            f"{low_vis:.1f} low-visibility hours"
        )