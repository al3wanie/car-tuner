"""E38 ECU parameter definitions — base offsets common to all E38 variants.

Offsets are relative to the calibration section start (0x1C0000).
These are derived from community documentation (HP Tuners parameter IDs,
EFILive IDs, TunerPro XDF cross-references).

NOTE: Offsets may vary between OS versions. These are representative for the
most common E38 OS (12612384, 12617560, 12625871). When connecting to a real
ECU, offsets should be verified against the specific OS calibration map.
"""

from ..calibration.definition import ParamDef, TableDef, BitParamDef

# ============================================================================
# SCALAR PARAMETERS
# ============================================================================

PARAMS = {}


def _p(name, category, offset, dtype="uint16", scale=1.0, bias=0.0,
       units="", min_value=0, max_value=65535, description="", dangerous=False):
    PARAMS[name] = ParamDef(
        name=name, category=category, offset=offset, dtype=dtype,
        scale=scale, bias=bias, units=units,
        min_value=min_value, max_value=max_value,
        description=description, dangerous=dangerous,
    )


# --- Security / VATS ---
_p("VATS Fuel Disable Timer", "Security", 0x0812, "uint16", 0.1, 0, "sec", 0, 600,
   "Time engine runs before VATS shuts off fuel if key not recognized")

# --- Rev Limiter ---
_p("Rev Limit Fuel Cut", "Rev Limiter", 0x0E52, "uint16", 1, 0, "RPM", 500, 9000,
   "RPM at which fuel is cut")
_p("Rev Limit Fuel Restore", "Rev Limiter", 0x0E54, "uint16", 1, 0, "RPM", 500, 9000,
   "RPM at which fuel is restored after cut")
_p("Rev Limit Spark Cut", "Rev Limiter", 0x0E56, "uint16", 1, 0, "RPM", 500, 9000,
   "RPM at which spark retard begins")
_p("Rev Limit Max Retard", "Rev Limiter", 0x0E5A, "uint16", 0.1, 0, "deg", 0, 50,
   "Maximum spark retard at rev limit")

# --- Speed Limiter ---
_p("Max Vehicle Speed", "Speed Limiter", 0x0E80, "uint16", 1, 0, "mph", 0, 255,
   "Maximum allowed vehicle speed")
_p("Speed Limiter Hysteresis", "Speed Limiter", 0x0E82, "uint16", 1, 0, "mph", 0, 20,
   "Speed below max at which limiter releases")

# --- Idle ---
_p("Idle Target RPM Park/Neutral", "Idle", 0x1050, "uint16", 1, 0, "RPM", 400, 2000,
   "Target idle RPM in Park/Neutral")
_p("Idle Target RPM In-Gear", "Idle", 0x1052, "uint16", 1, 0, "RPM", 400, 2000,
   "Target idle RPM when transmission is in gear")
_p("Idle Max Airflow", "Idle", 0x1060, "uint16", 0.1, 0, "g/s", 0, 50,
   "Maximum airflow allowed during idle")
_p("Idle Spark Advance", "Idle", 0x1070, "int16", 0.1, 0, "deg", -10, 40,
   "Base spark advance at idle")
_p("Idle RPM Decay Rate", "Idle", 0x1080, "uint16", 1, 0, "RPM/s", 0, 500,
   "Rate at which idle RPM decays to target after blip")

# --- Cooling Fans ---
_p("Fan 1 On Temp", "Fans", 0x1200, "uint16", 0.1, 0, "°F", 150, 260,
   "Temperature at which fan 1 turns on")
_p("Fan 1 Off Temp", "Fans", 0x1202, "uint16", 0.1, 0, "°F", 140, 250,
   "Temperature at which fan 1 turns off")
_p("Fan 2 On Temp", "Fans", 0x1204, "uint16", 0.1, 0, "°F", 180, 270,
   "Temperature at which fan 2 (high speed) turns on")
_p("Fan 2 Off Temp", "Fans", 0x1206, "uint16", 0.1, 0, "°F", 170, 260,
   "Temperature at which fan 2 turns off")
_p("A/C Fan On Temp", "Fans", 0x1208, "uint16", 0.1, 0, "°F", 150, 260,
   "Fan on temperature when A/C is running")
_p("A/C Fan Off Temp", "Fans", 0x120A, "uint16", 0.1, 0, "°F", 140, 250,
   "Fan off temperature when A/C is running")

# --- Fuel ---
_p("Injector Flow Rate", "Fuel", 0x0A00, "uint16", 0.01, 0, "lb/hr", 10, 120,
   "Rated injector flow rate at 43.5 PSI")
_p("Fuel Stoich AFR", "Fuel", 0x0A10, "uint16", 0.001, 0, ":1", 10, 20,
   "Stoichiometric air/fuel ratio (14.68 for gasoline)")
_p("PE Enable Throttle", "Fuel", 0x0B00, "uint16", 0.1, 0, "%", 0, 100,
   "Throttle position at which Power Enrichment activates")
_p("PE AFR Target", "Fuel", 0x0B10, "uint16", 0.01, 0, ":1", 10, 14,
   "Target AFR during Power Enrichment")
_p("PE Delay", "Fuel", 0x0B20, "uint16", 0.01, 0, "sec", 0, 5,
   "Delay before PE activates after throttle threshold")
_p("Fuel Pump Voltage", "Fuel", 0x0A30, "uint16", 0.1, 0, "V", 8, 18,
   "Assumed fuel pump voltage for injector compensation")
_p("Closed Loop Target AFR", "Fuel", 0x0A40, "uint16", 0.001, 0, ":1", 12, 16,
   "Target AFR during closed loop operation")

# --- Spark ---
_p("Spark Advance Base", "Spark", 0x0C00, "int16", 0.1, 0, "deg", -10, 50,
   "Base spark advance at key-on")
_p("Knock Retard Max", "Spark", 0x0C20, "uint16", 0.1, 0, "deg", 0, 20,
   "Maximum knock retard allowed", dangerous=True)
_p("Knock Retard Recovery Rate", "Spark", 0x0C22, "uint16", 0.01, 0, "deg/s", 0, 10,
   "Rate at which spark advance is restored after knock")
_p("Knock Sensitivity", "Spark", 0x0C30, "uint16", 1, 0, "", 0, 255,
   "Knock sensor sensitivity (lower = more sensitive)", dangerous=True)

# --- Torque Management ---
_p("Torque Reduction 1-2 Shift", "Torque", 0x1400, "uint16", 0.1, 0, "%", 0, 100,
   "Torque reduction during 1-2 shift")
_p("Torque Reduction 2-3 Shift", "Torque", 0x1402, "uint16", 0.1, 0, "%", 0, 100,
   "Torque reduction during 2-3 shift")
_p("Torque Reduction 3-4 Shift", "Torque", 0x1404, "uint16", 0.1, 0, "%", 0, 100,
   "Torque reduction during 3-4 shift")
_p("Torque Reduction 4-5 Shift", "Torque", 0x1406, "uint16", 0.1, 0, "%", 0, 100,
   "Torque reduction during 4-5 shift")
_p("Torque Reduction 5-6 Shift", "Torque", 0x1408, "uint16", 0.1, 0, "%", 0, 100,
   "Torque reduction during 5-6 shift")

# --- Transmission ---
_p("TCC Lock Min Temp", "Transmission", 0x1500, "uint16", 0.1, 0, "°F", 0, 250,
   "Minimum coolant temp for TCC lockup")
_p("TCC Slip Target", "Transmission", 0x1510, "uint16", 1, 0, "RPM", 0, 200,
   "Target TCC slip RPM when locked")
_p("Line Pressure Offset", "Transmission", 0x1520, "int16", 0.1, 0, "PSI", -50, 50,
   "Offset added to base line pressure")

# --- MAP Sensor ---
_p("MAP Sensor Range", "MAP", 0x0900, "uint16", 0.01, 0, "bar", 1, 4,
   "MAP sensor maximum range (1-bar, 2-bar, or 3-bar)")
_p("MAP Sensor Offset", "MAP", 0x0902, "int16", 0.001, 0, "V", -1, 1,
   "MAP sensor voltage offset for calibration")

# --- A/C ---
_p("A/C Cutout RPM", "A/C", 0x1300, "uint16", 1, 0, "RPM", 0, 8000,
   "RPM above which A/C compressor is disabled")
_p("A/C Cutout TPS", "A/C", 0x1302, "uint16", 0.1, 0, "%", 0, 100,
   "Throttle position above which A/C is disabled")
_p("A/C Idle RPM Bump", "A/C", 0x1304, "uint16", 1, 0, "RPM", 0, 500,
   "Extra idle RPM when A/C compressor is on")

# --- Startup ---
_p("Cranking Fuel PW", "Startup", 0x0D00, "uint16", 0.01, 0, "ms", 0, 50,
   "Base cranking fuel pulse width")
_p("Cranking Prime Pulses", "Startup", 0x0D10, "uint8", 1, 0, "", 0, 10,
   "Number of prime fuel pulses at key-on")
_p("Startup IAC Steps", "Startup", 0x0D20, "uint16", 1, 0, "steps", 0, 255,
   "Idle air control valve opening on startup")
_p("Startup Spark Advance", "Startup", 0x0D30, "int16", 0.1, 0, "deg", -10, 40,
   "Spark advance during cranking")


# ============================================================================
# BIT PARAMETERS (Enable/Disable flags)
# ============================================================================

BITS = {}


def _b(name, category, offset, bit, inverted=False, description=""):
    BITS[name] = BitParamDef(
        name=name, category=category, offset=offset, bit=bit,
        inverted=inverted, description=description,
    )


# --- Security / VATS ---
_b("VATS Enabled", "Security", 0x0810, 0, False,
   "Vehicle Anti-Theft System — disable for LS swap")
_b("VATS Passlock Enabled", "Security", 0x0810, 1, False,
   "Passlock security system — disable for LS swap")

# --- Features ---
_b("EGR Enabled", "Emissions", 0x0820, 0, False,
   "Exhaust Gas Recirculation system")
_b("EVAP Enabled", "Emissions", 0x0820, 1, False,
   "Evaporative emissions system")
_b("AIR Pump Enabled", "Emissions", 0x0820, 2, False,
   "Secondary air injection pump")
_b("Catalyst Monitor Enabled", "Emissions", 0x0820, 3, False,
   "Catalytic converter efficiency monitor")
_b("O2 Sensor Heater Enabled", "Emissions", 0x0820, 4, False,
   "O2 sensor heater circuit monitor")
_b("Rear O2 Enabled", "Emissions", 0x0820, 5, False,
   "Rear (post-cat) O2 sensor usage")

_b("AFM/DoD Enabled", "AFM", 0x0830, 0, False,
   "Active Fuel Management (cylinder deactivation)")
_b("AFM Oil Pressure Monitor", "AFM", 0x0830, 1, False,
   "AFM oil pressure switch monitoring")

_b("Speed Limiter Enabled", "Speed Limiter", 0x0E81, 0, False,
   "Vehicle speed limiter active")
_b("Cruise Control Enabled", "Features", 0x0840, 0, False,
   "Electronic cruise control")
_b("Skip Shift Enabled", "Features", 0x0840, 1, False,
   "CAGS skip-shift solenoid (1-4 shift in manual trans)")
_b("Traction Control Enabled", "Features", 0x0840, 2, False,
   "Engine-based traction control")
_b("Stabilitrak Enabled", "Features", 0x0840, 3, False,
   "Electronic stability control")

_b("A/C Enabled", "A/C", 0x1301, 0, False,
   "A/C compressor relay output")
_b("A/C Request Input", "A/C", 0x1301, 1, False,
   "A/C request switch input monitoring")


# ============================================================================
# TABLE PARAMETERS
# ============================================================================

TABLES = {}


def _t(name, category, offset, rows=16, cols=16, cell_dtype="uint16",
       cell_scale=1.0, cell_bias=0.0, cell_units="",
       row_axis_offset=0, col_axis_offset=0, axis_dtype="uint16",
       axis_scale=1.0, row_units="RPM", col_units="kPa",
       description="", min_value=0, max_value=65535):
    TABLES[name] = TableDef(
        name=name, category=category, offset=offset,
        rows=rows, cols=cols, cell_dtype=cell_dtype,
        cell_scale=cell_scale, cell_bias=cell_bias, cell_units=cell_units,
        row_axis_offset=row_axis_offset, col_axis_offset=col_axis_offset,
        axis_dtype=axis_dtype, axis_scale=axis_scale,
        row_units=row_units, col_units=col_units,
        description=description, min_value=min_value, max_value=max_value,
    )


# --- VE (Volumetric Efficiency) Tables ---
_t("VE Table Main", "Fuel", 0x2000,
   rows=16, cols=16, cell_dtype="uint16",
   cell_scale=0.00390625, cell_units="%",
   row_axis_offset=0x1F00, col_axis_offset=0x1F40,
   axis_scale=1.0, row_units="RPM", col_units="kPa",
   description="Main Volumetric Efficiency table — the heart of fueling",
   min_value=0, max_value=200)

_t("VE Table Secondary", "Fuel", 0x2400,
   rows=16, cols=16, cell_dtype="uint16",
   cell_scale=0.00390625, cell_units="%",
   row_axis_offset=0x1F00, col_axis_offset=0x1F40,
   description="Secondary VE table for blended fueling",
   min_value=0, max_value=200)

_t("VE Table High Octane", "Fuel", 0x2800,
   rows=16, cols=16, cell_dtype="uint16",
   cell_scale=0.00390625, cell_units="%",
   row_axis_offset=0x1F00, col_axis_offset=0x1F40,
   description="High octane VE table",
   min_value=0, max_value=200)

# --- MAF Table ---
_t("MAF Airflow Table", "Fuel", 0x3000,
   rows=1, cols=256, cell_dtype="uint16",
   cell_scale=0.01, cell_units="g/s",
   col_axis_offset=0x2F00, axis_scale=1.0,
   col_units="Hz",
   description="MAF frequency to airflow conversion (up to 15400 Hz)",
   min_value=0, max_value=1024)

# --- PE (Power Enrichment) EQ Ratio Table ---
_t("PE EQ Ratio vs RPM", "Fuel", 0x3400,
   rows=1, cols=16, cell_dtype="uint16",
   cell_scale=0.001, cell_units=":1",
   col_axis_offset=0x33E0, axis_scale=1.0, col_units="RPM",
   description="Power Enrichment equivalence ratio by RPM",
   min_value=0.7, max_value=1.2)

# --- Spark Advance Tables ---
_t("Spark Advance High Octane", "Spark", 0x4000,
   rows=16, cols=16, cell_dtype="int16",
   cell_scale=0.1, cell_units="deg",
   row_axis_offset=0x3F00, col_axis_offset=0x3F40,
   axis_scale=1.0, row_units="RPM", col_units="kPa",
   description="Spark advance table for high octane fuel",
   min_value=-10, max_value=60)

_t("Spark Advance Low Octane", "Spark", 0x4400,
   rows=16, cols=16, cell_dtype="int16",
   cell_scale=0.1, cell_units="deg",
   row_axis_offset=0x3F00, col_axis_offset=0x3F40,
   description="Spark advance table for low octane fuel",
   min_value=-10, max_value=60)

# --- Transmission Shift Tables ---
_t("1-2 Shift Points", "Transmission", 0x5000,
   rows=1, cols=16, cell_dtype="uint16",
   cell_scale=1, cell_units="mph",
   col_axis_offset=0x4FE0, axis_scale=0.1, col_units="% TPS",
   description="1-2 upshift speed vs throttle position",
   min_value=0, max_value=200)

_t("2-3 Shift Points", "Transmission", 0x5040,
   rows=1, cols=16, cell_dtype="uint16",
   cell_scale=1, cell_units="mph",
   col_axis_offset=0x4FE0,
   description="2-3 upshift speed vs throttle position",
   min_value=0, max_value=200)

_t("3-4 Shift Points", "Transmission", 0x5080,
   rows=1, cols=16, cell_dtype="uint16",
   cell_scale=1, cell_units="mph",
   col_axis_offset=0x4FE0,
   description="3-4 upshift speed vs throttle position",
   min_value=0, max_value=200)

_t("4-5 Shift Points", "Transmission", 0x50C0,
   rows=1, cols=16, cell_dtype="uint16",
   cell_scale=1, cell_units="mph",
   col_axis_offset=0x4FE0,
   description="4-5 upshift speed vs throttle position",
   min_value=0, max_value=200)

_t("5-6 Shift Points", "Transmission", 0x5100,
   rows=1, cols=16, cell_dtype="uint16",
   cell_scale=1, cell_units="mph",
   col_axis_offset=0x4FE0,
   description="5-6 upshift speed vs throttle position",
   min_value=0, max_value=200)

# --- Line Pressure Table ---
_t("Line Pressure vs TPS", "Transmission", 0x5200,
   rows=1, cols=16, cell_dtype="uint16",
   cell_scale=0.1, cell_units="PSI",
   col_axis_offset=0x4FE0, axis_scale=0.1, col_units="% TPS",
   description="Transmission line pressure vs throttle position",
   min_value=0, max_value=400)

# --- Fan Speed Table ---
_t("Fan Speed vs Coolant Temp", "Fans", 0x1220,
   rows=1, cols=8, cell_dtype="uint16",
   cell_scale=0.1, cell_units="%",
   col_axis_offset=0x1210, axis_scale=0.1, col_units="°F",
   description="Fan duty cycle vs coolant temperature",
   min_value=0, max_value=100)

# --- Idle Airflow vs Coolant Temp ---
_t("Idle Airflow vs ECT", "Idle", 0x1090,
   rows=1, cols=16, cell_dtype="uint16",
   cell_scale=0.01, cell_units="g/s",
   col_axis_offset=0x1088, axis_scale=0.1, col_units="°F",
   description="Target idle airflow vs engine coolant temperature",
   min_value=0, max_value=50)

# --- Knock Retard Table ---
_t("Knock Retard Table", "Spark", 0x0C40,
   rows=16, cols=16, cell_dtype="uint16",
   cell_scale=0.1, cell_units="deg",
   row_axis_offset=0x3F00, col_axis_offset=0x3F40,
   description="Maximum knock retard by RPM and load",
   min_value=0, max_value=30)
