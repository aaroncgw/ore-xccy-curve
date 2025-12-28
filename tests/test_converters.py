"""Tests for converter functions."""

import tempfile
from pathlib import Path

import pytest

# Try to import ORE - skip tests if not available
try:
    import ORE as ore
    from ore_xccy_curve.converters import (
        create_flat_forward_curve,
        extract_curve_points,
        get_discount_factors,
        get_zero_rates,
        load_curve_from_csv,
        load_curve_from_json,
        ore_curve_to_quantlib,
        ore_handle_to_curve,
        quantlib_curve_to_ore_handle,
        quantlib_curve_to_relinkable_handle,
        save_curve_to_csv,
        save_curve_to_json,
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


@pytest.mark.skipif(not ORE_AVAILABLE, reason="ORE not installed")
class TestOreHandleToCurve:
    """Tests for ore_handle_to_curve."""

    @pytest.fixture
    def eval_date(self) -> ore.Date:
        """Create evaluation date."""
        d = ore.Date(15, 1, 2024)
        ore.Settings.instance().evaluationDate = d
        return d

    def test_extract_curve_from_handle(self, eval_date: ore.Date):
        """Test extracting curve from a handle."""
        handle = create_flat_forward_curve(eval_date, 0.05)

        curve = ore_handle_to_curve(handle)

        assert curve is not None
        # Verify the curve works
        df = curve.discount(eval_date + ore.Period(1, ore.Years))
        assert 0.9 < df < 1.0

    def test_empty_handle_raises(self):
        """Test that empty handle raises ValueError."""
        empty_handle = ore.YieldTermStructureHandle()

        with pytest.raises(ValueError, match="empty"):
            ore_handle_to_curve(empty_handle)

    def test_curve_is_quantlib_compatible(self, eval_date: ore.Date):
        """Test that extracted curve is QuantLib-compatible."""
        handle = create_flat_forward_curve(eval_date, 0.05)
        curve = ore_handle_to_curve(handle)

        # These are QuantLib methods that should work
        assert curve.referenceDate() == eval_date
        assert curve.maxDate() > eval_date


@pytest.mark.skipif(not ORE_AVAILABLE, reason="ORE not installed")
class TestOreCurveToQuantlib:
    """Tests for ore_curve_to_quantlib."""

    @pytest.fixture
    def eval_date(self) -> ore.Date:
        """Create evaluation date."""
        d = ore.Date(15, 1, 2024)
        ore.Settings.instance().evaluationDate = d
        return d

    def test_convert_ore_curve(self, eval_date: ore.Date):
        """Test converting ORE curve to QuantLib."""
        ore_curve = ore.FlatForward(eval_date, 0.05, ore.Actual360())

        ql_curve = ore_curve_to_quantlib(ore_curve)

        # Should be the same object (ORE inherits from QuantLib)
        assert ql_curve is ore_curve
        # Should still work
        df = ql_curve.discount(eval_date + ore.Period(1, ore.Years))
        assert 0.9 < df < 1.0


@pytest.mark.skipif(not ORE_AVAILABLE, reason="ORE not installed")
class TestGetDiscountFactors:
    """Tests for get_discount_factors."""

    @pytest.fixture
    def eval_date(self) -> ore.Date:
        """Create evaluation date."""
        d = ore.Date(15, 1, 2024)
        ore.Settings.instance().evaluationDate = d
        return d

    def test_get_multiple_dfs(self, eval_date: ore.Date):
        """Test getting discount factors for multiple dates."""
        handle = create_flat_forward_curve(eval_date, 0.05)
        dates = [
            eval_date + ore.Period(1, ore.Years),
            eval_date + ore.Period(2, ore.Years),
            eval_date + ore.Period(5, ore.Years),
        ]

        dfs = get_discount_factors(handle, dates)

        assert len(dfs) == 3
        # DFs should decrease with time
        assert dfs[0] > dfs[1] > dfs[2]
        # All should be between 0 and 1
        for df in dfs:
            assert 0 < df < 1


@pytest.mark.skipif(not ORE_AVAILABLE, reason="ORE not installed")
class TestGetZeroRates:
    """Tests for get_zero_rates."""

    @pytest.fixture
    def eval_date(self) -> ore.Date:
        """Create evaluation date."""
        d = ore.Date(15, 1, 2024)
        ore.Settings.instance().evaluationDate = d
        return d

    def test_get_multiple_zero_rates(self, eval_date: ore.Date):
        """Test getting zero rates for multiple dates."""
        handle = create_flat_forward_curve(eval_date, 0.05)
        dates = [
            eval_date + ore.Period(1, ore.Years),
            eval_date + ore.Period(5, ore.Years),
            eval_date + ore.Period(10, ore.Years),
        ]

        rates = get_zero_rates(handle, dates)

        assert len(rates) == 3
        # For flat curve, rates should be approximately equal
        for rate in rates:
            assert abs(rate - 0.05) < 0.001

    def test_get_zero_rates_with_custom_daycount(self, eval_date: ore.Date):
        """Test getting zero rates with custom day count."""
        handle = create_flat_forward_curve(eval_date, 0.05)
        dates = [eval_date + ore.Period(1, ore.Years)]

        rates = get_zero_rates(handle, dates, day_count=ore.Actual360())

        assert len(rates) == 1
        assert rates[0] > 0


@pytest.mark.skipif(not ORE_AVAILABLE, reason="ORE not installed")
class TestExtractCurvePoints:
    """Tests for extract_curve_points."""

    @pytest.fixture
    def eval_date(self) -> ore.Date:
        """Create evaluation date."""
        d = ore.Date(15, 1, 2024)
        ore.Settings.instance().evaluationDate = d
        return d

    def test_extract_default_tenors(self, eval_date: ore.Date):
        """Test extracting curve points with default tenors."""
        handle = create_flat_forward_curve(eval_date, 0.05)

        points = extract_curve_points(handle, max_years=10)

        # Should have short tenors + yearly up to 10Y
        assert len(points) > 10
        # Each point should have (date, df, zero_rate)
        for dt, df, zr in points:
            assert isinstance(dt, str)
            assert 0 < df < 1
            assert zr > 0

    def test_extract_specific_tenors(self, eval_date: ore.Date):
        """Test extracting specific tenors."""
        handle = create_flat_forward_curve(eval_date, 0.05)

        points = extract_curve_points(handle, tenors=["1Y", "5Y", "10Y"])

        assert len(points) == 3


@pytest.mark.skipif(not ORE_AVAILABLE, reason="ORE not installed")
class TestCurvePersistenceCSV:
    """Tests for CSV curve persistence."""

    @pytest.fixture
    def eval_date(self) -> ore.Date:
        """Create evaluation date."""
        d = ore.Date(15, 1, 2024)
        ore.Settings.instance().evaluationDate = d
        return d

    def test_save_and_load_csv(self, eval_date: ore.Date):
        """Test saving and loading a curve to/from CSV."""
        original_handle = create_flat_forward_curve(eval_date, 0.05)

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            csv_path = Path(f.name)

        try:
            # Save
            save_curve_to_csv(
                original_handle,
                csv_path,
                tenors=["1Y", "5Y", "10Y"],
                curve_name="TEST_CURVE",
            )

            # Verify file exists and has content
            assert csv_path.exists()
            content = csv_path.read_text()
            assert "TEST_CURVE" in content
            assert "discount_factor" in content

            # Load
            loaded_handle = load_curve_from_csv(csv_path)

            # Compare discount factors
            date_1y = eval_date + ore.Period(1, ore.Years)
            date_5y = eval_date + ore.Period(5, ore.Years)

            orig_df_1y = original_handle.discount(date_1y)
            loaded_df_1y = loaded_handle.discount(date_1y)
            assert abs(orig_df_1y - loaded_df_1y) < 1e-10

            orig_df_5y = original_handle.discount(date_5y)
            loaded_df_5y = loaded_handle.discount(date_5y)
            assert abs(orig_df_5y - loaded_df_5y) < 1e-10
        finally:
            csv_path.unlink(missing_ok=True)

    def test_load_csv_with_zero_rates(self, eval_date: ore.Date):
        """Test loading a curve using zero rates instead of discount factors."""
        original_handle = create_flat_forward_curve(eval_date, 0.05)

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            csv_path = Path(f.name)

        try:
            save_curve_to_csv(original_handle, csv_path, tenors=["1Y", "5Y", "10Y"])
            loaded_handle = load_curve_from_csv(csv_path, use_discount_factors=False)

            # Should still produce valid curve
            date_5y = eval_date + ore.Period(5, ore.Years)
            df = loaded_handle.discount(date_5y)
            assert 0 < df < 1
        finally:
            csv_path.unlink(missing_ok=True)


@pytest.mark.skipif(not ORE_AVAILABLE, reason="ORE not installed")
class TestCurvePersistenceJSON:
    """Tests for JSON curve persistence."""

    @pytest.fixture
    def eval_date(self) -> ore.Date:
        """Create evaluation date."""
        d = ore.Date(15, 1, 2024)
        ore.Settings.instance().evaluationDate = d
        return d

    def test_save_and_load_json(self, eval_date: ore.Date):
        """Test saving and loading a curve to/from JSON."""
        original_handle = create_flat_forward_curve(eval_date, 0.05)

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            json_path = Path(f.name)

        try:
            # Save
            save_curve_to_json(
                original_handle,
                json_path,
                tenors=["1Y", "5Y", "10Y"],
                curve_name="TEST_CURVE",
            )

            # Verify file exists and has content
            assert json_path.exists()
            import json
            with open(json_path) as f:
                data = json.load(f)
            assert data["curve_name"] == "TEST_CURVE"
            assert len(data["points"]) == 3

            # Load
            loaded_handle = load_curve_from_json(json_path)

            # Compare discount factors
            date_1y = eval_date + ore.Period(1, ore.Years)
            date_5y = eval_date + ore.Period(5, ore.Years)

            orig_df_1y = original_handle.discount(date_1y)
            loaded_df_1y = loaded_handle.discount(date_1y)
            assert abs(orig_df_1y - loaded_df_1y) < 1e-10

            orig_df_5y = original_handle.discount(date_5y)
            loaded_df_5y = loaded_handle.discount(date_5y)
            assert abs(orig_df_5y - loaded_df_5y) < 1e-10
        finally:
            json_path.unlink(missing_ok=True)

    def test_load_json_with_zero_rates(self, eval_date: ore.Date):
        """Test loading a curve using zero rates instead of discount factors."""
        original_handle = create_flat_forward_curve(eval_date, 0.05)

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            json_path = Path(f.name)

        try:
            save_curve_to_json(original_handle, json_path, tenors=["1Y", "5Y", "10Y"])
            loaded_handle = load_curve_from_json(json_path, use_discount_factors=False)

            # Should still produce valid curve
            date_5y = eval_date + ore.Period(5, ore.Years)
            df = loaded_handle.discount(date_5y)
            assert 0 < df < 1
        finally:
            json_path.unlink(missing_ok=True)
