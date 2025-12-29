"""
Market data module for cross-currency curve bootstrapping.

Contains FX spot, FX forwards, and cross-currency basis swap quotes.
Supports any currency pair configuration.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional


@dataclass
class FXForwardQuote:
    """FX Forward quote data."""

    tenor: str  # e.g., "1M", "3M", "6M", "1Y"
    forward_points: float  # Forward points in pips


@dataclass
class XCCYBasisSwapQuote:
    """Cross-currency basis swap quote data."""

    tenor: str  # e.g., "2Y", "5Y", "10Y"
    basis_spread: float  # Basis spread in bps


@dataclass
class CurrencyConfig:
    """Configuration for a currency in XCCY curve building."""

    ccy: str  # ISO currency code (e.g., "USD", "GBP", "EUR")
    ois_index_name: str  # OIS index name (e.g., "SOFR", "SONIA", "ESTR")
    calendar_name: str  # Calendar identifier
    day_count: str = "Actual360"  # Day count convention


@dataclass
class XCCYMarketData:
    """
    Market data for cross-currency curve bootstrapping.

    This contains only the XCCY-specific market data needed to bootstrap
    the foreign XCCY curve:
    - Currency pair configuration (domestic/foreign)
    - FX spot rate
    - FX forward points for short end
    - Cross-currency basis swap spreads for long end

    The domestic and foreign OIS curves are expected to be built separately
    and passed to XCCYCurveBuilder as pre-built curves.

    FX Convention:
    - fx_spot is in market convention (e.g., GBPUSD=1.27, USDJPY=148.50)
    - fx_base_ccy indicates which currency is the FX base (first in pair name)
    - For GBPUSD: fx_base_ccy="GBP" (not collateral)
    - For USDJPY: fx_base_ccy="USD" (equals collateral)
    """

    valuation_date: date
    domestic_ccy: CurrencyConfig  # Collateral/domestic currency (always USD for the user)
    foreign_ccy: CurrencyConfig  # Foreign currency (e.g., GBP, EUR, JPY)
    fx_spot: float  # FX spot rate in market convention
    fx_forwards: List[FXForwardQuote] = field(default_factory=list)
    xccy_basis_swaps: List[XCCYBasisSwapQuote] = field(default_factory=list)
    fx_base_ccy: Optional[str] = None  # FX base currency (first in pair), auto-detected if None

    def __post_init__(self):
        """Auto-detect fx_base_ccy if not provided."""
        if self.fx_base_ccy is None:
            # Default: assume foreign currency is FX base (works for GBPUSD, EURUSD, AUDUSD)
            # Override in factory methods for pairs like USDJPY where USD is FX base
            self.fx_base_ccy = self.foreign_ccy.ccy

    @property
    def ccy_pair(self) -> str:
        """Return the currency pair string in market convention (e.g., 'GBPUSD', 'USDJPY')."""
        fx_quote_ccy = (
            self.domestic_ccy.ccy if self.fx_base_ccy == self.foreign_ccy.ccy
            else self.foreign_ccy.ccy
        )
        return f"{self.fx_base_ccy}{fx_quote_ccy}"

    @property
    def is_fx_base_domestic(self) -> bool:
        """Return True if FX base currency equals domestic (collateral) currency.

        This affects how the FX spot is interpreted in the curve helpers:
        - GBPUSD: fx_base=GBP, domestic=USD → False
        - USDJPY: fx_base=USD, domestic=USD → True
        """
        return self.fx_base_ccy == self.domestic_ccy.ccy

    def get_forward_rate(self, tenor: str) -> float:
        """Get the outright forward rate for a given tenor."""
        for fwd in self.fx_forwards:
            if fwd.tenor == tenor:
                return self.fx_spot + (fwd.forward_points / 10000.0)
        raise ValueError(f"Unknown tenor: {tenor}")

    def get_basis_spread_bps(self, tenor: str) -> float:
        """Get the cross-currency basis spread in basis points."""
        for swap in self.xccy_basis_swaps:
            if swap.tenor == tenor:
                return swap.basis_spread
        raise ValueError(f"Unknown tenor: {tenor}")

    def print_summary(self) -> None:
        """Print a summary of the market data."""
        print(f"\n{'='*60}")
        print(f"{self.ccy_pair} Market Data Summary - {self.valuation_date}")
        print(f"{'='*60}")
        print(f"\nFX Spot: {self.fx_spot:.4f}")

        print(f"\n{'FX Forwards':-^40}")
        print(f"{'Tenor':<10} {'Points':<12} {'Outright':<12}")
        for fwd in self.fx_forwards:
            outright = self.fx_spot + (fwd.forward_points / 10000.0)
            print(f"{fwd.tenor:<10} {fwd.forward_points:<12.1f} {outright:<12.4f}")

        print(f"\n{'XCCY Basis Swaps':-^40}")
        print(f"{'Tenor':<10} {'Spread (bps)':<15}")
        for swap in self.xccy_basis_swaps:
            print(f"{swap.tenor:<10} {swap.basis_spread:<15.1f}")
        print()


class MarketDataFactory:
    """Factory for creating market data with dummy values for various currency pairs."""

    # Predefined currency configurations
    CURRENCY_CONFIGS: Dict[str, CurrencyConfig] = {
        "USD": CurrencyConfig("USD", "SOFR", "US-FederalReserve", "Actual360"),
        "GBP": CurrencyConfig("GBP", "SONIA", "UK-Exchange", "Actual365Fixed"),
        "EUR": CurrencyConfig("EUR", "ESTR", "TARGET", "Actual360"),
        "JPY": CurrencyConfig("JPY", "TONAR", "Japan", "Actual365Fixed"),
        "CHF": CurrencyConfig("CHF", "SARON", "Switzerland", "Actual360"),
        "AUD": CurrencyConfig("AUD", "AONIA", "Australia", "Actual365Fixed"),
        "CAD": CurrencyConfig("CAD", "CORRA", "Canada", "Actual365Fixed"),
    }

    @classmethod
    def create_gbpusd(cls, valuation_date: Optional[date] = None) -> XCCYMarketData:
        """Create dummy GBPUSD market data."""
        if valuation_date is None:
            valuation_date = date(2024, 1, 15)

        return XCCYMarketData(
            valuation_date=valuation_date,
            domestic_ccy=cls.CURRENCY_CONFIGS["USD"],
            foreign_ccy=cls.CURRENCY_CONFIGS["GBP"],
            fx_spot=1.2750,
            fx_forwards=[
                FXForwardQuote("1W", -2.5),
                FXForwardQuote("2W", -5.0),
                FXForwardQuote("1M", -12.0),
                FXForwardQuote("2M", -24.0),
                FXForwardQuote("3M", -38.0),
                FXForwardQuote("6M", -78.0),
                FXForwardQuote("9M", -115.0),
                FXForwardQuote("1Y", -155.0),
            ],
            xccy_basis_swaps=[
                XCCYBasisSwapQuote("2Y", -12.5),
                XCCYBasisSwapQuote("3Y", -15.0),
                XCCYBasisSwapQuote("4Y", -16.5),
                XCCYBasisSwapQuote("5Y", -17.5),
                XCCYBasisSwapQuote("7Y", -18.0),
                XCCYBasisSwapQuote("10Y", -17.0),
                XCCYBasisSwapQuote("15Y", -15.0),
                XCCYBasisSwapQuote("20Y", -13.0),
                XCCYBasisSwapQuote("30Y", -10.0),
            ],
        )

    @classmethod
    def create_eurusd(cls, valuation_date: Optional[date] = None) -> XCCYMarketData:
        """Create dummy EURUSD market data."""
        if valuation_date is None:
            valuation_date = date(2024, 1, 15)

        return XCCYMarketData(
            valuation_date=valuation_date,
            domestic_ccy=cls.CURRENCY_CONFIGS["USD"],
            foreign_ccy=cls.CURRENCY_CONFIGS["EUR"],
            fx_spot=1.0850,
            fx_forwards=[
                FXForwardQuote("1W", 1.5),
                FXForwardQuote("2W", 3.0),
                FXForwardQuote("1M", 7.0),
                FXForwardQuote("2M", 14.0),
                FXForwardQuote("3M", 22.0),
                FXForwardQuote("6M", 45.0),
                FXForwardQuote("9M", 68.0),
                FXForwardQuote("1Y", 92.0),
            ],
            xccy_basis_swaps=[
                XCCYBasisSwapQuote("2Y", -8.0),
                XCCYBasisSwapQuote("3Y", -10.0),
                XCCYBasisSwapQuote("4Y", -11.5),
                XCCYBasisSwapQuote("5Y", -12.5),
                XCCYBasisSwapQuote("7Y", -13.0),
                XCCYBasisSwapQuote("10Y", -12.0),
                XCCYBasisSwapQuote("15Y", -10.0),
                XCCYBasisSwapQuote("20Y", -8.5),
                XCCYBasisSwapQuote("30Y", -7.0),
            ],
        )

    @classmethod
    def create_usdjpy(cls, valuation_date: Optional[date] = None) -> XCCYMarketData:
        """
        Create dummy USDJPY market data.

        Note: For USDJPY, USD is still the domestic (collateral) currency since
        trading accounts are denominated in USD. JPY is the foreign currency.
        The fx_spot is expressed in market convention (JPY per USD = 148.50).

        The FX base currency (USD) equals the collateral currency, which differs
        from GBPUSD where the FX base (GBP) is not the collateral (USD).
        This affects the isFxBaseCurrencyCollateralCurrency flag in the helpers.

        This builds the JPY XCCY curve collateralized in USD.
        """
        if valuation_date is None:
            valuation_date = date(2024, 1, 15)

        return XCCYMarketData(
            valuation_date=valuation_date,
            domestic_ccy=cls.CURRENCY_CONFIGS["USD"],
            foreign_ccy=cls.CURRENCY_CONFIGS["JPY"],
            fx_spot=148.50,  # USDJPY: JPY per USD (market convention)
            fx_base_ccy="USD",  # USD is FX base (unlike GBPUSD where GBP is FX base)
            fx_forwards=[
                FXForwardQuote("1W", -8.0),
                FXForwardQuote("2W", -16.0),
                FXForwardQuote("1M", -35.0),
                FXForwardQuote("2M", -72.0),
                FXForwardQuote("3M", -110.0),
                FXForwardQuote("6M", -225.0),
                FXForwardQuote("9M", -340.0),
                FXForwardQuote("1Y", -460.0),
            ],
            xccy_basis_swaps=[
                XCCYBasisSwapQuote("2Y", -25.0),
                XCCYBasisSwapQuote("3Y", -28.0),
                XCCYBasisSwapQuote("4Y", -30.0),
                XCCYBasisSwapQuote("5Y", -32.0),
                XCCYBasisSwapQuote("7Y", -33.0),
                XCCYBasisSwapQuote("10Y", -30.0),
                XCCYBasisSwapQuote("15Y", -25.0),
                XCCYBasisSwapQuote("20Y", -22.0),
                XCCYBasisSwapQuote("30Y", -18.0),
            ],
        )


# Backward compatibility alias
GBPUSDMarketData = XCCYMarketData


def create_dummy_gbpusd_data(valuation_date: Optional[date] = None) -> XCCYMarketData:
    """Backward compatible function to create GBPUSD data."""
    return MarketDataFactory.create_gbpusd(valuation_date)
