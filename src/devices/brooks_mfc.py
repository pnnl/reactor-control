"""Brooks Mass Flow Controller implementation."""

from typing import Optional, Dict, Union
import logging
import time
import sys
from pathlib import Path

SRC_PATH = Path(__file__).resolve().parent.parent.parent
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from .base import SerialDevice
from src.core.config import DeviceConfig, default_config

logger = logging.getLogger(__name__)


class BrooksMFC(SerialDevice):
    """Communication protocol for Brooks Mass Flow Controllers.

    Supports RS-232 communication with plain command protocol.
    """

    def __init__(
        self,
        port: Optional[str] = None,
        config: Union[DeviceConfig, None] = None,
    ):
        """Initialize Brooks MFC device.

        Args:
            port: Serial port name (e.g., 'COM4')
            config: Device configuration, uses default if None
        """
        config = config or default_config
        resolved_port = port or (config.mfc_ports[0] if config.mfc_ports else "COM4")
        super().__init__(resolved_port, config, baudrate=config.mfc_baudrate)
        self.terminator = "\r"  # CR only as discovered

    def connect(self) -> bool:
        """Establish connection to Brooks MFC.

        Returns:
            True if connection successful and device identified, False otherwise
        """
        if not self._open_serial_connection():
            return False

        # Test connection by sending identification request
        response = self.send_command("azi")
        if response and response.startswith("AZ,"):
            # self.logger.info(f"Brooks MFC identified on {self.port}: {response}")
            return True
        else:
            self.logger.warning(f"Brooks MFC identification failed on {self.port}")
            return False

    def disconnect(self) -> None:
        """Disconnect from Brooks MFC."""
        self._close_serial_connection()

    def send_command(self, command: str) -> Optional[str]:
        """Send command to Brooks MFC and return response.

        Args:
            command: Command string

        Returns:
            Response string from device, or None if error
        """
        if not self.is_connected or not self.connection:
            self.logger.error("Not connected to MFC")
            return None

        return self._send_serial_command(command, self.terminator)

    def get_percent_open(self, channel: int = 1) -> Optional[float]:
        """Get current percent open from MFC.

        Args:
            channel: MFC channel number (1-4, default: 1)

        Returns:
            Current percent open (0-100), or None if error
        """
        if not 1 <= channel <= 4:
            self.logger.error(f"Invalid channel: {channel} (must be 1-4)")
            return None

        input_port = 2 * channel - 1
        response = self.send_command(f"az.{input_port}k")
        if response and response.startswith("AZ,"):
            parts = response.split(",")
            if len(parts) > 5:
                try:
                    percent_open = float(parts[5].strip())
                    return percent_open
                except (ValueError, IndexError) as e:
                    self.logger.error(f"Failed to parse percent open: {e}")
            self.logger.error(f"Invalid response format: '{response}'")
            return None
        self.logger.error(f"Invalid percent open response: '{response}'")
        return None

    def set_flow_rate(self, flow_rate: float, channel: int = 1) -> bool:
        """Set flow rate on MFC.

        Args:
            flow_rate: Desired flow rate percentage (0-100)
            channel: MFC channel number (1-4, default: 1)

        Returns:
            True if command successful, False otherwise
        """
        if not 1 <= channel <= 4:
            self.logger.error(f"Invalid channel: {channel} (must be 1-4)")
            return False

        if not 0 <= flow_rate <= 100:
            self.logger.error(f"Invalid flow rate: {flow_rate} (must be 0-100)")
            return False

        output_port = 2 * channel
        write_value = round(flow_rate, 1)
        command = f"az.{output_port}p1={write_value:.1f}"
        response = self.send_command(command)
        if not response or not response.startswith("AZ,"):
            self.logger.error(f"Set flow rate failed: '{response}'")
            return False

        self.logger.info(
            f"Set flow rate to {flow_rate:.1f}% on channel {channel} successfully."
        )

        # Set valve override based on flow rate
        vor_value = 1 if flow_rate <= 1 else 0
        vor_command = f"az.{output_port}p29={vor_value}"
        vor_response = self.send_command(vor_command)
        if not vor_response or not vor_response.startswith("AZ,"):
            self.logger.error(f"Set valve override failed: '{vor_response}'")
            return False

        self.logger.info(
            f"Set valve override to {'closed' if vor_value == 1 else 'normal'} on channel {channel}"
        )

        return True

    def get_device_info(self) -> Dict[str, str]:
        """Get device information from MFC.

        Returns:
            Dictionary containing device information
        """
        info = {}

        response = self.send_command("azi")
        if response and response.startswith("AZ,"):
            parts = [p.strip() for p in response.split(",")]
            if len(parts) >= 6:
                info["response_type"] = parts[0]
                info["serial_number"] = parts[1]
                info["address"] = parts[2]
                info["manufacturer"] = parts[3]
                info["model"] = parts[4]
                info["version_year"] = parts[5]
                if len(parts) >= 7:
                    info["firmware_version"] = parts[6]
                if len(parts) >= 8:
                    info["hardware_revision"] = parts[7]
                if len(parts) >= 9:
                    info["checksum"] = parts[8]

                self.logger.info(f"Device Info:")
                self.logger.info(f"  Manufacturer: {info['manufacturer']}")
                self.logger.info(f"  Model: {info['model']}")
                self.logger.info(f"  Serial Number: {info['serial_number']}")
                self.logger.info(f"  Firmware: {info.get('firmware_version', 'N/A')}")
                self.logger.info(f"  Address: {info['address']}")
            else:
                self.logger.error(f"Invalid device info format: '{response}'")
        else:
            self.logger.error(f"Failed to get device info: '{response}'")

        return info
