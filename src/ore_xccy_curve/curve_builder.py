"""
Cross-currency curve bootstrapping using ORE (Open Source Risk Engine).

Bootstraps a mark-to-market cross-currency basis curve using:
- FX spot and forward points for the short end
- Cross-currency basis swap spreads for the long end

Supports any currency pair configuration.
"""

from datetime import date
from typing import Callable, Dict, List, Optional, Tuple

import ORE as ore

from ore_xccy_curve.market_data import CurrencyConfig, XCCYMarketData


class OISIndexFactory:
    """Factory for creating OIS indices based on currency configuration."""

    _INDEX_REGISTRY: Dict[str, Callable] = {
        "SOFR": lambda handle: ore.Sofr(handle) if handle else ore.Sofr(),
        "SONIA": lambda handle: ore.Sonia(handle) if handle else ore.Sonia(),
        "ESTR": lambda handle: ore.Estr(handle) if handle else ore.Estr(),
        "TONAR": lambda handle: ore.Tonar(handle) if handle else ore.Tonar(),
        "SARON": lambda handle: ore.Saron(handle) if handle else ore.Saron(),
        "AONIA": lambda handle: ore.Aonia(handle) if handle else ore.Aonia(),
        "CORRA": lambda handle: ore.Corra(handle) if handle else ore.Corra(),
    }

    @classmethod
    def create(
        cls,
        index_name: str,
        curve_handle: Optional[ore.YieldTermStructureHandle] = None,
    ) -> ore.OvernightIndex:
        """Create an OIS index by name."""
        if index_name not in cls._INDEX_REGISTRY:
            raise ValueError(
                f"Unknown OIS index: {index_name}. "
                f"Available: {list(cls._INDEX_REGISTRY.keys())}"
            )
        return cls._INDEX_REGISTRY[index_name](curve_handle)

    @classmethod
    def register(cls, name: str, constructor: Callable) -> None:
        """Register a new OIS index constructor."""
        cls._INDEX_REGISTRY[name] = constructor


class CalendarFactory:
    """Factory for creating ORE calendars based on currency configuration."""

    _CALENDAR_REGISTRY: Dict[str, Callable[[], ore.Calendar]] = {
        "US-FederalReserve": lambda: ore.UnitedStates(ore.UnitedStates.FederalReserve),
        "US-NYSE": lambda: ore.UnitedStates(ore.UnitedStates.NYSE),
        "UK-Exchange": lambda: ore.UnitedKingdom(ore.UnitedKingdom.Exchange),
        "TARGET": lambda: ore.TARGET(),
        "Japan": lambda: ore.Japan(),
        "Switzerland": lambda: ore.Switzerland(),
        "Australia": lambda: ore.Australia(),
        "Canada": lambda: ore.Canada(),
    }

    @classmethod
    def create(cls, calendar_name: str) -> ore.Calendar:
        """Create a calendar by name."""
        if calendar_name not in cls._CALENDAR_REGISTRY:
            raise ValueError(
                f"Unknown calendar: {calendar_name}. "
                f"Available: {list(cls._CALENDAR_REGISTRY.keys())}"
            )
        return cls._CALENDAR_REGISTRY[calendar_name]()

    @classmethod
    def register(cls, name: str, constructor: Callable[[], ore.Calendar]) -> None:
        """Register a new calendar constructor."""
        cls._CALENDAR_REGISTRY[name] = constructor


class DayCountFactory:
    """Factory for creating day count conventions."""

    _DAYCOUNT_REGISTRY: Dict[str, Callable[[], ore.DayCounter]] = {
        "Actual360": lambda: ore.Actual360(),
        "Actual365Fixed": lambda: ore.Actual365Fixed(),
        "Actual365NoLeap": lambda: ore.Actual365Fixed(ore.Actual365Fixed.NoLeap),
        "ActualActual": lambda: ore.ActualActual(ore.ActualActual.ISDA),
        "Thirty360": lambda: ore.Thirty360(ore.Thirty360.BondBasis),
    }

    @classmethod
    def create(cls, day_count_name: str) -> ore.DayCounter:
        """Create a day count convention by name."""
        if day_count_name not in cls._DAYCOUNT_REGISTRY:
            raise ValueError(
                f"Unknown day count: {day_count_name}. "
                f"Available: {list(cls._DAYCOUNT_REGISTRY.keys())}"
            )
        return cls._DAYCOUNT_REGISTRY[day_count_name]()


class OISCurveBuilder:
    """
    Builds OIS discount curves from OIS swap rates.

    This is a helper class for building single-currency discount curves.
    """

    def __init__(
        self,
        eval_date: ore.Date,
        ccy_config: CurrencyConfig,
        ois_rates: List[Tuple[str, float]],
        settlement_days: int = 2,
    ):
        """
        Initialize the OIS curve builder.

        Args:
            eval_date: Evaluation date
            ccy_config: Currency configuration
            ois_rates: List of (tenor, rate) tuples
            settlement_days: Settlement days for OIS swaps
        """
        self.eval_date = eval_date
        self.ccy_config = ccy_config
        self.ois_rates = ois_rates
        self.settlement_days = settlement_days

        self.calendar = CalendarFactory.create(ccy_config.calendar_name)
        self.day_count = DayCountFactory.create(ccy_config.day_count)

    @staticmethod
    def _tenor_to_period(tenor: str) -> ore.Period:
        """Convert tenor string to ORE Period."""
        if tenor.endswith("W"):
            return ore.Period(int(tenor[:-1]), ore.Weeks)
        elif tenor.endswith("M"):
            return ore.Period(int(tenor[:-1]), ore.Months)
        elif tenor.endswith("Y"):
            return ore.Period(int(tenor[:-1]), ore.Years)
        else:
            raise ValueError(f"Unknown tenor format: {tenor}")

    def build(self) -> ore.YieldTermStructureHandle:
        """
        Build the OIS discount curve.

        Returns:
            Handle to the discount curve
        """
        helpers = []
        index = OISIndexFactory.create(self.ccy_config.ois_index_name)

        for tenor, rate in self.ois_rates:
            quote = ore.QuoteHandle(ore.SimpleQuote(rate))
            period = self._tenor_to_period(tenor)
            helper = ore.OISRateHelper(self.settlement_days, period, quote, index)
            helpers.append(helper)

        curve = ore.PiecewiseLogLinearDiscount(self.eval_date, helpers, self.day_count)
        curve.enableExtrapolation()

        return ore.YieldTermStructureHandle(curve)


class XCCYCurveBuilder:
    """
    Builds cross-currency basis curves using ORE.

    This class is focused on building the foreign XCCY basis curve
    from FX forwards and cross-currency basis swap quotes.

    Required input curves:
    - Domestic discount curve: for discounting (collateral/funding curve)
    - Domestic index curve: for projecting domestic floating rates
    - Foreign index curve: for projecting foreign floating rates

    The output is the foreign XCCY curve (foreign discount factors implied
    by cross-currency basis swaps).
    """

    def __init__(
        self,
        market_data: XCCYMarketData,
        domestic_discount_curve: ore.YieldTermStructureHandle,
        domestic_index_curve: ore.YieldTermStructureHandle,
        foreign_index_curve: ore.YieldTermStructureHandle,
    ):
        """
        Initialize the XCCY curve builder.

        Args:
            market_data: Cross-currency market data for curve bootstrapping
            domestic_discount_curve: Domestic discount/collateral curve (e.g., USD OIS)
            domestic_index_curve: Domestic index curve for floating rate projections
            foreign_index_curve: Foreign index curve for floating rate projections
        """
        self.market_data = market_data
        self.domestic_discount_curve = domestic_discount_curve
        self.domestic_index_curve = domestic_index_curve
        self.foreign_index_curve = foreign_index_curve

        self._setup_conventions()

        # Built curve (populated after build())
        self.foreign_xccy_curve: Optional[ore.YieldTermStructureHandle] = None
        self.fx_spot_handle: Optional[ore.QuoteHandle] = None

    def _setup_conventions(self) -> None:
        """Set up calendars and market conventions."""
        self.domestic_calendar = CalendarFactory.create(
            self.market_data.domestic_ccy.calendar_name
        )
        self.foreign_calendar = CalendarFactory.create(
            self.market_data.foreign_ccy.calendar_name
        )
        self.joint_calendar = ore.JointCalendar(
            self.domestic_calendar, self.foreign_calendar
        )
        self.foreign_day_count = DayCountFactory.create(
            self.market_data.foreign_ccy.day_count
        )
        self.settlement_days = 2

        val_date = self.market_data.valuation_date
        self.eval_date = ore.Date(val_date.day, val_date.month, val_date.year)
        ore.Settings.instance().evaluationDate = self.eval_date

    @staticmethod
    def _tenor_to_period(tenor: str) -> ore.Period:
        """Convert tenor string to ORE Period."""
        if tenor.endswith("W"):
            return ore.Period(int(tenor[:-1]), ore.Weeks)
        elif tenor.endswith("M"):
            return ore.Period(int(tenor[:-1]), ore.Months)
        elif tenor.endswith("Y"):
            return ore.Period(int(tenor[:-1]), ore.Years)
        else:
            raise ValueError(f"Unknown tenor format: {tenor}")

    @property
    def ccy_pair(self) -> str:
        """Return the currency pair string."""
        return self.market_data.ccy_pair

    @property
    def domestic_ccy(self) -> str:
        """Return domestic currency code."""
        return self.market_data.domestic_ccy.ccy

    @property
    def foreign_ccy(self) -> str:
        """Return foreign currency code."""
        return self.market_data.foreign_ccy.ccy

    def build(self) -> ore.YieldTermStructureHandle:
        """
        Build the cross-currency basis curve for foreign currency
        collateralized in domestic currency.

        Returns:
            Handle to the foreign cross-currency basis curve
        """
        # FX spot quote
        fx_spot_quote = ore.QuoteHandle(ore.SimpleQuote(self.market_data.fx_spot))
        self.fx_spot_handle = fx_spot_quote

        # Relinkable handle for the curve being bootstrapped
        xccy_curve_handle = ore.RelinkableYieldTermStructureHandle()

        helpers = []

        # Determine if FX base currency equals collateral (domestic) currency
        # For GBPUSD: fx_base=GBP, domestic=USD → False
        # For USDJPY: fx_base=USD, domestic=USD → True
        is_fx_base_collateral = self.market_data.is_fx_base_domestic

        # Add FX forward helpers for short end
        for fwd in self.market_data.fx_forwards:
            fwd_points = fwd.forward_points / 10000.0
            fwd_points_quote = ore.QuoteHandle(ore.SimpleQuote(fwd_points))
            period = self._tenor_to_period(fwd.tenor)

            helper = ore.FxSwapRateHelper(
                fwd_points_quote,
                fx_spot_quote,
                period,
                self.settlement_days,
                self.joint_calendar,
                ore.ModifiedFollowing,
                True,  # end of month
                is_fx_base_collateral,  # isFxBaseCurrencyCollateralCurrency
                self.domestic_discount_curve,
            )
            helpers.append(helper)

        # Add cross-currency basis swap helpers for long end
        # Use mark-to-market reset helpers (market standard for XCCY basis swaps)
        #
        # MtM XCCY Basis Swap structure (ORE convention):
        # - Domestic leg (USD): Notional RESETS at each period based on FX fixing
        # - Foreign leg: FIXED notional, pays foreign OIS + basis spread
        #
        # The spread is on the foreign leg (spreadOnForeignCcy=true by default).
        # A negative basis (e.g., -12.5 bps) means foreign pays OIS - 12.5 bps.
        domestic_index = OISIndexFactory.create(
            self.market_data.domestic_ccy.ois_index_name,
            self.domestic_index_curve,
        )
        foreign_index = OISIndexFactory.create(
            self.market_data.foreign_ccy.ois_index_name,
            self.foreign_index_curve,
        )

        for swap in self.market_data.xccy_basis_swaps:
            spread = swap.basis_spread / 10000.0
            spread_quote = ore.QuoteHandle(ore.SimpleQuote(spread))
            period = self._tenor_to_period(swap.tenor)

            # Use MtM reset helper - market standard for XCCY basis swaps
            # Parameter order: foreign first, domestic second (per ORE API)
            helper = ore.CrossCcyBasisMtMResetSwapHelper(
                spread_quote,                    # spreadQuote: basis spread (on foreign leg)
                fx_spot_quote,                   # spotFX: FX spot rate
                self.settlement_days,            # settlementDays
                self.joint_calendar,             # settlementCalendar
                period,                          # swapTenor
                ore.ModifiedFollowing,           # rollConvention
                foreign_index,                   # foreignCcyIndex (foreign, FIXED notional)
                domestic_index,                  # domesticCcyIndex (USD, notional RESETS)
                xccy_curve_handle,               # foreignCcyDiscountCurve (being bootstrapped)
                self.domestic_discount_curve,    # domesticCcyDiscountCurve (USD discount)
                True,                            # foreignIndexGiven
                True,                            # domesticIndexGiven
                False,                           # foreignDiscountCurveGiven (bootstrapping this)
                True,                            # domesticDiscountCurveGiven
                self.foreign_index_curve,        # foreignCcyFxFwdRateCurve
                self.domestic_index_curve,       # domesticCcyFxFwdRateCurve
            )
            helpers.append(helper)

        # Bootstrap the curve
        curve = ore.PiecewiseLogLinearDiscount(
            self.eval_date,
            helpers,
            self.foreign_day_count,
        )
        curve.enableExtrapolation()
        xccy_curve_handle.linkTo(curve)

        self.foreign_xccy_curve = ore.YieldTermStructureHandle(curve)
        return self.foreign_xccy_curve

    def get_discount_factor(self, target_date: date) -> float:
        """Get discount factor from the XCCY curve."""
        if self.foreign_xccy_curve is None:
            raise ValueError("XCCY curve not built. Call build() first.")
        ore_date = ore.Date(target_date.day, target_date.month, target_date.year)
        return self.foreign_xccy_curve.discount(ore_date)

    def get_zero_rate(
        self, target_date: date, compounding: str = "continuous"
    ) -> float:
        """Get zero rate from the XCCY curve."""
        if self.foreign_xccy_curve is None:
            raise ValueError("XCCY curve not built. Call build() first.")
        ore_date = ore.Date(target_date.day, target_date.month, target_date.year)
        comp = ore.Continuous if compounding == "continuous" else ore.Annual
        return self.foreign_xccy_curve.zeroRate(
            ore_date, self.foreign_day_count, comp
        ).rate()

    def get_implied_fx_forward(self, target_date: date) -> float:
        """
        Calculate implied FX forward rate from the curves.

        Uses covered interest rate parity:
        F = S * (DF_domestic / DF_foreign_xccy)
        """
        if self.foreign_xccy_curve is None:
            raise ValueError("XCCY curve not built. Call build() first.")

        ore_date = ore.Date(target_date.day, target_date.month, target_date.year)
        df_domestic = self.domestic_discount_curve.discount(ore_date)
        df_foreign = self.foreign_xccy_curve.discount(ore_date)

        return self.market_data.fx_spot * (df_domestic / df_foreign)

    def print_curve_summary(self) -> None:
        """Print a summary of the bootstrapped XCCY curve."""
        if self.foreign_xccy_curve is None:
            print("XCCY curve not built. Call build() first.")
            return

        print(f"\n{'='*70}")
        print(f"{self.ccy_pair} XCCY Basis Curve Summary")
        print(f"{'='*70}")
        print(f"Valuation Date: {self.market_data.valuation_date}")
        print(f"FX Spot: {self.market_data.fx_spot:.4f}")
        print(f"Domestic: {self.domestic_ccy} ({self.market_data.domestic_ccy.ois_index_name})")
        print(f"Foreign: {self.foreign_ccy} ({self.market_data.foreign_ccy.ois_index_name})")

        tenors = ["1M", "3M", "6M", "1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "20Y", "30Y"]

        print(f"\n{'Tenor':<8} {self.domestic_ccy + ' DF':<12} {self.foreign_ccy + ' DF':<12} "
              f"{'XCCY DF':<12} {'FX Fwd':<12} {'Basis (bps)':<12}")
        print("-" * 70)

        for tenor in tenors:
            period = self._tenor_to_period(tenor)
            target_date = self.joint_calendar.advance(self.eval_date, period)

            df_domestic = self.domestic_discount_curve.discount(target_date)
            df_foreign_idx = self.foreign_index_curve.discount(target_date)
            df_xccy = self.foreign_xccy_curve.discount(target_date)

            fx_fwd = self.market_data.fx_spot * (df_domestic / df_xccy)

            # Implied basis = difference between XCCY curve and foreign index curve
            year_frac = self.foreign_day_count.yearFraction(self.eval_date, target_date)
            if year_frac > 0:
                foreign_zero = -1.0 / year_frac * (df_foreign_idx - 1.0) if df_foreign_idx < 1 else 0
                xccy_zero = -1.0 / year_frac * (df_xccy - 1.0) if df_xccy < 1 else 0
                implied_basis = (xccy_zero - foreign_zero) * 10000
            else:
                implied_basis = 0.0

            print(
                f"{tenor:<8} {df_domestic:<12.6f} {df_foreign_idx:<12.6f} {df_xccy:<12.6f} "
                f"{fx_fwd:<12.4f} {implied_basis:<12.1f}"
            )

        print()


def build_xccy_curve(
    market_data: XCCYMarketData,
    domestic_discount_curve: ore.YieldTermStructureHandle,
    domestic_index_curve: ore.YieldTermStructureHandle,
    foreign_index_curve: ore.YieldTermStructureHandle,
) -> dict:
    """
    Build the foreign XCCY basis curve from market data and pre-built input curves.

    All three input curves must be provided - they are expected to come from
    external sources (e.g., curve loaders, market data systems).

    Args:
        market_data: Cross-currency market data (FX spot, forwards, basis swaps)
        domestic_discount_curve: Pre-built domestic discount/collateral curve
        domestic_index_curve: Pre-built domestic index curve for rate projections
        foreign_index_curve: Pre-built foreign index curve for rate projections

    Returns:
        Dictionary with curve handles:
        - "domestic_discount": Domestic discount curve (pass-through)
        - "domestic_index": Domestic index curve (pass-through)
        - "foreign_index": Foreign index curve (pass-through)
        - "foreign_xccy": Bootstrapped foreign XCCY basis curve
        - "fx_spot": FX spot quote handle
        - "xccy_builder": The XCCYCurveBuilder instance
    """
    val_date = market_data.valuation_date
    eval_date = ore.Date(val_date.day, val_date.month, val_date.year)
    ore.Settings.instance().evaluationDate = eval_date

    # Build XCCY basis curve
    xccy_builder = XCCYCurveBuilder(
        market_data=market_data,
        domestic_discount_curve=domestic_discount_curve,
        domestic_index_curve=domestic_index_curve,
        foreign_index_curve=foreign_index_curve,
    )
    xccy_curve = xccy_builder.build()

    return {
        "domestic_discount": domestic_discount_curve,
        "domestic_index": domestic_index_curve,
        "foreign_index": foreign_index_curve,
        "foreign_xccy": xccy_curve,
        "fx_spot": xccy_builder.fx_spot_handle,
        "xccy_builder": xccy_builder,
    }
