"""Tests for market — MarketAnalyzer and dynamic pricing."""

from unittest.mock import patch

from eu_pricing.market import MarketAnalyzer, get_market_analyzer


class TestMarketAnalyzer:
    """Tests for MarketAnalyzer dynamic pricing multiplier."""

    def test_default_multiplier(self):
        """Initial cached multiplier should be 1.0."""
        analyzer = MarketAnalyzer()
        # Reset internal cache to force a fresh calculation
        analyzer._last_update = 0.0
        with patch("os.getloadavg", return_value=(1.0, 0.8, 0.6)):
            multiplier = analyzer.get_current_multiplier()
            # Load 1.0 < 2.0 threshold → no load impact; no active tasks → no task impact
            assert multiplier == 1.0

    def test_multiplier_with_high_load(self):
        """CPU load above 2.0 should increase the multiplier."""
        analyzer = MarketAnalyzer()
        analyzer._last_update = 0.0
        with patch("os.getloadavg", return_value=(4.0, 3.0, 2.0)):
            multiplier = analyzer.get_current_multiplier()
            # Load impact: (4.0 - 2.0) * 0.2 = 0.4
            # Base: 1.0 + 0.4 = 1.4
            assert multiplier == 1.4

    def test_multiplier_rounds_to_two_decimals(self):
        """Multiplier should be rounded to 2 decimal places."""
        analyzer = MarketAnalyzer()
        analyzer._last_update = 0.0
        with patch("os.getloadavg", return_value=(2.3, 1.5, 1.0)):
            multiplier = analyzer.get_current_multiplier()
            # Load impact: (2.3 - 2.0) * 0.2 = 0.06
            # Base: 1.0 + 0.06 = 1.06
            assert multiplier == 1.06

    def test_caching_returns_same_value_within_interval(self, monkeypatch):
        """Within the update interval, the cached multiplier should be returned."""
        analyzer = MarketAnalyzer()
        analyzer._last_update = 0.0
        with patch("os.getloadavg", return_value=(4.0, 3.0, 2.0)):
            analyzer.get_current_multiplier()  # Prime cache

        # Set last_update far in the future to simulate cached state
        analyzer._last_update = 9999999999.0
        with patch("os.getloadavg", return_value=(10.0, 8.0, 5.0)):
            # Despite high load, cache should return the old value
            cached = analyzer.get_current_multiplier()
            assert cached == 1.4  # Cached from first calculation

    def test_get_current_multiplier_handles_oserror(self, monkeypatch):
        """Should handle OSError from os.getloadavg gracefully and return base multiplier."""
        analyzer = MarketAnalyzer()
        analyzer._last_update = 0.0

        def raise_oserror():
            raise OSError("Load average not available")

        monkeypatch.setattr("os.getloadavg", raise_oserror)
        multiplier = analyzer.get_current_multiplier()
        assert multiplier == 1.0

    def test_get_current_multiplier_handles_attribute_error(self, monkeypatch):
        """Should handle AttributeError (e.g., on non-unix) gracefully."""
        analyzer = MarketAnalyzer()
        analyzer._last_update = 0.0

        def raise_attribute_error():
            raise AttributeError("No loadavg on this platform")

        monkeypatch.setattr("os.getloadavg", raise_attribute_error)
        multiplier = analyzer.get_current_multiplier()
        assert multiplier == 1.0


class TestGetMarketAnalyzer:
    """Tests for the get_market_analyzer singleton factory."""

    def test_get_market_analyzer_returns_singleton(self):
        """get_market_analyzer() should always return the same instance."""
        a1 = get_market_analyzer()
        a2 = get_market_analyzer()
        assert a1 is a2

    def test_get_market_analyzer_instance_type(self):
        """get_market_analyzer() should return a MarketAnalyzer instance."""
        analyzer = get_market_analyzer()
        assert isinstance(analyzer, MarketAnalyzer)


class TestMarketAnalyzerCaching:
    """Tests for MarketAnalyzer caching behavior."""

    def test_cache_refreshes_after_interval(self, monkeypatch):
        """After update interval passes, cache should refresh."""
        import time as _time

        analyzer = MarketAnalyzer()
        analyzer._update_interval = 0.01  # Very short interval for testing

        # Force initial calculation with low load
        monkeypatch.setattr("os.getloadavg", lambda: (1.0, 0.8, 0.6))
        analyzer._last_update = 0.0
        v1 = analyzer.get_current_multiplier()
        assert v1 == 1.0

        # Travel forward in time past refresh interval
        _orig_time = _time.time
        monkeypatch.setattr(_time, "time", lambda: _orig_time() + 1.0)

        # Now with high load — should recalculate
        monkeypatch.setattr("os.getloadavg", lambda: (4.0, 3.0, 2.0))
        v2 = analyzer.get_current_multiplier()
        assert v2 == 1.4  # recalculated with high load

    def test_cache_returns_stale_on_refresh_error(self, monkeypatch):
        """If getloadavg fails on refresh, cache should keep previous value."""
        import time as _time

        analyzer = MarketAnalyzer()
        # First: get a valid cached value with low load
        monkeypatch.setattr("os.getloadavg", lambda: (1.0, 0.8, 0.6))
        analyzer._last_update = 0.0
        v1 = analyzer.get_current_multiplier()
        assert v1 == 1.0

        # Force refresh by forwarding time past update interval
        _orig_time = _time.time
        monkeypatch.setattr(_time, "time", lambda: _orig_time() + 100.0)
        # Make getloadavg raise on refresh
        monkeypatch.setattr("os.getloadavg", lambda: (_ for _ in ()).throw(OSError("fail")))
        v2 = analyzer.get_current_multiplier()
        # OSError caught internally — multiplier stays at base
        assert v2 == 1.0


class TestMarketAnalyzerBoundaries:
    """Tests for MarketAnalyzer boundary conditions."""

    def test_negative_load_handled_gracefully(self, monkeypatch):
        """Extremely high load should not produce absurd multipliers."""
        analyzer = MarketAnalyzer()
        analyzer._last_update = 0.0
        monkeypatch.setattr("os.getloadavg", lambda: (100.0, 80.0, 50.0))
        multiplier = analyzer.get_current_multiplier()
        # (100 - 2) * 0.2 = 19.6, base = 1.0 + 19.6 = 20.6
        assert multiplier == 20.6

    def test_load_at_threshold_exact(self, monkeypatch):
        """Load exactly at 2.0 threshold should not add impact."""
        analyzer = MarketAnalyzer()
        analyzer._last_update = 0.0
        monkeypatch.setattr("os.getloadavg", lambda: (2.0, 1.5, 1.0))
        multiplier = analyzer.get_current_multiplier()
        # load exactly 2.0 → no load impact
        assert multiplier == 1.0
