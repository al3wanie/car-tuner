"""
E38 ECU Tuner — Professional LS Engine Tuning Tool.

Read, write, flash, and tune GM E38 ECUs via J2534 passthrough adapter.
Supports offline .bin file editing and live ECU connection.

Usage:
    python e38_tuner.py              # Start with home screen
    python e38_tuner.py --demo       # Demo mode (no hardware needed)
    python e38_tuner.py --file X.bin # Open a saved .bin file
"""

import sys
import os
import argparse
import logging

# Ensure the project root is in the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Windows console encoding fix
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


def setup_logging(verbose=False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        handlers=[
            logging.FileHandler("e38_tuner.log", encoding="utf-8"),
            logging.StreamHandler() if verbose else logging.NullHandler(),
        ],
    )


def main():
    parser = argparse.ArgumentParser(
        description="E38 ECU Tuner — Professional LS Engine Tuning Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python e38_tuner.py                            Start the tuner (home screen)
  python e38_tuner.py --demo                     Demo mode for testing without hardware
  python e38_tuner.py --file backup.bin          Open a saved calibration file
  python e38_tuner.py --preset ls_swap_manual    Apply LS 6.0 HD VTC manual swap preset
  python e38_tuner.py -v                         Verbose logging for debugging
        """,
    )
    parser.add_argument("--demo", action="store_true", help="Start in demo mode (no hardware)")
    parser.add_argument("--file", "-f", type=str, help="Open a .bin calibration file")
    parser.add_argument("--preset", type=str, help="Apply a preset (e.g., ls_swap_manual)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    args = parser.parse_args()

    setup_logging(args.verbose)

    # Check dependencies
    try:
        import textual  # noqa: F401
    except ImportError:
        print("Missing dependency: textual")
        print("Install with: pip install -r requirements_e38.txt")
        sys.exit(1)

    from src.e38.ui.app import E38TunerApp

    app = E38TunerApp(bin_file=args.file, demo=args.demo, preset=args.preset)
    app.run()


if __name__ == "__main__":
    main()
