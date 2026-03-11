"""Run experiment scripts from VSCode.

To run an experiment:
1. Create your experiment script (see experiments/ folder)
2. Edit the SCRIPT_PATH below to point to your script
3. Press F5 or click Run to execute

Example scripts are provided in the experiments/ folder.
"""

import sys
from pathlib import Path

# Add src to path
SRC_PATH = Path(__file__).resolve().parent.parent.parent
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))


# =============================================================================
# CONFIGURATION - Edit these values before running
# =============================================================================

# Path to your experiment script (relative to project root or absolute)
# Examples:
#   - experiments/my_experiment.py
#   - experiments/example_nox_test.py
#   - C:/Users/labuser/my_experiments/test.py
SCRIPT_PATH = Path("experiments/steady_state.py")

# Connect to physical devices?
# Set to True only when ready to run with real hardware
CONNECT_DEVICES = True

# Output directory for experiment data (None = use default from config/paths.yaml)
OUTPUT_DIR = None


# =============================================================================
# MAIN SCRIPT - Run this file in VSCode
# =============================================================================


def main() -> None:
    """Run the experiment script."""

    print("=" * 60)
    print("EXPERIMENT RUNNER")
    print("=" * 60)
    print(f"Script: {SCRIPT_PATH}")
    print(f"Output: {OUTPUT_DIR or 'default'}")
    print(f"Devices: {'Yes' if CONNECT_DEVICES else 'No (mock mode)'}")
    print()

    # Check if script exists
    if not SCRIPT_PATH.exists():
        print(f"[ERROR] Script not found: {SCRIPT_PATH}")
        print()
        print("Create your experiment script and set SCRIPT_PATH above.")
        print("Example scripts are in the experiments/ folder.")
        return

    # Load the experiment script
    print(f"Loading script: {SCRIPT_PATH}")
    script_globals = {
        "__file__": str(SCRIPT_PATH),
        "__name__": "__experiment_script__",
    }

    try:
        with open(SCRIPT_PATH, "r", encoding="utf-8") as f:
            script_code = f.read()
    except Exception as exc:
        print(f"[ERROR] Failed to read script: {exc}")
        return

    # Execute the script
    # The script should use 'with ExperimentContext(...) as exp: ...'
    print("Running experiment...")
    print()

    try:
        exec(compile(script_code, SCRIPT_PATH, "exec"), script_globals)
    except Exception as exc:
        print()
        print(f"[ERROR] Experiment failed: {exc}")
        import traceback

        traceback.print_exc()
        return

    print()
    print("Done.")


if __name__ == "__main__":
    main()
