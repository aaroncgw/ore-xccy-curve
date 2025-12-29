"""
Utilities for loading yield term structures from files.

Loads curves into QuantLib objects (DiscountCurve or ZeroCurve).
Since ORE extends QuantLib, these curves are compatible with both libraries.
"""

import csv
import json
from pathlib import Path
from typing import TYPE_CHECKING, Union

import ORE as ore

if TYPE_CHECKING:
    import QuantLib as ql


def _iso_to_ore_date(iso_str: str) -> ore.Date:
    """Convert ISO string (YYYY-MM-DD) to ORE/QuantLib Date."""
    parts = iso_str.split("-")
    return ore.Date(int(parts[2]), int(parts[1]), int(parts[0]))


def load_curve_from_csv(
    file_path: Union[str, Path],
    use_discount_factors: bool = True,
) -> "ql.YieldTermStructure":
    """
    Load a yield curve from a CSV file.

    Returns a QuantLib-compatible YieldTermStructure (DiscountCurve or ZeroCurve).
    Since ORE extends QuantLib, the returned curve works with both libraries.

    Args:
        file_path: Path to the CSV file
        use_discount_factors: If True, build curve from discount factors.
                              If False, build from zero rates.

    Returns:
        QuantLib YieldTermStructure (DiscountCurve or ZeroCurve)

    Example:
        >>> curve = load_curve_from_csv("gbp_xccy_curve.csv")
        >>> df = curve.discount(target_date)
    """
    dates = []
    dfs = []
    zrs = []
    ref_date = None

    with open(file_path, "r") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row or row[0].startswith("#"):
                # Parse metadata from comments
                if row and row[0] == "# reference_date":
                    ref_date = _iso_to_ore_date(row[1].strip())
                continue
            if row[0] == "date":
                continue  # Skip header

            dt = _iso_to_ore_date(row[0])
            df = float(row[1])
            zr = float(row[2])

            dates.append(dt)
            dfs.append(df)
            zrs.append(zr)

    if ref_date is None and dates:
        # Use first date as reference if not specified
        ref_date = dates[0]

    ore.Settings.instance().evaluationDate = ref_date

    if use_discount_factors:
        # DiscountCurve requires first point at reference date with DF=1.0
        all_dates = [ref_date] + dates
        all_values = [1.0] + dfs
        curve = ore.DiscountCurve(all_dates, all_values, ore.Actual365Fixed())
    else:
        # ZeroCurve requires first point at reference date
        all_dates = [ref_date] + dates
        all_values = [zrs[0] if zrs else 0.0] + zrs
        curve = ore.ZeroCurve(all_dates, all_values, ore.Actual365Fixed())

    curve.enableExtrapolation()
    return curve


def load_curve_from_json(
    file_path: Union[str, Path],
    use_discount_factors: bool = True,
) -> "ql.YieldTermStructure":
    """
    Load a yield curve from a JSON file.

    Returns a QuantLib-compatible YieldTermStructure (DiscountCurve or ZeroCurve).
    Since ORE extends QuantLib, the returned curve works with both libraries.

    Args:
        file_path: Path to the JSON file
        use_discount_factors: If True, build curve from discount factors.
                              If False, build from zero rates.

    Returns:
        QuantLib YieldTermStructure (DiscountCurve or ZeroCurve)

    Example:
        >>> curve = load_curve_from_json("gbp_xccy_curve.json")
        >>> df = curve.discount(target_date)
    """
    with open(file_path, "r") as f:
        data = json.load(f)

    ref_date = _iso_to_ore_date(data["reference_date"])
    ore.Settings.instance().evaluationDate = ref_date

    dates = []
    dfs = []
    zrs = []

    for point in data["points"]:
        dates.append(_iso_to_ore_date(point["date"]))
        dfs.append(point["discount_factor"])
        zrs.append(point["zero_rate"])

    if use_discount_factors:
        # DiscountCurve requires first point at reference date with DF=1.0
        all_dates = [ref_date] + dates
        all_values = [1.0] + dfs
        curve = ore.DiscountCurve(all_dates, all_values, ore.Actual365Fixed())
    else:
        # ZeroCurve requires first point at reference date
        all_dates = [ref_date] + dates
        all_values = [zrs[0] if zrs else 0.0] + zrs
        curve = ore.ZeroCurve(all_dates, all_values, ore.Actual365Fixed())

    curve.enableExtrapolation()
    return curve
