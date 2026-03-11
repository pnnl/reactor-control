"""Experiments layer for reactor control.

Flexible scripting interface for designing experiments.

Example:
    from src.experiments.scripting import ExperimentContext, Sample

    with ExperimentContext(name="My Experiment") as exp:
        exp.set_sample(Sample(material_type="catalyst", user_label="Test-001", mass_mg=100.0))
        exp.set_temperature(target=200, rate=5)
        exp.hold(minutes=30)
        exp.set_gas_flows(total_flow_rate=100, gas_concentrations={"NO_ppm": 500})
        exp.hold(minutes=60)
"""

from .scripting import ExperimentContext
from .scripting import Sample

__all__ = [
    "ExperimentContext",
    "Sample",
]
