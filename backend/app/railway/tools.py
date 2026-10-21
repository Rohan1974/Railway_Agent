"""Tool definitions shared by both agent modes (Anthropic tool format) + dispatcher."""
from __future__ import annotations

from typing import Any

from .service import RailwayError, RailwayService

_STATION = {"type": "string", "description": "Station code (e.g. PUNE, CSMT) or city/station name (e.g. Mumbai)."}
_DATE = {"type": "string", "description": "Journey date in YYYY-MM-DD."}
_CLASS = {"type": "string", "enum": ["SL", "3A", "2A", "1A", "CC", "EC"],
          "description": "SL=Sleeper, 3A=AC 3 Tier, 2A=AC 2 Tier, 1A=AC First, CC=AC Chair Car, EC=Executive Chair Car."}
_QUOTA = {"type": "string", "enum": ["GN", "TQ", "LD", "SS"],
          "description": "GN=General, TQ=Tatkal, LD=Ladies, SS=Senior Citizen. Default GN."}
_TRAIN = {"type": "string", "description": "5-digit train number, e.g. 12123."}

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {"name": "search_trains",
     "description": "Find trains between two stations on a date, with seat availability per class.",
     "input_schema": {"type": "object", "properties": {
         "from_station": _STATION, "to_station": _STATION, "journey_date": _DATE, "travel_class": _CLASS},
         "required": ["from_station", "to_station", "journey_date"]}},
    {"name": "check_availability",
     "description": "Check seat availability for one train, class and date.",
     "input_schema": {"type": "object", "properties": {
         "train_number": _TRAIN, "from_station": _STATION, "to_station": _STATION,
         "journey_date": _DATE, "travel_class": _CLASS},
         "required": ["train_number", "from_station", "to_station", "journey_date", "travel_class"]}},
    {"name": "get_fare",
     "description": "Get the fare breakdown for a train, class and quota.",
     "input_schema": {"type": "object", "properties": {
         "train_number": _TRAIN, "from_station": _STATION, "to_station": _STATION, "travel_class": _CLASS,
         "quota": _QUOTA, "passengers": {"type": "integer", "minimum": 1, "maximum": 6}},
         "required": ["train_number", "from_station", "to_station", "travel_class"]}},
    {"name": "book_ticket",
     "description": "Book a ticket. Only call after the user has explicitly confirmed train, class, date and passengers.",
     "input_schema": {"type": "object", "properties": {
         "train_number": _TRAIN, "from_station": _STATION, "to_station": _STATION, "journey_date": _DATE,
         "travel_class": _CLASS, "quota": _QUOTA,
         "passengers": {"type": "array", "minItems": 1, "maxItems": 6, "items": {
             "type": "object", "properties": {
                 "name": {"type": "string"}, "age": {"type": "integer"},
                 "gender": {"type": "string", "enum": ["M", "F", "T"]},
                 "berth_pref": {"type": "string", "enum": ["LB", "MB", "UB", "SL", "SU", "WS", "NONE"]}},
             "required": ["name", "age", "gender"]}}},
         "required": ["train_number", "from_station", "to_station", "journey_date", "travel_class", "passengers"]}},
    {"name": "pnr_status",
     "description": "Get booking and passenger status for a 10-digit PNR.",
     "input_schema": {"type": "object", "properties": {"pnr": {"type": "string"}}, "required": ["pnr"]}},
    {"name": "cancel_ticket",
     "description": "Cancel a booking by PNR. Only call after the user has explicitly confirmed cancellation.",
     "input_schema": {"type": "object", "properties": {"pnr": {"type": "string"}}, "required": ["pnr"]}},
]

TOOL_NAMES = {t["name"] for t in TOOL_SCHEMAS}


def execute_tool(service: RailwayService, name: str, args: dict[str, Any]) -> tuple[dict, bool]:
    """Run a tool. Returns (result, ok). Validation errors come back as {'error': ...}, ok=False."""
    if name not in TOOL_NAMES:
        return {"error": f"Unknown tool {name}."}, False
    try:
        return getattr(service, name)(**args), True
    except RailwayError as e:
        return {"error": str(e)}, False
    except TypeError as e:  # wrong/missing arguments from the model
        return {"error": f"Bad arguments for {name}: {e}"}, False
