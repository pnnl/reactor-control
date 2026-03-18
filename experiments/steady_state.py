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

with ExperimentContext(
    name="steady-state",
    output_dir=None,  # None = use default (C:/Data)
    connect_devices=True,  # Set True to use real hardware
) as exp:

    exp.set_sample(
        Sample(
            batch_id="nn1120-2",
            mass_mg=50.0,
            operator="nelson",
            composition="Pd/Al2O3",
            metal="Pd",
            support="g-Al2O3",
            metal_loading_wt_percent=0.1,
            mesh_size="40-60",
            synthesis_method=""
        )
    )


    exp.set_gas_flows(
        total_flow_rate=410,
        gas_concentrations={
            "h2": 9300.0,  # ppm
            "nh3": 0.0,  # ppm
            "no": 350.0,  # ppm
            "o2": 2.0,  # percent
            "h2o": 2.0,  # percent
        },
    )
    exp.set_temperature(target=200, rate=10, hold_minutes=0.1)
    exp.log_step()

    """ need to introudce parameter collect_data: True/False
    """

    exp.set_gas_flows(
        total_flow_rate=410,
        gas_concentrations={
            "h2": 6300.0,  # ppm
            "nh3": 0.0,  # ppm
            "no": 300.0,  # ppm
            "o2": 3.0,  # percent
            "h2o": 1.0,  # percent
        },
    )
    exp.set_temperature(target=400, rate=10, hold_minutes=0.1)
    exp.log_step()


    exp.start_data_collection(interval_sec=5.0)
  
    exp.hold(minutes=1.0)
    exp.stop_data_collection()
    exp.log_step()


    # exp.standby(temperature=200.0)
    # exp.export_to_z_drive()

