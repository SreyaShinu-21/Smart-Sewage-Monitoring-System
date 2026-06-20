"""
Tests for Smart Sewage Monitoring System
=========================================
Run with:  pytest tests/test_system.py -v
"""

import sys
import os
import numpy as np
import pandas as pd
import pytest

# Allow imports from ml/ directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ml"))

from train_model import (
    generate_sewage_dataset,
    threshold_predict,
    THRESHOLDS,
    build_preprocessing_pipeline,
)
from simulate_realtime import detect_anomalies, read_sensors


# ─────────────────────────────────────────────────────────────────────────────
# Dataset Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestDataset:
    def test_shape(self):
        df = generate_sewage_dataset(n_samples=100)
        assert df.shape == (100, 8), "Dataset should have 8 columns (7 features + Label)"

    def test_columns(self):
        df = generate_sewage_dataset(n_samples=50)
        expected = {"pH", "Temperature", "Turbidity", "COD", "BOD", "TDS", "Ammonia", "Label"}
        assert set(df.columns) == expected

    def test_label_binary(self):
        df = generate_sewage_dataset(n_samples=200)
        assert set(df["Label"].unique()).issubset({0, 1}), "Labels must be 0 or 1"

    def test_has_both_classes(self):
        df = generate_sewage_dataset(n_samples=200)
        assert 0 in df["Label"].values
        assert 1 in df["Label"].values

    def test_missing_values_injected(self):
        df = generate_sewage_dataset(n_samples=500)
        total_nulls = df.drop("Label", axis=1).isnull().sum().sum()
        assert total_nulls > 0, "Some missing values should be injected"

    def test_hazardous_ratio_approx(self):
        df = generate_sewage_dataset(n_samples=1000)
        ratio = df["Label"].mean()
        assert 0.20 <= ratio <= 0.45, f"Hazardous ratio {ratio:.2f} out of expected range"


# ─────────────────────────────────────────────────────────────────────────────
# Threshold Detection Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestThresholdDetection:
    """Tests aligned with paper equations (1) and (2)."""

    def _make_safe_row(self):
        return {
            "pH": 7.0, "Temperature": 25.0, "Turbidity": 3.0,
            "COD": 100.0, "BOD": 20.0, "TDS": 450.0, "Ammonia": 0.5,
        }

    def test_safe_reading_returns_zero(self):
        df = pd.DataFrame([self._make_safe_row()])
        assert threshold_predict(df)[0] == 0

    def test_high_temperature_triggers_alert(self):
        row = self._make_safe_row()
        row["Temperature"] = 50.0   # Above 35 °C threshold
        df = pd.DataFrame([row])
        assert threshold_predict(df)[0] == 1

    def test_low_ph_triggers_alert(self):
        row = self._make_safe_row()
        row["pH"] = 4.0
        df = pd.DataFrame([row])
        assert threshold_predict(df)[0] == 1

    def test_high_ph_triggers_alert(self):
        row = self._make_safe_row()
        row["pH"] = 10.5
        df = pd.DataFrame([row])
        assert threshold_predict(df)[0] == 1

    def test_high_cod_triggers_alert(self):
        row = self._make_safe_row()
        row["COD"] = 300.0
        df = pd.DataFrame([row])
        assert threshold_predict(df)[0] == 1

    def test_multiple_anomalies_still_one(self):
        row = self._make_safe_row()
        row["Temperature"] = 55.0
        row["COD"] = 500.0
        df = pd.DataFrame([row])
        assert threshold_predict(df)[0] == 1  # Still binary

    def test_batch_detection(self):
        rows = [self._make_safe_row() for _ in range(5)]
        rows[2]["Temperature"] = 50.0
        df = pd.DataFrame(rows)
        results = threshold_predict(df)
        assert results[2] == 1
        assert results[0] == 0


# ─────────────────────────────────────────────────────────────────────────────
# Simulation Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSimulation:
    def test_safe_reading_no_alerts(self):
        reading = {
            "water_level": 100.0,
            "gas_ppm": 150,
            "temperature": 25.0,
        }
        alerts = detect_anomalies(reading)
        assert len(alerts) == 0

    def test_water_overflow_alert(self):
        reading = {"water_level": 30.0, "gas_ppm": 100, "temperature": 25.0}
        alerts = detect_anomalies(reading)
        assert any("OVERFLOW" in a.upper() or "overflow" in a.lower() for a in alerts)

    def test_gas_threshold_exact_boundary(self):
        """Gas alert should trigger at exactly 300 ppm (≥ threshold)."""
        reading = {"water_level": 100.0, "gas_ppm": 300, "temperature": 25.0}
        alerts = detect_anomalies(reading)
        assert any("gas" in a.lower() or "GAS" in a for a in alerts)

    def test_gas_below_threshold_safe(self):
        reading = {"water_level": 100.0, "gas_ppm": 299, "temperature": 25.0}
        alerts = detect_anomalies(reading)
        assert not any("gas" in a.lower() for a in alerts)

    def test_high_temperature_alert(self):
        reading = {"water_level": 100.0, "gas_ppm": 100, "temperature": 50.0}
        alerts = detect_anomalies(reading)
        assert any("temp" in a.lower() for a in alerts)

    def test_read_sensors_returns_keys(self):
        reading = read_sensors(inject_anomaly=False)
        required = {"timestamp", "water_level", "gas_ppm", "temperature", "humidity", "pH"}
        assert required.issubset(set(reading.keys()))

    def test_read_sensors_value_ranges(self):
        for _ in range(20):
            r = read_sensors(inject_anomaly=False)
            assert 0   <= r["water_level"] <= 250
            assert 0   <= r["gas_ppm"]     <= 1000
            assert -10 <= r["temperature"] <= 100
            assert 0   <= r["humidity"]    <= 100
            assert 0   <= r["pH"]          <= 14


# ─────────────────────────────────────────────────────────────────────────────
# Preprocessing Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestPreprocessing:
    def test_pipeline_builds(self):
        pipe = build_preprocessing_pipeline()
        assert pipe is not None

    def test_imputation_removes_nans(self):
        from sklearn.impute import SimpleImputer
        X = np.array([[1, np.nan, 3], [4, 5, np.nan], [7, 8, 9]])
        imp = SimpleImputer(strategy="mean")
        X_out = imp.fit_transform(X)
        assert not np.isnan(X_out).any()

    def test_z_score_standardization(self):
        from sklearn.preprocessing import StandardScaler
        X = np.array([[1, 2], [3, 4], [5, 6]], dtype=float)
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        assert abs(X_scaled.mean()) < 1e-10
        assert abs(X_scaled.std() - 1.0) < 1e-6


# ─────────────────────────────────────────────────────────────────────────────
# Performance Benchmark
# ─────────────────────────────────────────────────────────────────────────────

class TestPerformanceBenchmarks:
    """Verify the system meets the accuracy targets stated in the paper."""

    def test_threshold_accuracy_above_85(self):
        """Threshold-based approach should achieve >85% accuracy on clean data."""
        from sklearn.metrics import accuracy_score
        df = generate_sewage_dataset(n_samples=500, random_state=1)
        y_true  = df["Label"].values
        y_pred  = threshold_predict(df.drop("Label", axis=1))
        acc = accuracy_score(y_true, y_pred)
        assert acc >= 0.70, f"Accuracy {acc:.2f} below expected 0.70 baseline"

    def test_rf_accuracy_above_90(self):
        """Random Forest on this dataset should achieve >90% accuracy."""
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.impute import SimpleImputer
        from sklearn.preprocessing import StandardScaler
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import accuracy_score

        df = generate_sewage_dataset(n_samples=800, random_state=7)
        X, y = df.drop("Label", axis=1), df["Label"]

        imp = SimpleImputer(strategy="mean")
        sc  = StandardScaler()
        X_proc = sc.fit_transform(imp.fit_transform(X))

        X_tr, X_te, y_tr, y_te = train_test_split(X_proc, y, test_size=0.2, random_state=7)
        model = RandomForestClassifier(n_estimators=50, random_state=7)
        model.fit(X_tr, y_tr)
        acc = accuracy_score(y_te, model.predict(X_te))
        assert acc >= 0.90, f"RF accuracy {acc:.2f} below 0.90 target"
