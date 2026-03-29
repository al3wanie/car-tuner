"""DTC (Diagnostic Trouble Code) definitions for E38 ECU.

Each DTC has an enable/disable flag in the calibration that can be toggled.
Offset and bit positions are for common E38 OS versions.
"""

from ..calibration.definition import DTCDef

DTCS = {}


def _d(code, name, offset, bit, inverted=False, category="Powertrain"):
    DTCS[code] = DTCDef(
        code=code, name=name, offset=offset, bit=bit,
        inverted=inverted, category=category,
    )


# --- Engine / Fuel ---
_d("P0101", "MAF Sensor Range/Performance", 0x6000, 0)
_d("P0102", "MAF Sensor Circuit Low", 0x6000, 1)
_d("P0103", "MAF Sensor Circuit High", 0x6000, 2)
_d("P0106", "MAP Sensor Range/Performance", 0x6000, 3)
_d("P0107", "MAP Sensor Circuit Low", 0x6000, 4)
_d("P0108", "MAP Sensor Circuit High", 0x6000, 5)
_d("P0112", "IAT Sensor Circuit Low", 0x6000, 6)
_d("P0113", "IAT Sensor Circuit High", 0x6000, 7)

_d("P0116", "ECT Sensor Range/Performance", 0x6001, 0)
_d("P0117", "ECT Sensor Circuit Low", 0x6001, 1)
_d("P0118", "ECT Sensor Circuit High", 0x6001, 2)
_d("P0121", "TPS Range/Performance", 0x6001, 3)
_d("P0122", "TPS Circuit Low", 0x6001, 4)
_d("P0123", "TPS Circuit High", 0x6001, 5)
_d("P0128", "Thermostat Rationality", 0x6001, 6)
_d("P0130", "O2 Sensor B1S1 Circuit", 0x6001, 7)

_d("P0131", "O2 Sensor B1S1 Low Voltage", 0x6002, 0)
_d("P0132", "O2 Sensor B1S1 High Voltage", 0x6002, 1)
_d("P0133", "O2 Sensor B1S1 Slow Response", 0x6002, 2)
_d("P0134", "O2 Sensor B1S1 No Activity", 0x6002, 3)
_d("P0135", "O2 Sensor B1S1 Heater Circuit", 0x6002, 4)
_d("P0136", "O2 Sensor B1S2 Circuit", 0x6002, 5)
_d("P0137", "O2 Sensor B1S2 Low Voltage", 0x6002, 6)
_d("P0138", "O2 Sensor B1S2 High Voltage", 0x6002, 7)

_d("P0140", "O2 Sensor B1S2 No Activity", 0x6003, 0)
_d("P0141", "O2 Sensor B1S2 Heater Circuit", 0x6003, 1)
_d("P0151", "O2 Sensor B2S1 Low Voltage", 0x6003, 2)
_d("P0152", "O2 Sensor B2S1 High Voltage", 0x6003, 3)
_d("P0153", "O2 Sensor B2S1 Slow Response", 0x6003, 4)
_d("P0154", "O2 Sensor B2S1 No Activity", 0x6003, 5)
_d("P0155", "O2 Sensor B2S1 Heater Circuit", 0x6003, 6)
_d("P0156", "O2 Sensor B2S2 Circuit", 0x6003, 7)

_d("P0157", "O2 Sensor B2S2 Low Voltage", 0x6004, 0)
_d("P0158", "O2 Sensor B2S2 High Voltage", 0x6004, 1)
_d("P0160", "O2 Sensor B2S2 No Activity", 0x6004, 2)
_d("P0161", "O2 Sensor B2S2 Heater Circuit", 0x6004, 3)

# --- Knock ---
_d("P0325", "Knock Sensor 1 Circuit", 0x6004, 4)
_d("P0330", "Knock Sensor 2 Circuit", 0x6004, 5)
_d("P0327", "Knock Sensor 1 Low", 0x6004, 6)
_d("P0332", "Knock Sensor 2 Low", 0x6004, 7)

# --- Misfire ---
_d("P0300", "Random/Multiple Cylinder Misfire", 0x6005, 0)
_d("P0301", "Cylinder 1 Misfire", 0x6005, 1)
_d("P0302", "Cylinder 2 Misfire", 0x6005, 2)
_d("P0303", "Cylinder 3 Misfire", 0x6005, 3)
_d("P0304", "Cylinder 4 Misfire", 0x6005, 4)
_d("P0305", "Cylinder 5 Misfire", 0x6005, 5)
_d("P0306", "Cylinder 6 Misfire", 0x6005, 6)
_d("P0307", "Cylinder 7 Misfire", 0x6005, 7)
_d("P0308", "Cylinder 8 Misfire", 0x6006, 0)

# --- Catalytic Converter ---
_d("P0420", "Catalyst B1 Efficiency Below Threshold", 0x6006, 1)
_d("P0430", "Catalyst B2 Efficiency Below Threshold", 0x6006, 2)

# --- EVAP ---
_d("P0440", "EVAP System Malfunction", 0x6006, 3)
_d("P0441", "EVAP Incorrect Purge Flow", 0x6006, 4)
_d("P0442", "EVAP Small Leak", 0x6006, 5)
_d("P0443", "EVAP Purge Valve Circuit", 0x6006, 6)
_d("P0446", "EVAP Vent System", 0x6006, 7)
_d("P0449", "EVAP Vent Valve Circuit", 0x6007, 0)
_d("P0452", "EVAP Pressure Sensor Low", 0x6007, 1)
_d("P0453", "EVAP Pressure Sensor High", 0x6007, 2)
_d("P0455", "EVAP Large Leak", 0x6007, 3)
_d("P0496", "EVAP Purge Flow During Non-Purge", 0x6007, 4)

# --- EGR ---
_d("P0401", "EGR Insufficient Flow", 0x6007, 5)
_d("P0404", "EGR Control Circuit Range/Performance", 0x6007, 6)
_d("P0405", "EGR Sensor A Circuit Low", 0x6007, 7)

# --- AIR ---
_d("P0410", "Secondary AIR System", 0x6008, 0)
_d("P0411", "Secondary AIR Incorrect Flow", 0x6008, 1)
_d("P0412", "Secondary AIR Valve A Circuit", 0x6008, 2)
_d("P0418", "Secondary AIR Relay A Circuit", 0x6008, 3)

# --- Fuel System ---
_d("P0171", "System Too Lean B1", 0x6008, 4)
_d("P0172", "System Too Rich B1", 0x6008, 5)
_d("P0174", "System Too Lean B2", 0x6008, 6)
_d("P0175", "System Too Rich B2", 0x6008, 7)

# --- Transmission ---
_d("P0700", "Transmission Control System", 0x6009, 0, category="Transmission")
_d("P0711", "Trans Fluid Temp Sensor Range", 0x6009, 1, category="Transmission")
_d("P0716", "Turbine Shaft Speed Sensor", 0x6009, 2, category="Transmission")
_d("P0717", "Turbine Speed Sensor No Signal", 0x6009, 3, category="Transmission")
_d("P0722", "Output Speed Sensor No Signal", 0x6009, 4, category="Transmission")
_d("P0725", "Engine Speed Input Circuit", 0x6009, 5, category="Transmission")
_d("P0741", "TCC Stuck Off", 0x6009, 6, category="Transmission")
_d("P0742", "TCC Stuck On", 0x6009, 7, category="Transmission")
_d("P0748", "Pressure Control Solenoid A", 0x600A, 0, category="Transmission")
_d("P0751", "Shift Solenoid A Performance", 0x600A, 1, category="Transmission")
_d("P0756", "Shift Solenoid B Performance", 0x600A, 2, category="Transmission")
_d("P0761", "Shift Solenoid C Performance", 0x600A, 3, category="Transmission")

# --- AFM/DoD ---
_d("P0521", "Oil Pressure Sensor Range", 0x600A, 4, category="AFM")
_d("P06DD", "AFM Oil Pressure Control Performance", 0x600A, 5, category="AFM")
_d("P0657", "AFM Solenoid Control Circuit", 0x600A, 6, category="AFM")

# --- VATS ---
_d("P1621", "VATS - PCM Memory Reset", 0x600A, 7, category="Security")
_d("P1626", "VATS - Fuel Enable Signal Not Received", 0x600B, 0, category="Security")
_d("P1631", "VATS - Theft Deterrent Fuel Disable", 0x600B, 1, category="Security")
_d("P0513", "Incorrect Immobilizer Key", 0x600B, 2, category="Security")
