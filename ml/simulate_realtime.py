"""
Smart Sewage Monitoring System — Real-Time Simulation
======================================================
Simulates live sensor readings and applies threshold-based
anomaly detection, mirroring the embedded firmware logic in Python.

Run this to demo the system without hardware.

Usage:
    python simulate_realtime.py
    python simulate_realtime.py --samples 50 --interval 1.0
"""

import time
import argparse
import random
import sys
from datetime import datetime

# ─── Thresholds (mirrors firmware constants) ──────────────────────────────────
WATER_LEVEL_THRESHOLD_CM = 50.0   # Overflow if distance ≤ 50 cm
GAS_THRESHOLD_PPM        = 300    # Gas alert if ≥ 300 ppm
TEMP_THRESHOLD_C         = 45.0   # High temp alert


# ─── ANSI colour helpers ──────────────────────────────────────────────────────
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
RESET  = "\033[0m"
BOLD   = "\033[1m"


def colour(text: str, code: str) -> str:
    return f"{code}{text}{RESET}"


# ─── Simulated Sensor Reading ─────────────────────────────────────────────────

def read_sensors(inject_anomaly: bool = False) -> dict:
    """
    Return a dict of simulated sensor readings.
    If inject_anomaly=True, randomly force an anomalous value.
    """
    if inject_anomaly and random.random() < 0.3:
        # Force one parameter into hazardous range
        anomaly_type = random.choice(["water", "gas", "temp"])
        water = random.uniform(5, 48) if anomaly_type == "water" else random.uniform(55, 200)
        gas   = random.randint(320, 700) if anomaly_type == "gas"   else random.randint(50, 250)
        temp  = random.uniform(46, 60)   if anomaly_type == "temp"  else random.uniform(20, 35)
    else:
        water = random.uniform(55, 200)    # Safe: far from sensor = low water
        gas   = random.randint(50, 280)    # Safe: below threshold
        temp  = random.uniform(20, 38)     # Safe range

    return {
        "timestamp":    datetime.now().strftime("%H:%M:%S"),
        "water_level":  round(water, 1),
        "gas_ppm":      gas,
        "temperature":  round(temp, 1),
        "humidity":     round(random.uniform(40, 90), 1),
        "pH":           round(random.uniform(6.5, 8.5), 2),
    }


# ─── Threshold Detection ──────────────────────────────────────────────────────

def detect_anomalies(reading: dict) -> list[str]:
    """Return list of alert messages for any threshold breach."""
    alerts = []
    if 0 < reading["water_level"] <= WATER_LEVEL_THRESHOLD_CM:
        alerts.append(
            f"OVERFLOW RISK — Water level {reading['water_level']} cm "
            f"(threshold ≤ {WATER_LEVEL_THRESHOLD_CM} cm)"
        )
    if reading["gas_ppm"] >= GAS_THRESHOLD_PPM:
        alerts.append(
            f"GAS HAZARD — Concentration {reading['gas_ppm']} ppm "
            f"(threshold ≥ {GAS_THRESHOLD_PPM} ppm)"
        )
    if reading["temperature"] >= TEMP_THRESHOLD_C:
        alerts.append(
            f"HIGH TEMP — {reading['temperature']}°C "
            f"(threshold ≥ {TEMP_THRESHOLD_C}°C)"
        )
    return alerts


# ─── Display Helpers ──────────────────────────────────────────────────────────

def print_header():
    print("\n" + "═"*60)
    print(colour("  Smart Sewage Monitoring System — Live Simulation", BOLD))
    print("═"*60)
    print(f"  {'Time':<10} {'Water(cm)':<12} {'Gas(ppm)':<11} "
          f"{'Temp(°C)':<10} {'Status'}")
    print("─"*60)


def print_reading(reading: dict, alerts: list[str]):
    status = colour("✓ SAFE", GREEN) if not alerts else colour("⚠ ANOMALY", RED)
    print(f"  {reading['timestamp']:<10} "
          f"{reading['water_level']:<12} "
          f"{reading['gas_ppm']:<11} "
          f"{reading['temperature']:<10} "
          f"{status}")
    for alert in alerts:
        print(colour(f"    ▶ {alert}", RED))


def print_summary(total: int, anomaly_count: int):
    rate = anomaly_count / total * 100 if total > 0 else 0
    print("\n" + "═"*60)
    print(colour("  Session Summary", BOLD))
    print("─"*60)
    print(f"  Total readings : {total}")
    print(f"  Anomalies      : {anomaly_count} ({rate:.1f}%)")
    print(f"  Safe readings  : {total - anomaly_count} ({100-rate:.1f}%)")
    print("═"*60 + "\n")


# ─── Main Loop ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Simulate Smart Sewage Monitoring System sensor readings")
    parser.add_argument("--samples",  type=int,   default=20,  help="Number of readings")
    parser.add_argument("--interval", type=float, default=0.8, help="Seconds between readings")
    parser.add_argument("--no-anomaly", action="store_true",   help="Disable random anomalies")
    args = parser.parse_args()

    inject = not args.no_anomaly
    anomaly_count = 0

    print_header()
    try:
        for i in range(args.samples):
            reading = read_sensors(inject_anomaly=inject)
            alerts  = detect_anomalies(reading)
            if alerts:
                anomaly_count += 1
            print_reading(reading, alerts)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print(colour("\n  Interrupted by user.", YELLOW))

    print_summary(args.samples, anomaly_count)


if __name__ == "__main__":
    main()
