"""
Utilities for saving ORE yield term structures to files.

Supports CSV and JSON formats for curve persistence.
"""

import csv
import json
from pathlib import Path
from typing import List, Tuple, Union

import ORE as ore

from ore_xccy_curve.curve_converters import ore_handle_to_curve


def _ore_date_to_iso(ore_date: ore.Date) -> str:
    """Convert ORE Date to ISO string (YYYY-MM-DD)."""
    return f"{ore_date.year()}-{ore_date.month():02d}-{ore_date.dayOfMonth():02d}"


def extract_curve_points(
    handle: ore.YieldTermStructureHandle,
    tenors: List[str] = None,
    max_years: int = 50,
) -> List[Tuple[str, float, float]]:
    """
    Extract curve points (date, discount factor, zero rate) from a curve.

    Args:
        handle: An ORE YieldTermStructureHandle
        tenors: Optional list of tenors to extract (e.g., ["1M", "3M", "1Y", "5Y"])
                If None, uses a default grid up to max_years
        max_years: Maximum years for default tenor grid (default 50)

    Returns:
        List of tuples: (iso_date, discount_factor, zero_rate)
    """
    curve = ore_handle_to_curve(handle)
    ref_date = curve.referenceDate()
    day_count = ore.Actual365Fixed()

    if tenors is None:
        # Default tenor grid
        tenors = (
            ["1W", "2W", "1M", "2M", "3M", "6M", "9M"]
            + [f"{y}Y" for y in range(1, min(max_years + 1, 51))]
        )

    points = []
    for tenor in tenors:
        try:
            period = ore.Period(tenor)
            target_date = ref_date + period
            df = handle.discount(target_date)
            zero = handle.zeroRate(target_date, day_count, ore.Continuous).rate()
            points.append((_ore_date_to_iso(target_date), df, zero))
        except RuntimeError:
            # Skip tenors that fail (e.g., beyond curve range)
            continue

    return points


def save_curve_to_csv(
    handle: ore.YieldTermStructureHandle,
    file_path: Union[str, Path],
    tenors: List[str] = None,
    curve_name: str = "curve",
) -> None:
    """
    Save an ORE curve to a CSV file.

    The CSV contains columns: date, discount_factor, zero_rate
    The reference date is stored in the header comment.

    Args:
        handle: An ORE YieldTermStructureHandle
        file_path: Path to save the CSV file
        tenors: Optional list of tenors to extract
        curve_name: Name to include in the file header

    Example:
        >>> save_curve_to_csv(xccy_handle, "gbp_xccy_curve.csv", curve_name="GBP_XCCY")
    """
    curve = ore_handle_to_curve(handle)
    ref_date = curve.referenceDate()
    points = extract_curve_points(handle, tenors)

    with open(file_path, "w", newline="") as f:
        writer = csv.writer(f)
        # Header with metadata
        writer.writerow(["# curve_name", curve_name])
        writer.writerow(["# reference_date", _ore_date_to_iso(ref_date)])
        writer.writerow(["# day_count", "Actual365Fixed"])
        writer.writerow(["# compounding", "Continuous"])
        writer.writerow([])  # Empty row separator
        writer.writerow(["date", "discount_factor", "zero_rate"])
        for dt, df, zr in points:
            writer.writerow([dt, f"{df:.15f}", f"{zr:.10f}"])


def save_curve_to_json(
    handle: ore.YieldTermStructureHandle,
    file_path: Union[str, Path],
    tenors: List[str] = None,
    curve_name: str = "curve",
) -> None:
    """
    Save an ORE curve to a JSON file.

    Args:
        handle: An ORE YieldTermStructureHandle
        file_path: Path to save the JSON file
        tenors: Optional list of tenors to extract
        curve_name: Name to include in the metadata

    Example:
        >>> save_curve_to_json(xccy_handle, "gbp_xccy_curve.json", curve_name="GBP_XCCY")
    """
    curve = ore_handle_to_curve(handle)
    ref_date = curve.referenceDate()
    points = extract_curve_points(handle, tenors)

    data = {
        "curve_name": curve_name,
        "reference_date": _ore_date_to_iso(ref_date),
        "day_count": "Actual365Fixed",
        "compounding": "Continuous",
        "points": [
            {"date": dt, "discount_factor": df, "zero_rate": zr}
            for dt, df, zr in points
        ],
    }

    with open(file_path, "w") as f:
        json.dump(data, f, indent=2)
