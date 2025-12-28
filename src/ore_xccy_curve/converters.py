"""
Converters for bridging QuantLib and ORE yield term structures.

ORE is built on QuantLib, so QuantLib YieldTermStructure objects can be
wrapped in ORE handles for use with XCCYCurveBuilder, and vice versa.

Also provides utilities for persisting curves to files and reloading them.
"""

import csv
import json
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, List, Tuple, Union

import ORE as ore

if TYPE_CHECKING:
    import QuantLib as ql


def quantlib_curve_to_ore_handle(
    ql_curve: Union[ore.YieldTermStructure, "QuantLib.YieldTermStructure"],
) -> ore.YieldTermStructureHandle:
    """
    Convert a QuantLib YieldTermStructure to an ORE YieldTermStructureHandle.

    Since ORE is built on QuantLib, the YieldTermStructure types are compatible.
    This function wraps the curve in an ORE handle for use with XCCYCurveBuilder.

    Args:
        ql_curve: A QuantLib or ORE YieldTermStructure object

    Returns:
        ORE YieldTermStructureHandle wrapping the input curve

    Example:
        >>> import QuantLib as ql
        >>> # Build your QuantLib curve
        >>> ql_curve = ql.FlatForward(today, 0.05, ql.Actual360())
        >>> # Convert to ORE handle
        >>> ore_handle = quantlib_curve_to_ore_handle(ql_curve)
        >>> # Use with XCCYCurveBuilder
        >>> builder = XCCYCurveBuilder(market_data, ore_handle, ore_handle, ore_handle)
    """
    # ORE's YieldTermStructureHandle can wrap QuantLib curves directly
    # since ORE extends QuantLib
    return ore.YieldTermStructureHandle(ql_curve)


def quantlib_curve_to_relinkable_handle(
    ql_curve: Union[ore.YieldTermStructure, "QuantLib.YieldTermStructure", None] = None,
) -> ore.RelinkableYieldTermStructureHandle:
    """
    Create a RelinkableYieldTermStructureHandle, optionally linked to a curve.

    Relinkable handles are useful when you need to update the curve later
    without recreating dependent objects.

    Args:
        ql_curve: Optional QuantLib or ORE YieldTermStructure to link initially

    Returns:
        ORE RelinkableYieldTermStructureHandle

    Example:
        >>> # Create empty relinkable handle
        >>> handle = quantlib_curve_to_relinkable_handle()
        >>> # Later, link it to a curve
        >>> handle.linkTo(my_curve)
    """
    handle = ore.RelinkableYieldTermStructureHandle()
    if ql_curve is not None:
        handle.linkTo(ql_curve)
    return handle


def create_flat_forward_curve(
    valuation_date: ore.Date,
    rate: float,
    day_count: ore.DayCounter = None,
) -> ore.YieldTermStructureHandle:
    """
    Create a simple flat forward curve for testing or placeholder purposes.

    Args:
        valuation_date: The curve's reference date
        rate: The flat forward rate (e.g., 0.05 for 5%)
        day_count: Day count convention (defaults to Actual360)

    Returns:
        ORE YieldTermStructureHandle with a flat forward curve

    Example:
        >>> eval_date = ore.Date(15, 1, 2024)
        >>> curve = create_flat_forward_curve(eval_date, 0.05)
    """
    if day_count is None:
        day_count = ore.Actual360()

    flat_curve = ore.FlatForward(valuation_date, rate, day_count)
    flat_curve.enableExtrapolation()
    return ore.YieldTermStructureHandle(flat_curve)


def ore_handle_to_curve(
    handle: ore.YieldTermStructureHandle,
) -> ore.YieldTermStructure:
    """
    Extract the underlying YieldTermStructure from an ORE handle.

    Since ORE is built on QuantLib, the returned curve is compatible with
    both ORE and QuantLib APIs. You can use it directly with QuantLib code.

    Args:
        handle: An ORE YieldTermStructureHandle

    Returns:
        The underlying YieldTermStructure (compatible with QuantLib)

    Raises:
        ValueError: If the handle is empty (not linked to a curve)

    Example:
        >>> # Get curve from XCCYCurveBuilder
        >>> xccy_handle = xccy_builder.foreign_xccy_curve
        >>> # Extract for use with QuantLib
        >>> curve = ore_handle_to_curve(xccy_handle)
        >>> # Use with QuantLib APIs
        >>> df = curve.discount(target_date)
    """
    try:
        # Try to access the curve - will raise if empty
        curve = handle.currentLink()
        if curve is None:
            raise ValueError("Handle is empty - not linked to any curve")
        return curve
    except RuntimeError as e:
        # QuantLib/ORE raises RuntimeError for empty handles
        raise ValueError(f"Handle is empty - not linked to any curve: {e}") from e


def ore_curve_to_quantlib(
    ore_curve: ore.YieldTermStructure,
) -> "ql.YieldTermStructure":
    """
    Convert an ORE YieldTermStructure to a QuantLib-compatible curve.

    Since ORE extends QuantLib, ORE curves are already QuantLib-compatible.
    This function simply returns the curve with proper type annotation for
    use in QuantLib-typed code.

    Note: This is essentially a no-op at runtime since ORE curves inherit
    from QuantLib. It's provided for type clarity and documentation.

    Args:
        ore_curve: An ORE YieldTermStructure

    Returns:
        The same curve, usable with QuantLib APIs

    Example:
        >>> # Build XCCY curve with ORE
        >>> result = build_xccy_curve(market_data, dom_disc, dom_idx, for_idx)
        >>> xccy_curve = ore_handle_to_curve(result["foreign_xccy"])
        >>> # Use with QuantLib-based pricing
        >>> ql_curve = ore_curve_to_quantlib(xccy_curve)
    """
    # ORE curves are QuantLib-compatible, so just return as-is
    return ore_curve


def get_discount_factors(
    handle: ore.YieldTermStructureHandle,
    dates: list,
) -> list:
    """
    Extract discount factors from a curve for a list of dates.

    Convenience function to get DFs for multiple dates at once.

    Args:
        handle: An ORE YieldTermStructureHandle
        dates: List of ore.Date objects

    Returns:
        List of discount factors corresponding to each date

    Example:
        >>> dates = [eval_date + ore.Period(t, ore.Years) for t in [1, 2, 5, 10]]
        >>> dfs = get_discount_factors(xccy_handle, dates)
    """
    return [handle.discount(d) for d in dates]


def get_zero_rates(
    handle: ore.YieldTermStructureHandle,
    dates: list,
    day_count: ore.DayCounter = None,
    compounding: int = None,
) -> list:
    """
    Extract zero rates from a curve for a list of dates.

    Convenience function to get zero rates for multiple dates at once.

    Args:
        handle: An ORE YieldTermStructureHandle
        dates: List of ore.Date objects
        day_count: Day count convention (defaults to Actual365Fixed)
        compounding: Compounding convention (defaults to Continuous)

    Returns:
        List of zero rates corresponding to each date

    Example:
        >>> dates = [eval_date + ore.Period(t, ore.Years) for t in [1, 2, 5, 10]]
        >>> rates = get_zero_rates(xccy_handle, dates)
    """
    if day_count is None:
        day_count = ore.Actual365Fixed()
    if compounding is None:
        compounding = ore.Continuous

    return [handle.zeroRate(d, day_count, compounding).rate() for d in dates]


# =============================================================================
# Curve Persistence Functions
# =============================================================================


def _ore_date_to_iso(ore_date: ore.Date) -> str:
    """Convert ORE Date to ISO string (YYYY-MM-DD)."""
    return f"{ore_date.year()}-{ore_date.month():02d}-{ore_date.dayOfMonth():02d}"


def _iso_to_ore_date(iso_str: str) -> ore.Date:
    """Convert ISO string (YYYY-MM-DD) to ORE Date."""
    parts = iso_str.split("-")
    return ore.Date(int(parts[2]), int(parts[1]), int(parts[0]))


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
    Save a curve to a CSV file.

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
    Save a curve to a JSON file.

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


def load_curve_from_csv(
    file_path: Union[str, Path],
    use_discount_factors: bool = True,
) -> ore.YieldTermStructureHandle:
    """
    Load a curve from a CSV file.

    Args:
        file_path: Path to the CSV file
        use_discount_factors: If True, build curve from discount factors.
                              If False, build from zero rates.

    Returns:
        ORE YieldTermStructureHandle with the reconstructed curve

    Example:
        >>> handle = load_curve_from_csv("gbp_xccy_curve.csv")
        >>> df = handle.discount(target_date)
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
        # ZeroCurve requires first point at reference date with rate=0
        all_dates = [ref_date] + dates
        all_values = [zrs[0] if zrs else 0.0] + zrs
        curve = ore.ZeroCurve(all_dates, all_values, ore.Actual365Fixed())

    curve.enableExtrapolation()
    return ore.YieldTermStructureHandle(curve)


def load_curve_from_json(
    file_path: Union[str, Path],
    use_discount_factors: bool = True,
) -> ore.YieldTermStructureHandle:
    """
    Load a curve from a JSON file.

    Args:
        file_path: Path to the JSON file
        use_discount_factors: If True, build curve from discount factors.
                              If False, build from zero rates.

    Returns:
        ORE YieldTermStructureHandle with the reconstructed curve

    Example:
        >>> handle = load_curve_from_json("gbp_xccy_curve.json")
        >>> df = handle.discount(target_date)
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
    return ore.YieldTermStructureHandle(curve)
