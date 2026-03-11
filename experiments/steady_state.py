"""Example experiment script: Steady-State Test.

This is an example of how to write an experiment script using
the ExperimentContext atomic operations.

Copy this file and modify it for your own experiments.
"""

import time
from src.experiments.scripting import ExperimentContext, Sample


# =============================================================================
# EXPERIMENT SCRIPT
# =============================================================================

# The 'with' statement ensures proper setup and cleanup
with ExperimentContext(
    name="steady-state",
    output_dir=None,  # None = use default (C:/Data)
    connect_devices=True,  # Set True to use real hardware
) as exp:
    # -------------------------------------------------------------------------
    # 1. Define the sample
    # -------------------------------------------------------------------------
    exp.set_sample(
        Sample(
            user_label="nn1120",
            mass_mg=50.0,
            operator="nelson",
            composition="Pd/Al2O3",
            metal="Pd",
            support="g-Al2O3",
            metal_loading_wt_percent=0.1,
            mesh_size="40-60",
            notes="",
        )
    )
    """Let's add all the info from .scripting.py"""

    # -------------------------------------------------------------------------
    # 2. Purge the system
    # -------------------------------------------------------------------------

    exp.set_gas_flows(
        total_flow_rate=410,
        gas_concentrations={
            "h2": 9300.0,  # ppm
            "nh3": 0.0,  # ppm
            "no": 350.0,  # ppm
            "o2": 2.0,  # percent
            "h2o": 0.0,  # percent
        },
    )
    exp.set_temperature(target=400, rate=10, hold_minutes=0.1)
    exp.log_step()

    # -------------------------------------------------------------------------
    # 5. First steady-state measurement
    # -------------------------------------------------------------------------

    exp.set_gas_flows(
        total_flow_rate=410,
        gas_concentrations={
            "h2": 9300.0,  # ppm
            "nh3": 0.0,  # ppm
            "no": 350.0,  # ppm
            "o2": 2.0,  # percent
            "h2o": 0.0,  # percent
        },
    )
    exp.set_temperature(target=400, rate=10, hold_minutes=0.1)
    exp.log_step()

    # -------------------------------------------------------------------------
    # 7. Second steady-state measurement
    # -------------------------------------------------------------------------

    exp.start_data_collection(interval_sec=5.0)
    exp.hold(minutes=0.1, description="300C steady-state")
    exp.stop_data_collection()

    # -------------------------------------------------------------------------
    # 8. Ramp to second setpoint
    # -------------------------------------------------------------------------
    exp.log_step("Ramping to second temperature (300C)")
    exp.set_temperature(target=300, rate=10, hold_minutes=1)

    # -------------------------------------------------------------------------
    # 9. Second steady-state measurement
    # -------------------------------------------------------------------------
    exp.log_step("Second steady-state measurement at 300C")
    exp.start_data_collection(interval_sec=5.0)
    exp.hold(minutes=1, description="300C steady-state")
    exp.stop_data_collection()

    # -------------------------------------------------------------------------
    # 10. Ramp to second setpoint
    # -------------------------------------------------------------------------
    exp.log_step("Ramping to second temperature (300C)")
    exp.set_temperature(target=300, rate=10, hold_minutes=5)

    # -------------------------------------------------------------------------
    # 11. Second steady-state measurement
    # -------------------------------------------------------------------------
    exp.log_step("Second steady-state measurement at 300C")
    exp.start_data_collection(interval_sec=5.0)
    exp.hold(minutes=30, description="300C steady-state")
    exp.stop_data_collection()

    # -------------------------------------------------------------------------
    # 12. Cleanup - stop all flows
    # -------------------------------------------------------------------------
    exp.log_step("Experiment complete - stopping flows")
    exp.stop_all_flows()

# The context manager automatically handles cleanup when exiting the 'with' block
