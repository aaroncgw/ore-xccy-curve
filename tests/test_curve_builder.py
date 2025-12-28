"""Tests for curve builder module."""

from datetime import date, timedelta
from typing import List, Tuple

import pytest

from ore_xccy_curve.market_data import MarketDataFactory, XCCYMarketData

# Try to import ORE - skip tests if not available
try:
    import ORE as ore
    from ore_xccy_curve.curve_builder import (
        CalendarFactory,
        DayCountFactory,
        OISCurveBuilder,
        OISIndexFactory,
        XCCYCurveBuilder,
        build_xccy_curve,
    )

    ORE_AVAILABLE = True
except ImportError:
    ORE_AVAILABLE = False
    ore = None
    XCCYCurveBuilder = None


# Dummy OIS rates for testing (these would come from external sources in production)
def get_dummy_usd_ois_rates() -> List[Tuple[str, float]]:
    """Get dummy USD SOFR OIS rates for testing."""
    return [
        ("1M", 0.0525), ("3M", 0.0530), ("6M", 0.0528), ("1Y", 0.0510),
        ("2Y", 0.0465), ("3Y", 0.0430), ("5Y", 0.0395), ("7Y", 0.0385),
        ("10Y", 0.0380), ("15Y", 0.0385), ("20Y", 0.0390), ("30Y", 0.0395),
    ]


def get_dummy_gbp_ois_rates() -> List[Tuple[str, float]]:
    """Get dummy GBP SONIA OIS rates for testing."""
    return [
        ("1M", 0.0515), ("3M", 0.0520), ("6M", 0.0510), ("1Y", 0.0485),
        ("2Y", 0.0440), ("3Y", 0.0405), ("5Y", 0.0375), ("7Y", 0.0365),
        ("10Y", 0.0360), ("15Y", 0.0365), ("20Y", 0.0370), ("30Y", 0.0375),
    ]


def get_dummy_eur_ois_rates() -> List[Tuple[str, float]]:
    """Get dummy EUR ESTR OIS rates for testing."""
    return [
        ("1M", 0.0390), ("3M", 0.0395), ("6M", 0.0388), ("1Y", 0.0365),
        ("2Y", 0.0320), ("3Y", 0.0290), ("5Y", 0.0265), ("7Y", 0.0260),
        ("10Y", 0.0258), ("15Y", 0.0265), ("20Y", 0.0270), ("30Y", 0.0275),
    ]


def get_dummy_jpy_ois_rates() -> List[Tuple[str, float]]:
    """Get dummy JPY TONAR OIS rates for testing."""
    return [
        ("1M", -0.001), ("3M", -0.001), ("6M", 0.000), ("1Y", 0.002),
        ("2Y", 0.005), ("3Y", 0.008), ("5Y", 0.012), ("7Y", 0.015),
        ("10Y", 0.018), ("15Y", 0.020), ("20Y", 0.022), ("30Y", 0.024),
    ]


@pytest.mark.skipif(not ORE_AVAILABLE, reason="ORE not installed")
class TestOISIndexFactory:
    """Tests for OISIndexFactory."""

    def test_create_sofr(self):
        """Test creating SOFR index."""
        index = OISIndexFactory.create("SOFR")
        assert index is not None

    def test_create_sonia(self):
        """Test creating SONIA index."""
        index = OISIndexFactory.create("SONIA")
        assert index is not None

    def test_create_unknown_raises(self):
        """Test creating unknown index raises error."""
        with pytest.raises(ValueError, match="Unknown OIS index"):
            OISIndexFactory.create("UNKNOWN")


@pytest.mark.skipif(not ORE_AVAILABLE, reason="ORE not installed")
class TestCalendarFactory:
    """Tests for CalendarFactory."""

    def test_create_us_calendar(self):
        """Test creating US calendar."""
        cal = CalendarFactory.create("US-FederalReserve")
        assert cal is not None

    def test_create_uk_calendar(self):
        """Test creating UK calendar."""
        cal = CalendarFactory.create("UK-Exchange")
        assert cal is not None

    def test_create_unknown_raises(self):
        """Test creating unknown calendar raises error."""
        with pytest.raises(ValueError, match="Unknown calendar"):
            CalendarFactory.create("UNKNOWN")


@pytest.mark.skipif(not ORE_AVAILABLE, reason="ORE not installed")
class TestDayCountFactory:
    """Tests for DayCountFactory."""

    def test_create_actual360(self):
        """Test creating Actual360 day count."""
        dc = DayCountFactory.create("Actual360")
        assert dc is not None

    def test_create_actual365(self):
        """Test creating Actual365Fixed day count."""
        dc = DayCountFactory.create("Actual365Fixed")
        assert dc is not None

    def test_create_unknown_raises(self):
        """Test creating unknown day count raises error."""
        with pytest.raises(ValueError, match="Unknown day count"):
            DayCountFactory.create("UNKNOWN")


@pytest.mark.skipif(not ORE_AVAILABLE, reason="ORE not installed")
class TestOISCurveBuilder:
    """Tests for OISCurveBuilder class."""

    @pytest.fixture
    def eval_date(self) -> ore.Date:
        """Create evaluation date."""
        d = ore.Date(15, 1, 2024)
        ore.Settings.instance().evaluationDate = d
        return d

    def test_build_usd_curve(self, eval_date: ore.Date):
        """Test building USD OIS curve."""
        config = MarketDataFactory.CURRENCY_CONFIGS["USD"]
        rates = [("1M", 0.0525), ("3M", 0.0530), ("1Y", 0.0510), ("5Y", 0.0395)]

        builder = OISCurveBuilder(eval_date, config, rates)
        curve = builder.build()

        assert curve is not None
        # Check DF at 1Y is reasonable
        df_1y = curve.discount(eval_date + ore.Period(1, ore.Years))
        assert 0.9 < df_1y < 1.0

    def test_build_gbp_curve(self, eval_date: ore.Date):
        """Test building GBP OIS curve."""
        config = MarketDataFactory.CURRENCY_CONFIGS["GBP"]
        rates = [("1M", 0.0515), ("3M", 0.0520), ("1Y", 0.0485), ("5Y", 0.0375)]

        builder = OISCurveBuilder(eval_date, config, rates)
        curve = builder.build()

        assert curve is not None


@pytest.mark.skipif(not ORE_AVAILABLE, reason="ORE not installed")
class TestXCCYCurveBuilder:
    """Tests for XCCYCurveBuilder class."""

    @pytest.fixture
    def market_data(self) -> XCCYMarketData:
        """Create test market data."""
        return MarketDataFactory.create_gbpusd()

    @pytest.fixture
    def curves(self, market_data: XCCYMarketData) -> dict:
        """Build all curves including the input OIS curves."""
        val_date = market_data.valuation_date
        eval_date = ore.Date(val_date.day, val_date.month, val_date.year)
        ore.Settings.instance().evaluationDate = eval_date

        # Build input curves (simulating external curve loading)
        usd_curve = OISCurveBuilder(
            eval_date, market_data.domestic_ccy, get_dummy_usd_ois_rates()
        ).build()
        gbp_curve = OISCurveBuilder(
            eval_date, market_data.foreign_ccy, get_dummy_gbp_ois_rates()
        ).build()

        # Build XCCY curve
        return build_xccy_curve(
            market_data,
            domestic_discount_curve=usd_curve,
            domestic_index_curve=usd_curve,
            foreign_index_curve=gbp_curve,
        )

    @pytest.fixture
    def xccy_builder(self, curves: dict) -> XCCYCurveBuilder:
        """Get XCCY builder from curves."""
        return curves["xccy_builder"]

    def test_build_xccy_curve(self, curves: dict):
        """Test building all curves via convenience function."""
        assert "domestic_discount" in curves
        assert "domestic_index" in curves
        assert "foreign_index" in curves
        assert "foreign_xccy" in curves
        assert "fx_spot" in curves
        assert "xccy_builder" in curves

    def test_ccy_pair_property(self, xccy_builder: XCCYCurveBuilder):
        """Test ccy_pair property."""
        assert xccy_builder.ccy_pair == "GBPUSD"

    def test_domestic_foreign_ccy_properties(self, xccy_builder: XCCYCurveBuilder):
        """Test currency code properties."""
        assert xccy_builder.domestic_ccy == "USD"
        assert xccy_builder.foreign_ccy == "GBP"

    def test_xccy_curve_is_built(self, xccy_builder: XCCYCurveBuilder):
        """Test that XCCY curve is built."""
        assert xccy_builder.foreign_xccy_curve is not None

    def test_get_discount_factor(self, xccy_builder: XCCYCurveBuilder):
        """Test getting discount factor from XCCY curve."""
        val_date = xccy_builder.market_data.valuation_date
        future_date = val_date + timedelta(days=365)

        df = xccy_builder.get_discount_factor(future_date)
        assert 0.9 < df < 1.0

    def test_get_discount_factor_without_build_raises(self, market_data: XCCYMarketData):
        """Test getting discount factor before building raises error."""
        val_date = market_data.valuation_date
        eval_date = ore.Date(val_date.day, val_date.month, val_date.year)
        ore.Settings.instance().evaluationDate = eval_date

        # Build input curves
        usd_curve = OISCurveBuilder(
            eval_date, market_data.domestic_ccy, get_dummy_usd_ois_rates()
        ).build()
        gbp_curve = OISCurveBuilder(
            eval_date, market_data.foreign_ccy, get_dummy_gbp_ois_rates()
        ).build()

        # Create builder without calling build()
        builder = XCCYCurveBuilder(
            market_data,
            domestic_discount_curve=usd_curve,
            domestic_index_curve=usd_curve,
            foreign_index_curve=gbp_curve,
        )

        with pytest.raises(ValueError, match="not built"):
            builder.get_discount_factor(val_date + timedelta(days=90))

    def test_get_zero_rate(self, xccy_builder: XCCYCurveBuilder):
        """Test getting zero rate from XCCY curve."""
        val_date = xccy_builder.market_data.valuation_date
        future_date = val_date + timedelta(days=365)

        zero_rate = xccy_builder.get_zero_rate(future_date)
        assert 0 < zero_rate < 0.10

    def test_get_implied_fx_forward(self, xccy_builder: XCCYCurveBuilder):
        """Test calculating implied FX forward."""
        val_date = xccy_builder.market_data.valuation_date
        fwd_3m = xccy_builder.get_implied_fx_forward(val_date + timedelta(days=90))

        spot = xccy_builder.market_data.fx_spot
        assert abs(fwd_3m - spot) / spot < 0.05

    def test_xccy_curve_reflects_basis(self, curves: dict, xccy_builder: XCCYCurveBuilder):
        """Test that XCCY curve reflects the basis adjustment."""
        val_date = xccy_builder.market_data.valuation_date
        target_date = val_date + timedelta(days=365 * 5)
        ore_date = ore.Date(target_date.day, target_date.month, target_date.year)

        df_foreign_idx = curves["foreign_index"].discount(ore_date)
        df_xccy = xccy_builder.get_discount_factor(target_date)

        # XCCY curve should differ from plain foreign index curve due to basis
        assert abs(df_xccy - df_foreign_idx) > 0.001

    def test_print_curve_summary(self, xccy_builder: XCCYCurveBuilder, capsys):
        """Test print_curve_summary outputs data."""
        xccy_builder.print_curve_summary()

        captured = capsys.readouterr()
        assert "GBPUSD XCCY Basis Curve Summary" in captured.out
        assert "USD DF" in captured.out
        assert "GBP DF" in captured.out
        assert "XCCY DF" in captured.out


@pytest.mark.skipif(not ORE_AVAILABLE, reason="ORE not installed")
class TestXCCYCurveBuilderMultiplePairs:
    """Tests for XCCYCurveBuilder with multiple currency pairs."""

    @pytest.fixture
    def eval_date(self) -> ore.Date:
        """Create evaluation date."""
        d = ore.Date(15, 1, 2024)
        ore.Settings.instance().evaluationDate = d
        return d

    @pytest.fixture
    def usd_curve(self, eval_date: ore.Date) -> ore.YieldTermStructureHandle:
        """Build USD OIS curve."""
        config = MarketDataFactory.CURRENCY_CONFIGS["USD"]
        return OISCurveBuilder(eval_date, config, get_dummy_usd_ois_rates()).build()

    def test_build_eurusd_curves(self, eval_date: ore.Date, usd_curve):
        """Test building EURUSD curves."""
        market_data = MarketDataFactory.create_eurusd()

        eur_curve = OISCurveBuilder(
            eval_date, market_data.foreign_ccy, get_dummy_eur_ois_rates()
        ).build()

        result = build_xccy_curve(
            market_data,
            domestic_discount_curve=usd_curve,
            domestic_index_curve=usd_curve,
            foreign_index_curve=eur_curve,
        )

        xccy_builder = result["xccy_builder"]
        assert xccy_builder.ccy_pair == "EURUSD"
        assert xccy_builder.domestic_ccy == "USD"
        assert xccy_builder.foreign_ccy == "EUR"
        assert xccy_builder.foreign_xccy_curve is not None

    def test_build_usdjpy_curves(self, eval_date: ore.Date, usd_curve):
        """Test building USDJPY curves."""
        market_data = MarketDataFactory.create_usdjpy()

        jpy_curve = OISCurveBuilder(
            eval_date, market_data.foreign_ccy, get_dummy_jpy_ois_rates()
        ).build()

        result = build_xccy_curve(
            market_data,
            domestic_discount_curve=usd_curve,
            domestic_index_curve=usd_curve,
            foreign_index_curve=jpy_curve,
        )

        xccy_builder = result["xccy_builder"]
        assert xccy_builder.domestic_ccy == "USD"
        assert xccy_builder.foreign_ccy == "JPY"
        assert xccy_builder.foreign_xccy_curve is not None
