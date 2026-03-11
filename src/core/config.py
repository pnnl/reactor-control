"""Configuration settings for reactor control system.

Loads device configuration from config/device_config.yaml.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

import yaml


# Config file path
CONFIG_DIR = Path(__file__).parent.parent.parent / "config"
DEVICE_CONFIG_FILE = CONFIG_DIR / "device_config.yaml"


@dataclass
class DeviceConfig:
    """Configuration settings for reactor hardware devices."""

    # Mass Flow Controller settings
    mfc_ports: List[str] = field(default_factory=lambda: ["COM4", "COM5"])
    mfc_baudrate: int = 9600
    mfc_timeout: float = 2.0

    # MFC Full Scale Settings (SCCM)
    mfc_full_scale_sccm: Dict[str, float] = field(
        default_factory=lambda: {"COM4": 200.0, "COM5": 200.0}
    )

    # Temperature Controller (Watlow PM Plus) settings
    tc_port: str = "COM6"
    tc_baudrate: int = 9600
    tc_timeout: float = 1.0
    tc_slave_id: int = 1
    tc_safe_temperature_c: float = 120.0

    # HPLC Pump settings
    hplc_port: str = "COM8"
    hplc_baudrate: int = 9600
    hplc_timeout: float = 2.0
    hplc_command_delay: float = 2.0

    # Omega CN7600 Temperature Controller settings
    omega_port: str = "COM10"
    omega_baudrate: int = 9600
    omega_timeout: float = 1.0
    omega_slave_id: int = 1
    omega_safe_temperature_c: float = 15.0

    # MKS ToolWEB settings
    mks_toolweb_host: str = "127.0.0.1"
    mks_toolweb_port: int = 80
    mks_toolweb_base_path: str = "/ToolWeb"
    mks_toolweb_sub_sensor: str = ""
    mks_toolweb_timeout: float = 2.0
    mks_toolweb_default_recipe: str = "Diesel 1Hz R4"

    # Gas routing map
    gas_routing_map: Dict[str, Dict[str, int | str]] = field(
        default_factory=lambda: {
            "nh3": {"device": "mfc", "port": "COM4", "channel": 1},
            "h2": {"device": "mfc", "port": "COM4", "channel": 2},
            "o2": {"device": "mfc", "port": "COM4", "channel": 3},
            "n2": {"device": "mfc", "port": "COM4", "channel": 4},
            "no": {"device": "mfc", "port": "COM5", "channel": 3},
            "h2o": {"device": "hplc"},
        }
    )

    # General settings
    connection_retry_attempts: int = 3
    connection_retry_delay: float = 1.0

    # MG2000 configuration (for ToolWEB)
    mg2000_ini_path: str = "C:\\OLT\\MG2000_SETUP.INI"
    mg2000_mgrcp_path: str = "C:\\OLT\\MG2000_last_used_recipe.MGRCP"
    mg2000_addins_dir: str = "C:\\OLT\\ADDINS"


def _load_device_config() -> Dict[str, Any]:
    """Load device configuration from YAML file."""
    if not DEVICE_CONFIG_FILE.exists():
        raise FileNotFoundError(f"Config file not found: {DEVICE_CONFIG_FILE}")

    with open(DEVICE_CONFIG_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def reload_config() -> None:
    """Force reload of configuration from YAML file.

    Useful for testing or when the YAML file has been modified.
    """
    global _config_data
    _config_data = _load_device_config()


def _create_config_from_data(data: Dict[str, Any]) -> DeviceConfig:
    """Create DeviceConfig from YAML data.

    Args:
        data: Dictionary loaded from YAML config file

    Returns:
        DeviceConfig instance
    """
    # Get default values
    default_config = DeviceConfig()

    # Override with YAML values where present
    return DeviceConfig(
        mfc_ports=data.get("mfc_ports", default_config.mfc_ports),
        mfc_baudrate=data.get("mfc_baudrate", default_config.mfc_baudrate),
        mfc_timeout=data.get("mfc_timeout", default_config.mfc_timeout),
        mfc_full_scale_sccm=data.get(
            "mfc_full_scale_sccm", default_config.mfc_full_scale_sccm
        ),
        tc_port=data.get("tc_port", default_config.tc_port),
        tc_baudrate=data.get("tc_baudrate", default_config.tc_baudrate),
        tc_timeout=data.get("tc_timeout", default_config.tc_timeout),
        tc_slave_id=data.get("tc_slave_id", default_config.tc_slave_id),
        tc_safe_temperature_c=data.get(
            "tc_safe_temperature_c", default_config.tc_safe_temperature_c
        ),
        hplc_port=data.get("hplc_port", default_config.hplc_port),
        hplc_baudrate=data.get("hplc_baudrate", default_config.hplc_baudrate),
        hplc_timeout=data.get("hplc_timeout", default_config.hplc_timeout),
        hplc_command_delay=data.get(
            "hplc_command_delay", default_config.hplc_command_delay
        ),
        omega_port=data.get("omega_port", default_config.omega_port),
        omega_baudrate=data.get("omega_baudrate", default_config.omega_baudrate),
        omega_timeout=data.get("omega_timeout", default_config.omega_timeout),
        omega_slave_id=data.get("omega_slave_id", default_config.omega_slave_id),
        omega_safe_temperature_c=data.get(
            "omega_safe_temperature_c", default_config.omega_safe_temperature_c
        ),
        mks_toolweb_host=data.get("mks_toolweb_host", default_config.mks_toolweb_host),
        mks_toolweb_port=data.get("mks_toolweb_port", default_config.mks_toolweb_port),
        mks_toolweb_base_path=data.get(
            "mks_toolweb_base_path", default_config.mks_toolweb_base_path
        ),
        mks_toolweb_sub_sensor=data.get(
            "mks_toolweb_sub_sensor", default_config.mks_toolweb_sub_sensor
        ),
        mks_toolweb_timeout=data.get(
            "mks_toolweb_timeout", default_config.mks_toolweb_timeout
        ),
        mks_toolweb_default_recipe=data.get(
            "mks_toolweb_default_recipe", default_config.mks_toolweb_default_recipe
        ),
        gas_routing_map=data.get("gas_routing_map", default_config.gas_routing_map),
        connection_retry_attempts=data.get(
            "connection_retry_attempts", default_config.connection_retry_attempts
        ),
        connection_retry_delay=data.get(
            "connection_retry_delay", default_config.connection_retry_delay
        ),
        mg2000_ini_path=data.get("mg2000_ini_path", default_config.mg2000_ini_path),
        mg2000_mgrcp_path=data.get(
            "mg2000_mgrcp_path", default_config.mg2000_mgrcp_path
        ),
        mg2000_addins_dir=data.get(
            "mg2000_addins_dir", default_config.mg2000_addins_dir
        ),
    )


# Load config at module import
_config_data: Dict[str, Any] = _load_device_config()

# Default configuration instance - loads from YAML
default_config = _create_config_from_data(_config_data)
