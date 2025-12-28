"""
Converters for bridging QuantLib and ORE yield term structures.

ORE is built on QuantLib, so QuantLib YieldTermStructure objects can be
wrapped in ORE handles for use with XCCYCurveBuilder.
"""

from typing import Union

import ORE as ore


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
