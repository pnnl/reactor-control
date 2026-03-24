"""Example experiment: Steady-State Test.

Run this script to execute a steady-state experiment.
Copy and modify this file for your own experiments.
"""

from src.experiments import Experiment, Sample


# Initialize the experiment
exp = Experiment(
    name="steady-state",
    output_dir=None,  # None = use default (C:/Data)
    connect_devices=True,  # Set True to use real hardware
)

try:
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
            "h2": 9300.0,  # ppm
            "nh3": 0.0,  # ppm
            "no": 350.0,  # ppm
            "o2": 0.0,  # percent
            "h2o": 0.0,  # percent
        },
    )

    exp.set_temperature(target=120, rate=20.0, hold_minutes=0.1)

    exp.start_data_collection(interval_sec=5.0)

    exp.run_temperature_program(
        target_temps=[120, 140, 160, 180, 200, 225, 250, 275, 300, 350, 400],  # °C
        ramp_rates=[10.0],  # °C/min
        hold_times=[30],  # min
    )

    exp.stop_data_collection()

finally:
    exp.close()
