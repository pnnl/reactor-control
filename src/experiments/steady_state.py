"""Steady-State Experiment.

Run this script to execute a steady-state experiment:
    python -m src.experiments.steady_state

Or from project root:
    python src/experiments/steady_state.py

Copy and modify this file for your own experiments.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to path so 'src' imports work
SRC_PATH = Path(__file__).resolve().parent.parent.parent
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from src.experiments import Experiment, Sample
from src.analyze import load_and_process


def run_steady_state(
    connect_devices: bool = True,
) -> tuple[Experiment, Path]:
    """Run a steady-state experiment.

    Args:
        connect_devices: If True, connect to real hardware. If False, mock mode.

    Returns:
        Tuple of (Experiment instance, path to output CSV).
    """
    exp = Experiment(
        name="steady-state",
        output_dir=None,
        connect_devices=connect_devices,
    )

    exp.set_sample(
        Sample(
            batch_id="nn2061",
            mass_mg=50.0,
            operator="nelson",
            composition="Pd/Al2O3",
            metal="Pd",
            support="g-Al2O3",
            metal_loading_wt_percent=0.1,
            mesh_size="30-60",
            synthesis_method="",
        )
    )

    exp.set_gas_flows(
        total_flow_rate=410,
        gas_concentrations={
            "h2": 9300.0,
            "nh3": 0.0,
            "no": 350.0,
            "o2": 0.0,
            "h2o": 3.0,
        },
    )

    exp.set_temperature(target=120, rate=20.0, hold_minutes=0.1)
    
    exp.start_data_collection(interval_sec=5.0)
    exp.run_temperature_program(
        target_temps=[120, 140, 160, 180, 200, 225, 250, 275, 300, 350, 400],
        ramp_rates=[10.0],
        hold_times=[30],
    )
    exp.stop_data_collection()

    ss_df = load_and_process(exp.experiment_id)
    exp.export_to_z_drive()
    exp.close()

    return exp, ss_df


if __name__ == "__main__":

    exp, ss_df = run_steady_state(connect_devices=True)

