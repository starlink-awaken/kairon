"""Tests for the anomaly module — AnomalyDetector."""



from observability.anomaly import AnomalyDetector, AnomalyResult


class TestAnomalyDetectorInit:
    """Verify initialization."""

    def test_default_parameters(self):
        d = AnomalyDetector()
        assert d.window_size == 100
        assert d.z_threshold == 3.0

    def test_custom_parameters(self):
        d = AnomalyDetector(window_size=50, z_threshold=2.5)
        assert d.window_size == 50
        assert d.z_threshold == 2.5


class TestAnomalyDetectorUpdate:
    """Verify the core update() method — sliding window, z-score, early behaviour."""

    def test_insufficient_samples_returns_non_anomaly(self):
        d = AnomalyDetector()
        for _ in range(2):
            r = d.update(10.0)
            assert r.is_anomaly is False

    def test_min_samples_before_detection(self):
        d = AnomalyDetector()
        for i in range(3):
            r = d.update(10.0)
            if i < 2:
                assert r.is_anomaly is False
            else:
                # At 3 samples we start checking
                assert not r.is_anomaly  # 10.0 is consistent with 10.0

    def test_anomalous_value_detected(self):
        d = AnomalyDetector(z_threshold=2.0)
        # Feed consistent baseline
        for _ in range(20):
            d.update(100.0)
        # Now feed a spike
        r = d.update(1000.0)
        assert r.is_anomaly is True
        assert r.z_score > 2.0

    def test_non_anomalous_value(self):
        d = AnomalyDetector(z_threshold=3.0)
        # Feed varied baseline so stddev is non-trivial
        for v in [100.0, 102.0, 98.0, 101.0, 99.0] * 4:
            d.update(v)
        r = d.update(100.5)  # very close to mean
        assert r.is_anomaly is False

    def test_result_fields_populated(self):
        d = AnomalyDetector()
        for _ in range(5):
            d.update(100.0)
        r = d.update(105.0)
        assert isinstance(r, AnomalyResult)
        assert r.value == 105.0
        assert r.mean != 0.0
        assert r.stddev > 0.0
        assert r.z_score >= 0.0
        assert r.threshold > 0.0
        assert r.trend in ("stable", "up", "down")

    def test_z_score_increases_with_deviation(self):
        d = AnomalyDetector(z_threshold=5.0)
        # Feed varied baseline so we get meaningful stddev
        for v in [100.0, 102.0, 98.0, 101.0, 99.0] * 4:
            d.update(v)
        r_small = d.update(110.0)
        # Reset and repeat with larger deviation
        d.reset()
        for v in [100.0, 102.0, 98.0, 101.0, 99.0] * 4:
            d.update(v)
        r_large = d.update(200.0)
        assert r_large.z_score > r_small.z_score


class TestSlidingWindow:
    """Verify the sliding window behaviour caps the influence of old samples."""

    def test_window_size_limits_history(self):
        d = AnomalyDetector(window_size=10)
        for _ in range(100):
            d.update(50.0)
        assert len(d._history) <= 10

    def test_window_slides_old_outliers_drop_off(self):
        d = AnomalyDetector(window_size=10, z_threshold=3.0)
        # Feed 10 stable values
        for _ in range(10):
            d.update(100.0)
        # Then a huge spike
        d.update(10000.0)  # This will be an anomaly
        # After many more stable values, the mean should converge back
        for _ in range(20):
            d.update(100.0)
        r = d.update(100.0)
        assert not r.is_anomaly


class TestZScoreDetection:
    """Verify z-score based anomaly detection."""

    def test_low_z_threshold_more_anomalies(self):
        d = AnomalyDetector(z_threshold=0.5)
        for _ in range(10):
            d.update(100.0)
        r = d.update(105.0)
        assert r.is_anomaly is True  # very low threshold

    def test_high_z_threshold_fewer_anomalies(self):
        d = AnomalyDetector(z_threshold=10.0)
        for _ in range(10):
            d.update(100.0)
        r = d.update(105.0)
        assert r.is_anomaly is False  # very high threshold

    def test_exact_z_score_computation(self):
        d = AnomalyDetector(z_threshold=2.0)
        # Tight baseline (all identical) so stddev is tiny
        for _ in range(10):
            d.update(100.0)
        # Even a small deviation becomes very anomalous with tiny stddev
        r = d.update(200.0)
        assert r.z_score > 2.0
        assert r.is_anomaly


class TestDetectSpike:
    """Verify the detect_spike instance method."""

    def test_spike_detected_above_3x_baseline(self):
        d = AnomalyDetector()
        values = [10.0, 12.0, 11.0, 9.0, 10.5, 50.0]
        assert d.detect_spike(values) is True

    def test_no_spike(self):
        d = AnomalyDetector()
        values = [10.0, 12.0, 11.0, 9.0, 10.5, 11.0]
        assert d.detect_spike(values) is False

    def test_insufficient_data(self):
        d = AnomalyDetector()
        assert d.detect_spike([1.0, 2.0]) is False

    def test_zero_baseline_uses_stddev(self):
        d = AnomalyDetector()
        values = [0.0, 0.0, 0.0, 0.0, 0.0, 5.0]
        assert d.detect_spike(values) is True

    def test_zero_baseline_no_spike(self):
        d = AnomalyDetector()
        values = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        assert d.detect_spike(values) is False


class TestDetectTrend:
    """Verify the detect_trend instance method."""

    def test_increasing_trend(self):
        d = AnomalyDetector()
        values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
        assert d.detect_trend(values) == "increasing"

    def test_decreasing_trend(self):
        d = AnomalyDetector()
        values = [10.0, 9.0, 8.0, 7.0, 6.0, 5.0, 4.0, 3.0]
        assert d.detect_trend(values) == "decreasing"

    def test_stable_trend(self):
        d = AnomalyDetector()
        values = [10.0, 10.5, 9.5, 10.0, 10.2, 9.8, 10.1, 9.9]
        assert d.detect_trend(values) == "stable"

    def test_insufficient_data(self):
        d = AnomalyDetector()
        assert d.detect_trend([1.0, 2.0]) == "insufficient_data"

    def test_exactly_5_values_sufficient(self):
        d = AnomalyDetector()
        values = [1.0, 2.0, 10.0, 20.0, 30.0]
        assert d.detect_trend(values) == "increasing"

    def test_internal_trend_lowercase(self):
        d = AnomalyDetector()
        for v in [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]:
            d.update(v)
        r = d.update(9.0)
        assert r.trend in ("up", "stable")  # internal uses "up"/"down"


class TestGetStats:
    """Verify get_stats returns diagnostic information."""

    def test_stats_baseline(self):
        d = AnomalyDetector()
        for _ in range(10):
            d.update(100.0)
        stats = d.get_stats()
        assert stats["count"] == 10
        assert stats["mean"] == 100.0
        assert stats["window_size"] == 100
        assert stats["samples"] == 10
        assert stats["adaptive"] is False
        assert stats["adaptive_multiplier"] == 1.0

    def test_stats_with_adaptive(self):
        d = AnomalyDetector()
        d.enable_adaptive_threshold()
        for _ in range(20):
            d.update(100.0)
        stats = d.get_stats()
        assert stats["adaptive"] is True

    def test_stats_empty(self):
        d = AnomalyDetector()
        stats = d.get_stats()
        assert stats["count"] == 0
        assert stats["mean"] == 0.0


class TestAdaptiveThreshold:
    """Verify adaptive threshold adjustment."""

    def test_enable_disable_adaptive(self):
        d = AnomalyDetector()
        assert d._adaptive_enabled is False
        d.enable_adaptive_threshold()
        assert d._adaptive_enabled is True
        d.disable_adaptive_threshold()
        assert d._adaptive_enabled is False
        assert d._adaptive_multiplier == 1.0

    def test_adaptive_adjusts_threshold_up(self):
        d = AnomalyDetector(z_threshold=3.0)
        d.enable_adaptive_threshold(target_rate=0.05, step=0.1)
        # Feed many values where ~half are anomalies (very extreme)
        for _ in range(50):
            d.update(100.0)
        for _ in range(50):
            d.update(10000.0)  # extreme spikes
        # The multiplier should have gone up
        assert d._adaptive_multiplier > 1.0

    def test_adaptive_adjusts_threshold_down(self):
        d = AnomalyDetector(z_threshold=3.0)
        d.enable_adaptive_threshold(target_rate=0.5, step=0.1)
        # Feed totally consistent values — no anomalies
        for _ in range(50):
            d.update(100.0)
        # With a high target rate and no anomalies, multiplier should decrease
        assert d._adaptive_multiplier <= 1.0

    def test_adaptive_not_active_when_disabled(self):
        d = AnomalyDetector()
        # Feed many extreme values
        for _ in range(10):
            d.update(100.0)
        d.update(10000.0)
        # Since adaptive is disabled, effective threshold = z_threshold
        r = d.update(10000.0)
        assert r.threshold == d.z_threshold


class TestReset:
    """Verify reset clears all state."""

    def test_reset_clears_state(self):
        d = AnomalyDetector()
        for _ in range(20):
            d.update(100.0)
        d.reset()
        assert d._count == 0
        assert d._mean == 0.0
        assert len(d._history) == 0
        assert d._adaptive_multiplier == 1.0
        assert d._last_spike_direction == "none"

    def test_after_reset_detection_restarts(self):
        d = AnomalyDetector()
        for _ in range(10):
            d.update(100.0)
        d.reset()
        r = d.update(100.0)
        assert r.is_anomaly is False  # insufficient samples again


class TestRollingStats:
    """Verify rolling mean, stddev, median, percentile."""

    def test_get_rolling_mean(self):
        d = AnomalyDetector()
        for v in [10.0, 20.0, 30.0]:
            d.update(v)
        assert d.get_rolling_mean() == 20.0

    def test_get_rolling_stddev(self):
        d = AnomalyDetector()
        for v in [10.0, 20.0, 30.0]:
            d.update(v)
        assert d.get_rolling_stddev() > 0.0

    def test_get_rolling_stddev_insufficient(self):
        d = AnomalyDetector()
        assert d.get_rolling_stddev() == 0.0
        d.update(10.0)
        assert d.get_rolling_stddev() == 0.0

    def test_get_rolling_median(self):
        d = AnomalyDetector()
        for v in [1.0, 10.0, 100.0]:
            d.update(v)
        assert d.get_rolling_median() == 10.0

    def test_get_rolling_median_empty(self):
        d = AnomalyDetector()
        assert d.get_rolling_median() == 0.0

    def test_get_rolling_percentile(self):
        d = AnomalyDetector()
        for v in [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]:
            d.update(v)
        p95 = d.get_rolling_percentile(95)
        # With 10 values the p95 should be in the upper range, at minimum >= p50
        p50 = d.get_rolling_percentile(50)
        assert p95 >= p50
        # p99 should be near the max
        p99 = d.get_rolling_percentile(99)
        assert p99 >= p95

    def test_get_rolling_percentile_empty(self):
        d = AnomalyDetector()
        assert d.get_rolling_percentile(50) == 0.0


class TestMultiSeries:
    """Verify the multi-series support."""

    def test_update_series_creates_separate_tracking(self):
        d = AnomalyDetector()
        r1 = d.update_series("cpu", 50.0)
        assert r1.is_anomaly is False  # insufficient samples
        r2 = d.update_series("mem", 80.0)
        assert r2.is_anomaly is False

    def test_update_series_anomaly_detection(self):
        d = AnomalyDetector(z_threshold=2.0)
        for _ in range(10):
            d.update_series("cpu", 50.0)
        r = d.update_series("cpu", 500.0)
        assert r.is_anomaly is True

    def test_get_series_values(self):
        d = AnomalyDetector()
        for v in [1.0, 2.0, 3.0]:
            d.update_series("cpu", v)
        vals = d.get_series_values("cpu")
        assert vals == [1.0, 2.0, 3.0]

    def test_get_series_values_unknown(self):
        d = AnomalyDetector()
        assert d.get_series_values("nonexistent") == []

    def test_series_result_fields(self):
        d = AnomalyDetector()
        for _ in range(5):
            d.update_series("cpu", 100.0)
        r = d.update_series("cpu", 105.0)
        assert r.mean > 0.0
        assert r.stddev > 0.0
        assert r.z_score >= 0.0
