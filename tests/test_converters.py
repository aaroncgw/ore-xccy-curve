"""Tests for converter functions."""

import pytest

# Try to import ORE - skip tests if not available
try:
    import ORE as ore
    from ore_xccy_curve.converters import (
        create_flat_forward_curve,
        quantlib_curve_to_ore_handle,
        quantlib_curve_to_relinkable_handle,
    )

    ORE_AVAILABLE = True
except ImportError:
    ORE_AVAILABLE = False
    ore = None


@pytest.mark.skipif(not ORE_AVAILABLE, reason="ORE not installed")
class TestQuantLibToOreHandle:
    """Tests for quantlib_curve_to_ore_handle."""

    @pytest.fixture
    def eval_date(self) -> ore.Date:
        """Create evaluation date."""
        d = ore.Date(15, 1, 2024)
        ore.Settings.instance().evaluationDate = d
        return d

    def test_wrap_flat_forward(self, eval_date: ore.Date):
        """Test wrapping a FlatForward curve."""
        flat_curve = ore.FlatForward(eval_date, 0.05, ore.Actual360())

        handle = quantlib_curve_to_ore_handle(flat_curve)

        assert handle is not None
        # Check we can get discount factors
        df_1y = handle.discount(eval_date + ore.Period(1, ore.Years))
        assert 0.9 < df_1y < 1.0

    def test_wrap_piecewise_curve(self, eval_date: ore.Date):
        """Test wrapping a bootstrapped piecewise curve."""
        # Build a simple OIS curve
        helpers = []
        index = ore.Sofr()
        for tenor, rate in [("1M", 0.05), ("3M", 0.051), ("1Y", 0.048)]:
            quote = ore.QuoteHandle(ore.SimpleQuote(rate))
            period = ore.Period(tenor)
            helper = ore.OISRateHelper(2, period, quote, index)
            helpers.append(helper)

        curve = ore.PiecewiseLogLinearDiscount(eval_date, helpers, ore.Actual360())
        curve.enableExtrapolation()

        handle = quantlib_curve_to_ore_handle(curve)

        assert handle is not None
        df_1y = handle.discount(eval_date + ore.Period(1, ore.Years))
        assert 0.9 < df_1y < 1.0


@pytest.mark.skipif(not ORE_AVAILABLE, reason="ORE not installed")
class TestRelinkableHandle:
    """Tests for quantlib_curve_to_relinkable_handle."""

    @pytest.fixture
    def eval_date(self) -> ore.Date:
        """Create evaluation date."""
        d = ore.Date(15, 1, 2024)
        ore.Settings.instance().evaluationDate = d
        return d

    def test_create_empty_handle(self):
        """Test creating an empty relinkable handle."""
        handle = quantlib_curve_to_relinkable_handle()
        assert handle is not None

    def test_create_linked_handle(self, eval_date: ore.Date):
        """Test creating a handle linked to a curve."""
        flat_curve = ore.FlatForward(eval_date, 0.05, ore.Actual360())

        handle = quantlib_curve_to_relinkable_handle(flat_curve)

        assert handle is not None
        df_1y = handle.discount(eval_date + ore.Period(1, ore.Years))
        assert 0.9 < df_1y < 1.0

    def test_relink_handle(self, eval_date: ore.Date):
        """Test relinking a handle to a different curve."""
        curve1 = ore.FlatForward(eval_date, 0.05, ore.Actual360())
        curve2 = ore.FlatForward(eval_date, 0.03, ore.Actual360())

        handle = quantlib_curve_to_relinkable_handle(curve1)
        df_before = handle.discount(eval_date + ore.Period(1, ore.Years))

        handle.linkTo(curve2)
        df_after = handle.discount(eval_date + ore.Period(1, ore.Years))

        # With lower rate, DF should be higher
        assert df_after > df_before


@pytest.mark.skipif(not ORE_AVAILABLE, reason="ORE not installed")
class TestCreateFlatForwardCurve:
    """Tests for create_flat_forward_curve."""

    @pytest.fixture
    def eval_date(self) -> ore.Date:
        """Create evaluation date."""
        d = ore.Date(15, 1, 2024)
        ore.Settings.instance().evaluationDate = d
        return d

    def test_create_with_default_daycount(self, eval_date: ore.Date):
        """Test creating flat curve with default day count."""
        handle = create_flat_forward_curve(eval_date, 0.05)

        assert handle is not None
        df_1y = handle.discount(eval_date + ore.Period(1, ore.Years))
        assert 0.9 < df_1y < 1.0

    def test_create_with_custom_daycount(self, eval_date: ore.Date):
        """Test creating flat curve with custom day count."""
        handle = create_flat_forward_curve(
            eval_date, 0.05, ore.Actual365Fixed()
        )

        assert handle is not None
        df_1y = handle.discount(eval_date + ore.Period(1, ore.Years))
        assert 0.9 < df_1y < 1.0

    def test_extrapolation_enabled(self, eval_date: ore.Date):
        """Test that extrapolation is enabled on the curve."""
        handle = create_flat_forward_curve(eval_date, 0.05)

        # Should not raise for dates far in the future
        df_50y = handle.discount(eval_date + ore.Period(50, ore.Years))
        assert df_50y > 0
