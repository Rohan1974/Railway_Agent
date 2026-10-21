import pytest

from app.railway.service import RailwayError
from app.railway.tools import execute_tool

PAX = [{"name": "Rohan", "age": 28, "gender": "M"}]


def test_resolve_station_by_code_name_and_city(svc):
    assert svc.resolve_station("pune") == ["PUNE"]
    assert set(svc.resolve_station("Mumbai")) == {"CSMT", "DR", "BCT", "LTT"}
    assert svc.resolve_station("Bangalore") == ["SBC"]
    with pytest.raises(RailwayError):
        svc.resolve_station("Atlantis")


def test_search_mumbai_to_pune(svc):
    res = svc.search_trains("Mumbai", "Pune", "2026-10-22")
    numbers = {t["train_number"] for t in res["trains"]}
    assert {"12123", "12127", "11007", "12125", "11301"} <= numbers
    deps = [t["departure"] for t in res["trains"]]
    assert deps == sorted(deps)


def test_search_respects_running_days(svc):
    # 12263 runs Tue & Fri only. 2026-10-23 is a Friday, 2026-10-22 a Thursday.
    assert any(t["train_number"] == "12263" for t in svc.search_trains("PUNE", "Delhi", "2026-10-23")["trains"])
    assert not any(t["train_number"] == "12263" for t in svc.search_trains("PUNE", "Delhi", "2026-10-22")["trains"])


def test_overnight_boarding_uses_train_start_date(svc):
    # 12115 leaves CSMT 22:50 and reaches PUNE next day 02:30. Boarding at PUNE on the 23rd = train start 22nd.
    t = next(t for t in svc.search_trains("PUNE", "SUR", "2026-10-23")["trains"] if t["train_number"] == "12115")
    assert t["departure"] == "2026-10-23 02:30"


def test_search_rejects_past_and_far_dates(svc):
    with pytest.raises(RailwayError):
        svc.search_trains("CSMT", "PUNE", "2026-10-01")
    with pytest.raises(RailwayError):
        svc.search_trains("CSMT", "PUNE", "2027-03-01")


def test_fare_breakdown_and_tatkal(svc):
    gn = svc.get_fare("12123", "CSMT", "PUNE", "CC")
    tq = svc.get_fare("12123", "CSMT", "PUNE", "CC", quota="TQ", passengers=2)
    assert tq["per_passenger"]["total"] > gn["per_passenger"]["total"]
    assert tq["total_fare"] == tq["per_passenger"]["total"] * 2


def test_wrong_class_errors(svc):
    with pytest.raises(RailwayError):
        svc.get_fare("12123", "CSMT", "PUNE", "SL")


def test_book_then_pnr_then_cancel(svc):
    before = svc.check_availability("11007", "CSMT", "PUNE", "2026-10-25", "3A")["status"]
    bk = svc.book_ticket("11007", "CSMT", "PUNE", "2026-10-25", "3A", PAX)
    assert len(bk["pnr"]) == 10
    st = svc.pnr_status(bk["pnr"])
    assert st["booking_status"] == "BOOKED" and st["passengers"][0]["name"] == "Rohan"
    if before.startswith("AVAILABLE"):
        n = int(before.split()[1])
        assert bk["passengers"][0]["status"].startswith("CNF")
        assert svc.check_availability("11007", "CSMT", "PUNE", "2026-10-25", "3A")["status"] == (
            f"AVAILABLE {n - 1}" if n > 1 else "WL 1")
    c = svc.cancel_ticket(bk["pnr"])
    assert c["status"] == "CANCELLED" and c["refund_amount"] >= 0
    with pytest.raises(RailwayError):
        svc.cancel_ticket(bk["pnr"])


def test_waitlist_when_full(svc, conn):
    conn.execute("INSERT OR REPLACE INTO inventory VALUES ('12289','2026-10-26','3A',0,7)")
    bk = svc.book_ticket("12289", "CSMT", "NGP", "2026-10-26", "3A", PAX * 2)
    assert [p["status"] for p in bk["passengers"]] == ["WL 8", "WL 9"]


def test_quota_rules(svc):
    with pytest.raises(RailwayError, match="Tatkal"):
        svc.book_ticket("12123", "CSMT", "PUNE", "2026-10-25", "CC", PAX, quota="TQ")
    assert svc.book_ticket("12123", "CSMT", "PUNE", "2026-10-22", "CC", PAX, quota="TQ")["quota"] == "TQ"
    with pytest.raises(RailwayError, match="Ladies"):
        svc.book_ticket("12123", "CSMT", "PUNE", "2026-10-25", "CC", PAX, quota="LD")
    with pytest.raises(RailwayError, match="Senior"):
        svc.book_ticket("12123", "CSMT", "PUNE", "2026-10-25", "CC", PAX, quota="SS")


def test_passenger_validation(svc):
    with pytest.raises(RailwayError):
        svc.book_ticket("12123", "CSMT", "PUNE", "2026-10-25", "CC", [{"name": "X", "age": 0, "gender": "M"}])
    with pytest.raises(RailwayError):
        svc.book_ticket("12123", "CSMT", "PUNE", "2026-10-25", "CC", PAX * 7)


def test_execute_tool_wraps_errors(svc):
    res, ok = execute_tool(svc, "pnr_status", {"pnr": "0000000000"})
    assert not ok and "not found" in res["error"]
    res, ok = execute_tool(svc, "search_trains", {"from_station": "CSMT"})
    assert not ok and "Bad arguments" in res["error"]
    res, ok = execute_tool(svc, "delete_everything", {})
    assert not ok
