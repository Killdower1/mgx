import json
from datetime import date, datetime, timedelta


FUNNEL_WARNING = (
    "Scoring hanya memakai revenue; conversion_rate, print_rate, dan "
    "unlocks_paid dikecualikan pending semantic audit."
)


class AnalysisError(Exception):
    """Raised when the requested comparison dates cannot be analyzed."""


def load_rows(path):
    with open(path, "r") as handle:
        rows = json.load(handle)
    if not isinstance(rows, list):
        raise AnalysisError("daily summary data must be a JSON list")
    return rows


def analyze_file(path, as_of_date, drop_pct=-20.0, min_loss=100000.0, top=None):
    return analyze_rows(
        load_rows(path),
        as_of_date=as_of_date,
        drop_pct=drop_pct,
        min_loss=min_loss,
        top=top,
    )


def analyze_rows(rows, as_of_date, drop_pct=-20.0, min_loss=100000.0, top=None):
    as_of = _parse_date(as_of_date, "as_of_date")
    by_date = _index_revenue(rows)
    available_dates = sorted(by_date.keys())
    reference = _latest_before(available_dates, as_of)
    if reference is None:
        raise AnalysisError(
            "no completed reference date exists before as_of date %s" % as_of.isoformat()
        )

    baseline = reference - timedelta(days=7)
    if baseline not in by_date:
        raise AnalysisError(
            "baseline date %s is absent for reference date %s"
            % (baseline.isoformat(), reference.isoformat())
        )

    reference_revenue = by_date[reference]
    baseline_revenue = by_date[baseline]
    result = _compare_dates(
        reference,
        baseline,
        reference_revenue,
        baseline_revenue,
        float(drop_pct),
        float(min_loss),
    )
    if top is not None:
        result["candidates"] = result["candidates"][: int(top)]
    return result


def _compare_dates(reference, baseline, reference_revenue, baseline_revenue, drop_pct, min_loss):
    candidates = []
    exclusions = []
    compared = 0
    missing_baseline = 0
    nonpositive_baseline = 0

    reference_names = sorted(reference_revenue.keys())
    for outlet_name in reference_names:
        current = reference_revenue[outlet_name]
        if outlet_name not in baseline_revenue:
            missing_baseline += 1
            exclusions.append(_exclusion(outlet_name, "missing_baseline", current, None))
            continue

        base = baseline_revenue[outlet_name]
        if base <= 0:
            nonpositive_baseline += 1
            exclusions.append(_exclusion(outlet_name, "nonpositive_baseline", current, base))
            continue

        compared += 1
        delta_amount = current - base
        delta_pct = (delta_amount / base) * 100.0
        nominal_loss = base - current

        if delta_pct > drop_pct:
            exclusions.append(
                _exclusion(outlet_name, "above_drop_threshold", current, base, delta_amount, delta_pct)
            )
            continue
        if nominal_loss < min_loss:
            exclusions.append(
                _exclusion(outlet_name, "below_min_loss", current, base, delta_amount, delta_pct)
            )
            continue

        candidates.append(
            {
                "outlet_name": outlet_name,
                "reference_revenue": current,
                "baseline_revenue": base,
                "delta_amount": delta_amount,
                "delta_pct": delta_pct,
                "nominal_loss": nominal_loss,
            }
        )

    candidates.sort(key=lambda item: (-item["nominal_loss"], item["outlet_name"]))
    exclusions.sort(key=lambda item: (item["reason"], item["outlet_name"]))

    reference_total = sum(reference_revenue.values())
    baseline_total = sum(baseline_revenue.values())
    total_delta = reference_total - baseline_total
    total_delta_pct = None
    if baseline_total > 0:
        total_delta_pct = (total_delta / baseline_total) * 100.0

    return {
        "reference_date": reference.isoformat(),
        "baseline_date": baseline.isoformat(),
        "totals": {
            "reference_revenue": reference_total,
            "baseline_revenue": baseline_total,
            "delta_amount": total_delta,
            "delta_pct": total_delta_pct,
        },
        "coverage": {
            "reference_outlets": len(reference_revenue),
            "baseline_outlets": len(baseline_revenue),
            "compared_outlets": compared,
            "candidate_outlets": len(candidates),
            "excluded_outlets": len(exclusions),
            "missing_baseline_outlets": missing_baseline,
            "nonpositive_baseline_outlets": nonpositive_baseline,
        },
        "thresholds": {
            "drop_pct": drop_pct,
            "min_loss": min_loss,
        },
        "candidates": candidates,
        "exclusions": exclusions,
        "warnings": [FUNNEL_WARNING],
    }


def _exclusion(outlet_name, reason, current, base, delta_amount=None, delta_pct=None):
    return {
        "outlet_name": outlet_name,
        "reason": reason,
        "reference_revenue": current,
        "baseline_revenue": base,
        "delta_amount": delta_amount,
        "delta_pct": delta_pct,
    }


def _index_revenue(rows):
    by_date = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise AnalysisError("row %s is not an object" % index)
        if "date" not in row or "outlet_name" not in row:
            raise AnalysisError("row %s is missing date or outlet_name" % index)
        day = _parse_date(row["date"], "row %s date" % index)
        outlet_name = str(row["outlet_name"])
        revenue = _to_float(row.get("revenue", 0))
        by_date.setdefault(day, {})
        by_date[day][outlet_name] = by_date[day].get(outlet_name, 0.0) + revenue
    return by_date


def _parse_date(value, label):
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            raise AnalysisError("%s must use YYYY-MM-DD" % label)
    raise AnalysisError("%s must be a date or YYYY-MM-DD string" % label)


def _latest_before(available_dates, as_of):
    completed = [day for day in available_dates if day < as_of]
    if not completed:
        return None
    return completed[-1]


def _to_float(value):
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        raise AnalysisError("revenue values must be numeric")
