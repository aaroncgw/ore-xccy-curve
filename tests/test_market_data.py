"""Tests for market data module."""

from datetime import date

import pytest

from ore_xccy_curve.market_data import (
    CurrencyConfig,
    FXForwardQuote,
    MarketDataFactory,
    XCCYBasisSwapQuote,
    XCCYMarketData,
)


class TestFXForwardQuote:
    """Tests for FXForwardQuote dataclass."""

    def test_creation(self):
        """Test FXForwardQuote creation."""
        quote = FXForwardQuote(tenor="3M", forward_points=-38.0, days=90)
        assert quote.tenor == "3M"
        assert quote.forward_points == -38.0
        assert quote.days == 90


class TestXCCYBasisSwapQuote:
    """Tests for XCCYBasisSwapQuote dataclass."""

    def test_creation(self):
        """Test XCCYBasisSwapQuote creation."""
        quote = XCCYBasisSwapQuote(tenor="5Y", basis_spread=-17.5, years=5)
        assert quote.tenor == "5Y"
        assert quote.basis_spread == -17.5
        assert quote.years == 5


class TestCurrencyConfig:
    """Tests for CurrencyConfig dataclass."""

    def test_creation(self):
        """Test CurrencyConfig creation."""
        config = CurrencyConfig(
            ccy="USD",
            ois_index_name="SOFR",
            calendar_name="US-FederalReserve",
            day_count="Actual360",
        )
        assert config.ccy == "USD"
        assert config.ois_index_name == "SOFR"
        assert config.calendar_name == "US-FederalReserve"
        assert config.day_count == "Actual360"


class TestXCCYMarketData:
    """Tests for XCCYMarketData class."""

    @pytest.fixture
    def gbpusd_data(self) -> XCCYMarketData:
        """Create GBPUSD test data."""
        return MarketDataFactory.create_gbpusd()

    def test_create_gbpusd(self, gbpusd_data: XCCYMarketData):
        """Test creating GBPUSD market data."""
        assert gbpusd_data.valuation_date == date(2024, 1, 15)
        assert gbpusd_data.fx_spot == 1.2750
        assert len(gbpusd_data.fx_forwards) == 8
        assert len(gbpusd_data.xccy_basis_swaps) == 9

    def test_ccy_pair_property(self, gbpusd_data: XCCYMarketData):
        """Test ccy_pair property."""
        assert gbpusd_data.ccy_pair == "GBPUSD"

    def test_domestic_foreign_currencies(self, gbpusd_data: XCCYMarketData):
        """Test domestic and foreign currency configs."""
        assert gbpusd_data.domestic_ccy.ccy == "USD"
        assert gbpusd_data.domestic_ccy.ois_index_name == "SOFR"
        assert gbpusd_data.foreign_ccy.ccy == "GBP"
        assert gbpusd_data.foreign_ccy.ois_index_name == "SONIA"

    def test_create_custom_date(self):
        """Test creating data with custom valuation date."""
        custom_date = date(2024, 6, 15)
        data = MarketDataFactory.create_gbpusd(custom_date)
        assert data.valuation_date == custom_date

    def test_get_forward_rate(self, gbpusd_data: XCCYMarketData):
        """Test getting forward rate for a tenor."""
        fwd_rate = gbpusd_data.get_forward_rate("3M")
        expected = 1.2750 + (-38.0 / 10000.0)
        assert abs(fwd_rate - expected) < 1e-6

    def test_get_forward_rate_unknown_tenor(self, gbpusd_data: XCCYMarketData):
        """Test getting forward rate for unknown tenor raises error."""
        with pytest.raises(ValueError, match="Unknown tenor"):
            gbpusd_data.get_forward_rate("5Y")

    def test_get_basis_spread(self, gbpusd_data: XCCYMarketData):
        """Test getting basis spread for a tenor."""
        spread = gbpusd_data.get_basis_spread_bps("5Y")
        assert spread == -17.5

    def test_get_basis_spread_unknown_tenor(self, gbpusd_data: XCCYMarketData):
        """Test getting basis spread for unknown tenor raises error."""
        with pytest.raises(ValueError, match="Unknown tenor"):
            gbpusd_data.get_basis_spread_bps("1M")

    def test_fx_forwards_have_negative_points(self, gbpusd_data: XCCYMarketData):
        """Test that GBPUSD FX forwards have negative points."""
        for fwd in gbpusd_data.fx_forwards:
            assert fwd.forward_points < 0, f"Expected negative points for {fwd.tenor}"

    def test_xccy_basis_swaps_have_negative_spreads(self, gbpusd_data: XCCYMarketData):
        """Test that XCCY basis swaps have negative spreads."""
        for swap in gbpusd_data.xccy_basis_swaps:
            assert swap.basis_spread < 0, f"Expected negative spread for {swap.tenor}"

    def test_print_summary(self, gbpusd_data: XCCYMarketData, capsys):
        """Test print_summary outputs data."""
        gbpusd_data.print_summary()

        captured = capsys.readouterr()
        assert "GBPUSD Market Data Summary" in captured.out
        assert "FX Spot: 1.2750" in captured.out
        assert "FX Forwards" in captured.out
        assert "XCCY Basis Swaps" in captured.out


class TestMarketDataFactory:
    """Tests for MarketDataFactory."""

    def test_create_gbpusd(self):
        """Test creating GBPUSD data."""
        data = MarketDataFactory.create_gbpusd()
        assert data.ccy_pair == "GBPUSD"
        assert data.fx_spot == 1.2750

    def test_create_eurusd(self):
        """Test creating EURUSD data."""
        data = MarketDataFactory.create_eurusd()
        assert data.ccy_pair == "EURUSD"
        assert data.fx_spot == 1.0850
        assert data.domestic_ccy.ccy == "USD"
        assert data.foreign_ccy.ccy == "EUR"
        assert data.foreign_ccy.ois_index_name == "ESTR"

    def test_create_usdjpy(self):
        """Test creating USDJPY data."""
        data = MarketDataFactory.create_usdjpy()
        assert data.ccy_pair == "JPYUSD"  # Foreign + Domestic
        assert data.fx_spot == 148.50
        assert data.foreign_ccy.ccy == "JPY"
        assert data.foreign_ccy.ois_index_name == "TONAR"

    def test_currency_configs_available(self):
        """Test that common currency configs are available."""
        expected_ccys = ["USD", "GBP", "EUR", "JPY", "CHF", "AUD", "CAD"]
        for ccy in expected_ccys:
            assert ccy in MarketDataFactory.CURRENCY_CONFIGS