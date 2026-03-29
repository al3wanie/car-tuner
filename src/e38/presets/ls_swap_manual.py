"""Preset: LS 6.0 HD swap into VTC 4800 with manual transmission.

Applies all tuning changes for:
- Engine: LS 6.0 HD (LQ4/LQ9 iron block)
- ECU: E38
- Body: VTC 4800
- Transmission: Manual from VTC 4500
- Fuel: UAE 95 octane pump gas
- Injectors: Stock 28.8 lb/hr

Run with: python e38_tuner.py --preset ls_swap_manual
"""

import logging

log = logging.getLogger(__name__)


def apply(editor):
    """Apply all LS 6.0 HD manual swap preset changes.

    Args:
        editor: CalibrationEditor instance with loaded calibration

    Returns:
        list: summary of all changes applied
    """
    changes = []

    def set_param(name, value, reason=""):
        try:
            old = editor.get_param(name)
            editor.set_param(name, value)
            changes.append(f"  {name}: {old} -> {value} {reason}")
            log.info(f"Set {name} = {value} ({reason})")
        except Exception as e:
            changes.append(f"  {name}: FAILED - {e}")
            log.warning(f"Failed to set {name}: {e}")

    def set_bit(name, enabled, reason=""):
        try:
            old = editor.get_bit(name)
            editor.set_bit(name, enabled)
            status = "ENABLED" if enabled else "DISABLED"
            changes.append(f"  {name}: {status} {reason}")
            log.info(f"Set {name} = {status} ({reason})")
        except Exception as e:
            changes.append(f"  {name}: FAILED - {e}")
            log.warning(f"Failed to set {name}: {e}")

    def disable_dtc(code, reason=""):
        try:
            editor.set_dtc_enabled(code, False)
            dtc_name = editor.dtcs[code].name if code in editor.dtcs else ""
            changes.append(f"  {code} ({dtc_name}): DISABLED {reason}")
        except Exception as e:
            changes.append(f"  {code}: FAILED - {e}")

    # =================================================================
    # STEP 1: VATS / SECURITY — Must disable for LS swap
    # =================================================================
    changes.append("\n[STEP 1] VATS / Security — Disable anti-theft")
    set_bit("VATS Enabled", False, "— required for LS swap")
    set_bit("VATS Passlock Enabled", False, "— required for LS swap")
    set_param("VATS Fuel Disable Timer", 0, "— no fuel cutoff")

    # =================================================================
    # STEP 2: EMISSIONS — Disable systems not present in swap
    # =================================================================
    changes.append("\n[STEP 2] Emissions — Disable missing systems")
    set_bit("EGR Enabled", False, "— no EGR on swap")
    set_bit("EVAP Enabled", False, "— different evap system")
    set_bit("AIR Pump Enabled", False, "— no secondary air pump")
    set_bit("Catalyst Monitor Enabled", False, "— different exhaust")
    set_bit("O2 Sensor Heater Enabled", False, "— if no rear O2")
    set_bit("Rear O2 Enabled", False, "— no post-cat O2")

    # =================================================================
    # STEP 3: AFM / FEATURES — Disable incompatible features
    # =================================================================
    changes.append("\n[STEP 3] Features — Disable incompatible systems")
    set_bit("AFM/DoD Enabled", False, "— 6.0 HD has no AFM")
    set_bit("AFM Oil Pressure Monitor", False, "— no AFM solenoids")
    set_bit("Traction Control Enabled", False, "— VTC system won't match")
    set_bit("Stabilitrak Enabled", False, "— not compatible")
    set_bit("Skip Shift Enabled", False, "— no CAGS solenoid")
    set_bit("Cruise Control Enabled", False, "— disable unless wired")

    # =================================================================
    # STEP 4: TORQUE MANAGEMENT — Zero out for manual trans
    # =================================================================
    changes.append("\n[STEP 4] Torque Management — Zero for manual transmission")
    set_param("Torque Reduction 1-2 Shift", 0, "— manual, no auto shifts")
    set_param("Torque Reduction 2-3 Shift", 0, "— manual")
    set_param("Torque Reduction 3-4 Shift", 0, "— manual")
    set_param("Torque Reduction 4-5 Shift", 0, "— manual")
    set_param("Torque Reduction 5-6 Shift", 0, "— manual")
    set_param("TCC Lock Min Temp", 0, "— no torque converter")
    set_param("TCC Slip Target", 0, "— no torque converter")
    set_param("Line Pressure Offset", 0, "— no auto trans")

    # =================================================================
    # STEP 5: REV LIMITER — Raise for manual trans
    # =================================================================
    changes.append("\n[STEP 5] Rev Limiter — Raise for manual")
    set_param("Rev Limit Fuel Cut", 6500, "— raised from ~5800")
    set_param("Rev Limit Fuel Restore", 6300, "— raised from ~5600")
    set_param("Rev Limit Spark Cut", 6400, "— raised from ~5700")
    set_param("Rev Limit Max Retard", 15, "— progressive retard")

    # =================================================================
    # STEP 6: SPEED LIMITER — Remove
    # =================================================================
    changes.append("\n[STEP 6] Speed Limiter — Remove")
    set_param("Max Vehicle Speed", 255, "— no speed limit")
    set_param("Speed Limiter Hysteresis", 5, "")
    set_bit("Speed Limiter Enabled", False, "— removed")

    # =================================================================
    # STEP 7: IDLE — Tune for manual trans
    # =================================================================
    changes.append("\n[STEP 7] Idle — Tune for manual transmission")
    set_param("Idle Target RPM Park/Neutral", 850, "— smooth idle")
    set_param("Idle Target RPM In-Gear", 850, "— same for manual")
    set_param("Idle Spark Advance", 15, "— stable idle")
    set_param("Idle Max Airflow", 8, "— prevent high idle")
    set_param("Idle RPM Decay Rate", 200, "— smooth return from blip")

    # =================================================================
    # STEP 8: COOLING FANS — Set for VTC radiator
    # =================================================================
    changes.append("\n[STEP 8] Cooling Fans — UAE heat protection")
    set_param("Fan 1 On Temp", 195, "— normal cooling")
    set_param("Fan 1 Off Temp", 185, "")
    set_param("Fan 2 On Temp", 210, "— high speed when hot")
    set_param("Fan 2 Off Temp", 200, "")
    set_param("A/C Fan On Temp", 190, "")
    set_param("A/C Fan Off Temp", 180, "")

    # =================================================================
    # STEP 9: FUEL — Stock 6.0 HD injectors, UAE 95 octane
    # =================================================================
    changes.append("\n[STEP 9] Fuel — Stock LQ4/LQ9 injectors")
    set_param("Injector Flow Rate", 28.8, "— stock 6.0 HD injectors")
    set_param("Fuel Stoich AFR", 14.68, "— gasoline stoich")
    set_param("Closed Loop Target AFR", 14.68, "— economy cruise")
    set_param("PE Enable Throttle", 70, "— power enrichment at 70% throttle")
    set_param("PE AFR Target", 12.5, "— rich for full throttle power")
    set_param("PE Delay", 0.5, "— quick enrichment response")
    set_param("Cranking Fuel PW", 6.0, "— good cold start")
    set_param("Cranking Prime Pulses", 2, "— prime before crank")

    # =================================================================
    # STEP 10: SPARK — Safe tune for UAE 95 octane
    # =================================================================
    changes.append("\n[STEP 10] Spark — Safe for UAE 95 octane pump gas")
    set_param("Knock Retard Max", 12, "— allow retard if knock")
    set_param("Knock Retard Recovery Rate", 2, "— recover 2°/sec")
    set_param("Knock Sensitivity", 128, "— middle sensitivity")
    set_param("Startup Spark Advance", 15, "— good cold start")

    # =================================================================
    # STEP 11: A/C — If wired
    # =================================================================
    changes.append("\n[STEP 11] A/C — UAE essential")
    set_param("A/C Cutout RPM", 6200, "— cut A/C near redline")
    set_param("A/C Cutout TPS", 95, "— cut A/C at WOT only")
    set_param("A/C Idle RPM Bump", 100, "— +100 RPM with A/C on")

    # =================================================================
    # STEP 12: MAP SENSOR — Stock 1-bar
    # =================================================================
    changes.append("\n[STEP 12] MAP Sensor — Stock 1-bar")
    set_param("MAP Sensor Range", 1.05, "— stock 1-bar MAP")

    # =================================================================
    # STEP 13: DTCs — Disable codes for missing equipment
    # =================================================================
    changes.append("\n[STEP 13] DTCs — Disable for LS swap")

    # VATS DTCs
    for code in ["P1621", "P1626", "P1631", "P0513"]:
        disable_dtc(code, "— VATS")

    # Emissions DTCs
    for code in ["P0401", "P0404", "P0405",  # EGR
                  "P0410", "P0411", "P0412", "P0418",  # AIR
                  "P0440", "P0441", "P0442", "P0443",  # EVAP
                  "P0446", "P0449", "P0452", "P0453",
                  "P0455", "P0496",
                  "P0420", "P0430"]:  # Catalyst
        disable_dtc(code, "— emissions")

    # AFM DTCs
    for code in ["P06DD", "P0657", "P0521"]:
        disable_dtc(code, "— AFM")

    # Transmission DTCs (auto trans codes)
    for code in ["P0700", "P0711", "P0716", "P0717", "P0722",
                  "P0725", "P0741", "P0742", "P0748", "P0751",
                  "P0756", "P0761"]:
        disable_dtc(code, "— auto trans")

    # Rear O2 DTCs
    for code in ["P0136", "P0137", "P0138", "P0140", "P0141",
                  "P0156", "P0157", "P0158", "P0160", "P0161"]:
        disable_dtc(code, "— rear O2")

    # =================================================================
    # SUMMARY
    # =================================================================
    changes.append(f"\n{'='*50}")
    changes.append(f"PRESET COMPLETE: LS 6.0 HD → VTC 4800 Manual")
    changes.append(f"Total byte changes: {len(editor.get_byte_diff())}")
    changes.append(f"{'='*50}")

    return changes
