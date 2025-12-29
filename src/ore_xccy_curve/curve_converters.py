"""
Converters for bridging QuantLib and ORE yield term structures.

ORE is built on QuantLib, so QuantLib YieldTermStructure objects can be
wrapped in ORE handles for use with XCCYCurveBuilder, and vice versa.
"""

from typing import TYPE_CHECKING, Union

import ORE as ore

if TYPE_CHECKING:
    import QuantLib as ql


def quantlib_curve_to_ore_handle(
    ql_curve: Union[ore.YieldTermStructure, "ql.YieldTermStructure"],
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
    ql_curve: Union[ore.YieldTermStructure, "ql.YieldTermStructure", None] = None,
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
