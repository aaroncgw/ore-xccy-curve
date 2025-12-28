"""
Main entry point for cross-currency curve bootstrapping.

Demonstrates how to use ORE (Open Source Risk Engine) to bootstrap
mark-to-market cross-currency basis curves for various currency pairs.

Note: In production, the domestic and foreign OIS curves would be loaded
from external sources. This demo uses OISCurveBuilder with dummy rates.
"""

from datetime import timedelta
from typing import List, Tuple

import ORE as ore

from ore_xccy_curve.curve_builder import OISCurveBuilder, build_xccy_curve
from ore_xccy_curve.market_data import MarketDataFactory


def get_dummy_usd_ois_rates() -> List[Tuple[str, float]]:
    """Get dummy USD SOFR OIS rates for demo purposes."""
    return [
        ("1M", 0.0525), ("3M", 0.0530), ("6M", 0.0528), ("1Y", 0.0510),
        ("2Y", 0.0465), ("3Y", 0.0430), ("5Y", 0.0395), ("7Y", 0.0385),
        ("10Y", 0.0380), ("15Y", 0.0385), ("20Y", 0.0390), ("30Y", 0.0395),
    ]


def get_dummy_gbp_ois_rates() -> List[Tuple[str, float]]:
    """Get dummy GBP SONIA OIS rates for demo purposes."""
    return [
        ("1M", 0.0515), ("3M", 0.0520), ("6M", 0.0510), ("1Y", 0.0485),
        ("2Y", 0.0440), ("3Y", 0.0405), ("5Y", 0.0375), ("7Y", 0.0365),
        ("10Y", 0.0360), ("15Y", 0.0365), ("20Y", 0.0370), ("30Y", 0.0375),
    ]


def get_dummy_eur_ois_rates() -> List[Tuple[str, float]]:
    """Get dummy EUR ESTR OIS rates for demo purposes."""
    return [
        ("1M", 0.0390), ("3M", 0.0395), ("6M", 0.0388), ("1Y", 0.0365),
        ("2Y", 0.0320), ("3Y", 0.0290), ("5Y", 0.0265), ("7Y", 0.0260),
        ("10Y", 0.0258), ("15Y", 0.0265), ("20Y", 0.0270), ("30Y", 0.0275),
    ]


def main():
    """Run the XCCY curve bootstrapping example."""
    print("=" * 70)
    print("Cross-Currency Curve Bootstrapping with ORE")
    print("=" * 70)

    # Bootstrap GBPUSD
    print("\n" + "=" * 70)
    print("GBPUSD Curve Bootstrapping")
    print("=" * 70)

    market_data = MarketDataFactory.create_gbpusd()
    market_data.print_summary()

    # Set up evaluation date
    val_date = market_data.valuation_date
    eval_date = ore.Date(val_date.day, val_date.month, val_date.year)
    ore.Settings.instance().evaluationDate = eval_date

    # Build input curves (in production, these would come from external sources)
    print("\nBuilding input curves...")
    usd_curve = OISCurveBuilder(
        eval_date, market_data.domestic_ccy, get_dummy_usd_ois_rates()
    ).build()
    gbp_curve = OISCurveBuilder(
        eval_date, market_data.foreign_ccy, get_dummy_gbp_ois_rates()
    ).build()

    print("  - USD Discount (SOFR OIS)")
    print("  - GBP Index (SONIA OIS)")

    # Build XCCY basis curve
    print("\nBootstrapping XCCY basis curve...")
    result = build_xccy_curve(
        market_data,
        domestic_discount_curve=usd_curve,
        domestic_index_curve=usd_curve,
        foreign_index_curve=gbp_curve,
    )

    print("  - GBP XCCY Basis Curve")

    # Print curve summary
    xccy_builder = result["xccy_builder"]
    xccy_builder.print_curve_summary()

    # Example forward calculations
    print("\nExample Forward Rate Calculations (GBPUSD):")
    print("-" * 50)
    for days in [90, 365, 365 * 5]:
        fwd_date = val_date + timedelta(days=days)
        fx_fwd = xccy_builder.get_implied_fx_forward(fwd_date)
        print(f"  {fwd_date}: {fx_fwd:.4f}")

    # Bootstrap EURUSD
    print("\n" + "=" * 70)
    print("EURUSD Curve Bootstrapping")
    print("=" * 70)

    market_data = MarketDataFactory.create_eurusd()
    market_data.print_summary()

    # Build EUR input curve
    eur_curve = OISCurveBuilder(
        eval_date, market_data.foreign_ccy, get_dummy_eur_ois_rates()
    ).build()

    print("\nBootstrapping XCCY basis curve...")
    result = build_xccy_curve(
        market_data,
        domestic_discount_curve=usd_curve,
        domestic_index_curve=usd_curve,
        foreign_index_curve=eur_curve,
    )

    xccy_builder = result["xccy_builder"]
    xccy_builder.print_curve_summary()

    print("\nDone!")


if __name__ == "__main__":
    main()
