"""
Car Tuner — ECU diagnostic, backup, tune & restore tool.
Connects via OBD-II adapter (ELM327 USB/Bluetooth/WiFi).
"""

import obd
import json
import os
import sys
import time
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backups")
TUNES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tunes")
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tuner_log.jsonl")

os.makedirs(BACKUP_DIR, exist_ok=True)
os.makedirs(TUNES_DIR, exist_ok=True)


# ── Connection ──────────────────────────────────────────────

def connect_to_car(port=None):
    """Connect to car via OBD-II. Auto-detects port if not specified."""
    print("[*] Scanning for OBD-II adapter...")
    if port:
        conn = obd.OBD(port)
    else:
        conn = obd.OBD()  # auto-detect

    if conn.is_connected():
        print(f"[+] Connected via: {conn.port_name()}")
        print(f"[+] Protocol: {conn.protocol_name()}")
        return conn
    else:
        print("[!] Could not connect. Check adapter and ignition.")
        print("    - Make sure ELM327 adapter is plugged in")
        print("    - Turn ignition to ON (engine can be off)")
        print("    - Try specifying port: python car_tuner.py --port COM3")
        return None


# ── ECU Detection ───────────────────────────────────────────

def detect_ecu(conn):
    """Read ECU info: VIN, ECU name, calibration ID, voltage, etc."""
    ecu_info = {}

    queries = {
        "VIN": obd.commands.VIN if hasattr(obd.commands, "VIN") else None,
        "ECU_NAME": obd.commands.ECU_NAME if hasattr(obd.commands, "ECU_NAME") else None,
        "CALIBRATION_ID": obd.commands.CALIBRATION_ID if hasattr(obd.commands, "CALIBRATION_ID") else None,
        "CVN": obd.commands.CVN if hasattr(obd.commands, "CVN") else None,
        "ELM_VERSION": obd.commands.ELM_VERSION,
        "ELM_VOLTAGE": obd.commands.ELM_VOLTAGE,
    }

    for name, cmd in queries.items():
        if cmd is None:
            continue
        try:
            resp = conn.query(cmd)
            if not resp.is_null():
                ecu_info[name] = str(resp.value)
        except Exception as e:
            ecu_info[name] = f"error: {e}"

    return ecu_info


# ── Read Current Tune (Live Data Snapshot) ──────────────────

def read_current_tune(conn):
    """
    Read all available PIDs — this captures the current state of the ECU.
    Includes fuel trims, timing, boost, AFR, sensor data, etc.
    """
    tune_data = {}
    supported = conn.supported_commands

    print(f"[*] Reading {len(supported)} supported parameters...")

    for cmd in supported:
        try:
            resp = conn.query(cmd)
            if not resp.is_null():
                val = resp.value
                tune_data[cmd.name] = {
                    "value": str(val),
                    "unit": str(val.units) if hasattr(val, "units") else None,
                    "command": cmd.name,
                    "desc": cmd.desc,
                }
        except Exception:
            pass

    # Key tuning parameters to highlight
    key_params = [
        "FUEL_STATUS", "SHORT_FUEL_TRIM_1", "LONG_FUEL_TRIM_1",
        "SHORT_FUEL_TRIM_2", "LONG_FUEL_TRIM_2",
        "TIMING_ADVANCE", "INTAKE_PRESSURE", "MAF",
        "COMMANDED_EQUIV_RATIO", "FUEL_RAIL_PRESSURE_DIRECT",
        "BOOST_PRESSURE", "ENGINE_LOAD", "COOLANT_TEMP",
        "INTAKE_TEMP", "RPM", "SPEED",
    ]

    print("\n── Key Tuning Parameters ──")
    for param in key_params:
        if param in tune_data:
            d = tune_data[param]
            unit = f" {d['unit']}" if d["unit"] else ""
            print(f"  {param}: {d['value']}{unit}")

    return tune_data


# ── Read DTCs (Trouble Codes) ──────────────────────────────

def read_dtcs(conn):
    """Read diagnostic trouble codes — important before tuning."""
    dtcs = []
    try:
        resp = conn.query(obd.commands.GET_DTC)
        if not resp.is_null():
            dtcs = [(code, desc) for code, desc in resp.value]
    except Exception:
        pass

    if dtcs:
        print(f"\n[!] WARNING: {len(dtcs)} trouble code(s) found:")
        for code, desc in dtcs:
            print(f"    {code}: {desc}")
        print("    Fix these before tuning!")
    else:
        print("\n[+] No trouble codes — car is healthy")

    return dtcs


# ── Read Freeze Frame Data ─────────────────────────────────

def read_freeze_frame(conn):
    """Read freeze frame data (snapshot at time of last DTC)."""
    freeze = {}
    try:
        resp = conn.query(obd.commands.FREEZE_DTC)
        if not resp.is_null():
            freeze["FREEZE_DTC"] = str(resp.value)
    except Exception:
        pass
    return freeze


# ── Backup ──────────────────────────────────────────────────

def backup_tune(ecu_info, tune_data, dtcs):
    """Save full ECU state to a backup file."""
    vin = ecu_info.get("VIN", "UNKNOWN")
    safe_vin = "".join(c if c.isalnum() else "_" for c in vin)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"backup_{safe_vin}_{timestamp}.json"
    filepath = os.path.join(BACKUP_DIR, filename)

    backup = {
        "timestamp": datetime.now().isoformat(),
        "ecu_info": ecu_info,
        "tune_data": tune_data,
        "dtcs": [(c, d) for c, d in dtcs],
        "notes": "Original tune backup — DO NOT DELETE",
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(backup, f, indent=2, ensure_ascii=False)

    print(f"\n[+] Backup saved: {filepath}")
    log_event("backup_created", {"file": filename, "vin": vin})
    return filepath


# ── List Backups ────────────────────────────────────────────

def list_backups():
    """List all saved tune backups."""
    files = sorted(os.listdir(BACKUP_DIR))
    if not files:
        print("[*] No backups found.")
        return []

    print("\n── Saved Backups ──")
    for i, f in enumerate(files, 1):
        filepath = os.path.join(BACKUP_DIR, f)
        size_kb = os.path.getsize(filepath) / 1024
        print(f"  {i}. {f} ({size_kb:.1f} KB)")
    return files


# ── Tuning Recommendations ─────────────────────────────────

def analyze_tune(ecu_info, tune_data):
    """Analyze current tune and suggest improvements."""
    recommendations = []

    print("\n── Tuning Analysis ──")

    # Check fuel trims
    for trim in ["SHORT_FUEL_TRIM_1", "LONG_FUEL_TRIM_1",
                  "SHORT_FUEL_TRIM_2", "LONG_FUEL_TRIM_2"]:
        if trim in tune_data:
            val_str = tune_data[trim]["value"]
            try:
                val = float(val_str.split()[0])
                if abs(val) > 10:
                    recommendations.append({
                        "param": trim,
                        "issue": f"Fuel trim is {val}% — too far from 0%",
                        "action": "Check for vacuum leaks, MAF sensor, or injector issues before tuning",
                        "severity": "high",
                    })
                elif abs(val) > 5:
                    recommendations.append({
                        "param": trim,
                        "issue": f"Fuel trim is {val}% — slightly off",
                        "action": "Minor correction may be needed",
                        "severity": "medium",
                    })
            except (ValueError, IndexError):
                pass

    # Check timing
    if "TIMING_ADVANCE" in tune_data:
        val_str = tune_data["TIMING_ADVANCE"]["value"]
        try:
            timing = float(val_str.split()[0])
            if timing < 5:
                recommendations.append({
                    "param": "TIMING_ADVANCE",
                    "issue": f"Timing advance is low ({timing} deg)",
                    "action": "ECU may be pulling timing — check for knock or low octane fuel",
                    "severity": "medium",
                })
        except (ValueError, IndexError):
            pass

    # Check engine load
    if "ENGINE_LOAD" in tune_data:
        val_str = tune_data["ENGINE_LOAD"]["value"]
        try:
            load = float(val_str.split()[0])
            if load > 80:
                recommendations.append({
                    "param": "ENGINE_LOAD",
                    "issue": f"Engine load is high ({load}%)",
                    "action": "Check air filter, exhaust restrictions",
                    "severity": "medium",
                })
        except (ValueError, IndexError):
            pass

    # Check intake temp
    if "INTAKE_TEMP" in tune_data:
        val_str = tune_data["INTAKE_TEMP"]["value"]
        try:
            temp = float(val_str.split()[0])
            if temp > 50:
                recommendations.append({
                    "param": "INTAKE_TEMP",
                    "issue": f"Intake air temp is high ({temp} C)",
                    "action": "Consider cold air intake or heat shielding before tuning for more power",
                    "severity": "low",
                })
        except (ValueError, IndexError):
            pass

    # ECU type-based suggestions
    ecu_name = ecu_info.get("ECU_NAME", "").upper()
    cal_id = ecu_info.get("CALIBRATION_ID", "").upper()

    if any(x in ecu_name for x in ["BOSCH", "SIEMENS", "CONTINENTAL", "DENSO", "DELPHI"]):
        recommendations.append({
            "param": "ECU_TYPE",
            "issue": f"ECU identified as {ecu_name}",
            "action": f"This ECU type is commonly tunable. Look for {ecu_name}-specific tuning tools.",
            "severity": "info",
        })

    if not recommendations:
        print("  [+] Everything looks good! Car is in a healthy state for tuning.")
    else:
        for r in recommendations:
            icon = {"high": "!!!", "medium": "!!", "low": "!", "info": "i"}.get(r["severity"], "?")
            print(f"  [{icon}] {r['param']}: {r['issue']}")
            print(f"       -> {r['action']}")

    return recommendations


# ── Save Tune Profile ──────────────────────────────────────

def save_tune_profile(name, tune_data, recommendations, ecu_info):
    """Save a named tune profile for later comparison or restore."""
    filepath = os.path.join(TUNES_DIR, f"{name}.json")
    profile = {
        "name": name,
        "timestamp": datetime.now().isoformat(),
        "ecu_info": ecu_info,
        "tune_data": tune_data,
        "recommendations": recommendations,
    }
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2, ensure_ascii=False)
    print(f"[+] Tune profile saved: {filepath}")
    return filepath


# ── Compare Tunes ───────────────────────────────────────────

def compare_tunes(file1, file2):
    """Compare two tune files side by side."""
    with open(file1, "r") as f:
        tune1 = json.load(f)
    with open(file2, "r") as f:
        tune2 = json.load(f)

    data1 = tune1.get("tune_data", {})
    data2 = tune2.get("tune_data", {})

    all_params = sorted(set(list(data1.keys()) + list(data2.keys())))

    print(f"\n── Tune Comparison ──")
    print(f"  File 1: {os.path.basename(file1)}")
    print(f"  File 2: {os.path.basename(file2)}")
    print()

    diffs = 0
    for param in all_params:
        v1 = data1.get(param, {}).get("value", "N/A")
        v2 = data2.get(param, {}).get("value", "N/A")
        if v1 != v2:
            diffs += 1
            print(f"  {param}:")
            print(f"    Before: {v1}")
            print(f"    After:  {v2}")

    if diffs == 0:
        print("  No differences found.")
    else:
        print(f"\n  Total differences: {diffs}")


# ── Live Monitor ────────────────────────────────────────────

def live_monitor(conn, params=None, interval=1.0):
    """
    Live-monitor key parameters in real time.
    Press Ctrl+C to stop.
    """
    if params is None:
        params = ["RPM", "SPEED", "ENGINE_LOAD", "COOLANT_TEMP",
                  "INTAKE_TEMP", "SHORT_FUEL_TRIM_1", "TIMING_ADVANCE"]

    print("\n── Live Monitor (Ctrl+C to stop) ──\n")

    try:
        while True:
            line_parts = []
            for param_name in params:
                cmd = getattr(obd.commands, param_name, None)
                if cmd is None:
                    continue
                try:
                    resp = conn.query(cmd)
                    if not resp.is_null():
                        line_parts.append(f"{param_name}={resp.value}")
                except Exception:
                    pass

            print("  " + " | ".join(line_parts), end="\r")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n[*] Monitor stopped.")


# ── Logging ─────────────────────────────────────────────────

def log_event(event_type, data):
    """Append event to log file."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "event": event_type,
        "data": data,
    }
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ── Main Menu ───────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Car Tuner — ECU diagnostic & tuning tool")
    parser.add_argument("--port", help="OBD-II adapter port (e.g. COM3, /dev/ttyUSB0)")
    parser.add_argument("--demo", action="store_true", help="Run in demo mode without a real connection")
    args = parser.parse_args()

    print("=" * 50)
    print("  CAR TUNER — ECU Diagnostic & Tuning Tool")
    print("=" * 50)

    if args.demo:
        print("\n[*] Running in DEMO mode (no real car connection)")
        run_demo()
        return

    conn = connect_to_car(args.port)
    if not conn:
        return

    while True:
        print("\n── Menu ──")
        print("  1. Detect ECU & car info")
        print("  2. Read current tune (full scan)")
        print("  3. Check trouble codes (DTCs)")
        print("  4. Backup current tune")
        print("  5. Analyze & get tuning recommendations")
        print("  6. Live monitor")
        print("  7. List saved backups")
        print("  8. Compare two tunes")
        print("  9. Full scan (detect + read + backup + analyze)")
        print("  0. Exit")

        choice = input("\n  Choose [0-9]: ").strip()

        if choice == "1":
            ecu_info = detect_ecu(conn)
            print("\n── ECU Info ──")
            for k, v in ecu_info.items():
                print(f"  {k}: {v}")

        elif choice == "2":
            tune_data = read_current_tune(conn)
            print(f"\n[+] Read {len(tune_data)} parameters")

        elif choice == "3":
            read_dtcs(conn)

        elif choice == "4":
            ecu_info = detect_ecu(conn)
            tune_data = read_current_tune(conn)
            dtcs = read_dtcs(conn)
            backup_tune(ecu_info, tune_data, dtcs)

        elif choice == "5":
            ecu_info = detect_ecu(conn)
            tune_data = read_current_tune(conn)
            analyze_tune(ecu_info, tune_data)

        elif choice == "6":
            live_monitor(conn)

        elif choice == "7":
            list_backups()

        elif choice == "8":
            files = list_backups()
            if len(files) < 2:
                print("[!] Need at least 2 backups to compare")
                continue
            try:
                a = int(input("  First file number: ")) - 1
                b = int(input("  Second file number: ")) - 1
                compare_tunes(
                    os.path.join(BACKUP_DIR, files[a]),
                    os.path.join(BACKUP_DIR, files[b]),
                )
            except (ValueError, IndexError):
                print("[!] Invalid selection")

        elif choice == "9":
            print("\n[*] Running full scan...")
            ecu_info = detect_ecu(conn)
            print("\n── ECU Info ──")
            for k, v in ecu_info.items():
                print(f"  {k}: {v}")
            tune_data = read_current_tune(conn)
            dtcs = read_dtcs(conn)
            backup_tune(ecu_info, tune_data, dtcs)
            recommendations = analyze_tune(ecu_info, tune_data)

            name = input("\n  Save this as a tune profile? (name or skip): ").strip()
            if name and name.lower() != "skip":
                save_tune_profile(name, tune_data, recommendations, ecu_info)

            log_event("full_scan", {"vin": ecu_info.get("VIN", "?"), "params": len(tune_data)})

        elif choice == "0":
            print("\n[*] Goodbye!")
            conn.close()
            break


# ── Demo Mode ───────────────────────────────────────────────

def run_demo():
    """Run with fake data to test the UI without a real car."""
    ecu_info = {
        "VIN": "WBAPH5C55BA123456",
        "ECU_NAME": "BOSCH ME17.8.31",
        "CALIBRATION_ID": "1037534956",
        "ELM_VERSION": "ELM327 v2.1",
        "ELM_VOLTAGE": "12.4V",
    }

    tune_data = {
        "RPM": {"value": "850 rpm", "unit": "rpm", "command": "RPM", "desc": "Engine RPM"},
        "SPEED": {"value": "0 kph", "unit": "kph", "command": "SPEED", "desc": "Vehicle Speed"},
        "ENGINE_LOAD": {"value": "32.5 percent", "unit": "percent", "command": "ENGINE_LOAD", "desc": "Calculated Engine Load"},
        "COOLANT_TEMP": {"value": "88 degC", "unit": "degC", "command": "COOLANT_TEMP", "desc": "Engine Coolant Temperature"},
        "INTAKE_TEMP": {"value": "42 degC", "unit": "degC", "command": "INTAKE_TEMP", "desc": "Intake Air Temperature"},
        "SHORT_FUEL_TRIM_1": {"value": "3.1 percent", "unit": "percent", "command": "SHORT_FUEL_TRIM_1", "desc": "Short Term Fuel Trim - Bank 1"},
        "LONG_FUEL_TRIM_1": {"value": "-1.5 percent", "unit": "percent", "command": "LONG_FUEL_TRIM_1", "desc": "Long Term Fuel Trim - Bank 1"},
        "TIMING_ADVANCE": {"value": "14.5 degree", "unit": "degree", "command": "TIMING_ADVANCE", "desc": "Timing Advance"},
        "MAF": {"value": "4.21 gps", "unit": "gps", "command": "MAF", "desc": "Mass Air Flow Rate"},
        "INTAKE_PRESSURE": {"value": "35 kPa", "unit": "kPa", "command": "INTAKE_PRESSURE", "desc": "Intake Manifold Pressure"},
        "FUEL_STATUS": {"value": "Closed loop", "unit": None, "command": "FUEL_STATUS", "desc": "Fuel System Status"},
    }

    dtcs = []

    print("\n── ECU Info (DEMO) ──")
    for k, v in ecu_info.items():
        print(f"  {k}: {v}")

    print(f"\n[*] Reading {len(tune_data)} supported parameters...")
    print("\n── Key Tuning Parameters ──")
    for param, d in tune_data.items():
        unit = f" {d['unit']}" if d["unit"] else ""
        print(f"  {param}: {d['value']}")

    print("\n[+] No trouble codes — car is healthy")

    backup_tune(ecu_info, tune_data, dtcs)
    recommendations = analyze_tune(ecu_info, tune_data)
    save_tune_profile("demo_baseline", tune_data, recommendations, ecu_info)

    print("\n[+] Demo complete! Check the backups/ and tunes/ folders.")


if __name__ == "__main__":
    main()
