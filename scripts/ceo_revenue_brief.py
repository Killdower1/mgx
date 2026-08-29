#!/usr/bin/env python3
import argparse
import json
import os
import sys
from datetime import datetime, timedelta


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

DEFAULT_DATA = os.path.join(
    REPO_ROOT,
    "streamlit_template",
    "data",
    "api_cache",
    "daily_summary.json",
)


def main(argv=None):
    from nicegui_template.services.ceo_revenue_engine import AnalysisError, analyze_file

    parser = argparse.ArgumentParser(description="CEO revenue drop brief")
    parser.add_argument("--data", default=DEFAULT_DATA)
    parser.add_argument("--as-of", default=_jakarta_today())
    parser.add_argument("--drop-pct", type=float, default=-20.0)
    parser.add_argument("--min-loss", type=float, default=100000.0)
    parser.add_argument("--top", type=int, default=None)
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args(argv)

    try:
        result = analyze_file(
            args.data,
            as_of_date=args.as_of,
            drop_pct=args.drop_pct,
            min_loss=args.min_loss,
            top=args.top,
        )
    except (AnalysisError, IOError, OSError) as exc:
        message = "ERROR: %s" % exc
        if args.json_output:
            sys.stderr.write(json.dumps({"error": str(exc)}, sort_keys=True) + "\n")
        else:
            sys.stderr.write(message + "\n")
        return 2

    if args.json_output:
        sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
    else:
        sys.stdout.write(_human_brief(result, args.top) + "\n")
    return 0


def _human_brief(result, top):
    totals = result["totals"]
    delta_pct = totals["delta_pct"]
    if delta_pct is None:
        delta_pct_text = "n/a"
    else:
        delta_pct_text = "%.1f%%" % delta_pct

    lines = [
        "Brief Revenue CEO",
        "Tanggal H-1: %s vs %s" % (result["reference_date"], result["baseline_date"]),
        "Total: %s vs %s (%s, %s)"
        % (
            _rupiah(totals["reference_revenue"]),
            _rupiah(totals["baseline_revenue"]),
            _rupiah(totals["delta_amount"]),
            delta_pct_text,
        ),
        "Coverage: %s outlet dibandingkan, %s kandidat drop"
        % (result["coverage"]["compared_outlets"], result["coverage"]["candidate_outlets"]),
    ]

    candidates = result["candidates"]
    if top is not None:
        candidates = candidates[:top]
    if candidates:
        lines.append("Prioritas:")
        for item in candidates:
            lines.append(
                "- %s: loss %s, drop %.1f%% (%s -> %s)"
                % (
                    item["outlet_name"],
                    _rupiah(item["nominal_loss"]),
                    item["delta_pct"],
                    _rupiah(item["baseline_revenue"]),
                    _rupiah(item["reference_revenue"]),
                )
            )
    else:
        lines.append("Prioritas: tidak ada outlet yang melewati threshold.")

    if result["warnings"]:
        lines.append("Warning: " + result["warnings"][0])
    return "\n".join(lines)


def _rupiah(value):
    sign = "-" if value < 0 else ""
    amount = int(round(abs(value)))
    return "%sRp%s" % (sign, format(amount, ",").replace(",", "."))


def _jakarta_today():
    return (datetime.utcnow() + timedelta(hours=7)).date().isoformat()


if __name__ == "__main__":
    sys.exit(main())
