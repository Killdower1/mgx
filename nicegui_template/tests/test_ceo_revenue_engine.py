import json

import pytest

from nicegui_template.services.ceo_revenue_engine import (
    AnalysisError,
    analyze_rows,
)


def row(day, outlet, revenue, conversion_rate=99, print_rate=88, unlocks_paid=77):
    return {
        "date": day,
        "outlet_name": outlet,
        "revenue": revenue,
        "conversion_rate": conversion_rate,
        "print_rate": print_rate,
        "unlocks_paid": unlocks_paid,
    }


def test_excludes_as_of_current_partial_date():
    rows = [
        row("2026-08-22", "A", 1000000),
        row("2026-08-29", "A", 700000),
        row("2026-08-30", "A", 1),
    ]

    result = analyze_rows(rows, as_of_date="2026-08-30")

    assert result["reference_date"] == "2026-08-29"
    assert result["baseline_date"] == "2026-08-22"
    assert result["totals"]["reference_revenue"] == 700000


def test_exact_same_weekday_baseline_required():
    rows = [
        row("2026-08-21", "A", 1000000),
        row("2026-08-22", "A", 900000),
        row("2026-08-29", "A", 700000),
    ]

    result = analyze_rows(rows, as_of_date="2026-08-30")

    assert result["baseline_date"] == "2026-08-22"
    assert result["totals"]["baseline_revenue"] == 900000


def test_ranks_candidates_by_nominal_loss_then_outlet_name():
    rows = [
        row("2026-08-22", "Zeta", 1000000),
        row("2026-08-22", "Alpha", 1000000),
        row("2026-08-22", "Beta", 2000000),
        row("2026-08-29", "Zeta", 700000),
        row("2026-08-29", "Alpha", 700000),
        row("2026-08-29", "Beta", 1200000),
    ]

    result = analyze_rows(rows, as_of_date="2026-08-30")

    assert [c["outlet_name"] for c in result["candidates"]] == [
        "Beta",
        "Alpha",
        "Zeta",
    ]


def test_threshold_and_minimum_loss_must_both_match():
    rows = [
        row("2026-08-22", "SmallLoss", 1000000),
        row("2026-08-22", "SmallPct", 320000),
        row("2026-08-22", "Candidate", 1000000),
        row("2026-08-29", "SmallLoss", 920000),
        row("2026-08-29", "SmallPct", 240000),
        row("2026-08-29", "Candidate", 750000),
    ]

    result = analyze_rows(rows, as_of_date="2026-08-30")

    assert [c["outlet_name"] for c in result["candidates"]] == ["Candidate"]
    reasons = dict((e["outlet_name"], e["reason"]) for e in result["exclusions"])
    assert reasons["SmallLoss"] == "above_drop_threshold"
    assert reasons["SmallPct"] == "below_min_loss"


def test_missing_baseline_date_error():
    rows = [row("2026-08-29", "A", 700000)]

    with pytest.raises(AnalysisError) as exc:
        analyze_rows(rows, as_of_date="2026-08-30")

    assert "baseline date 2026-08-22 is absent" in str(exc.value)


def test_zero_baseline_safe_exclusion():
    rows = [
        row("2026-08-22", "Zero", 0),
        row("2026-08-22", "Negative", -1),
        row("2026-08-29", "Zero", 500000),
        row("2026-08-29", "Negative", 500000),
    ]

    result = analyze_rows(rows, as_of_date="2026-08-30")

    assert result["candidates"] == []
    assert result["coverage"]["nonpositive_baseline_outlets"] == 2
    assert set(e["reason"] for e in result["exclusions"]) == {"nonpositive_baseline"}


def test_deterministic_ordering_for_equal_losses():
    rows = [
        row("2026-08-22", "Charlie", 1000000),
        row("2026-08-22", "Bravo", 1000000),
        row("2026-08-22", "Alpha", 1000000),
        row("2026-08-29", "Charlie", 700000),
        row("2026-08-29", "Bravo", 700000),
        row("2026-08-29", "Alpha", 700000),
    ]

    result = analyze_rows(rows, as_of_date="2026-08-30")

    assert [c["outlet_name"] for c in result["candidates"]] == [
        "Alpha",
        "Bravo",
        "Charlie",
    ]


def test_json_serializable_result_and_funnel_warning():
    rows = [
        row("2026-08-22", "A", 1000000, conversion_rate=1),
        row("2026-08-29", "A", 700000, conversion_rate=100),
    ]

    result = analyze_rows(rows, as_of_date="2026-08-30")

    json.dumps(result, sort_keys=True)
    assert any("conversion_rate" in warning for warning in result["warnings"])
