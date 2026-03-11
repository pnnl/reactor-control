"""HPLC Pump implementation using SSI Serial Pump Control protocol."""

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


class HPLCPump(SerialDevice):
    """Communication protocol for HPLC pumps with SSI Serial Pump Control.

    Supports Series 3 pumps with 1K buffer and standard communication protocol.
    Uses 9600 baud, 8-N-1, with command termination and acknowledgments.
    """

    def __init__(
        self,
        port: Optional[str] = None,
        config: Union[DeviceConfig, None] = None,
    ):
        """Initialize HPLC pump device.

        Args:
            port: Serial port name (e.g., 'COM8')
            config: Device configuration, uses default if None
        """
        config = config or default_config
        resolved_port = port or config.hplc_port
        super().__init__(resolved_port, config, baudrate=config.hplc_baudrate)
        self.command_delay = getattr(config, "hplc_command_delay", 1.0)
        self.terminator = "\r"  # Standard CR termination

    def connect(self) -> bool:
        """Establish connection to HPLC pump.

        Returns:
            True if connection successful and device responds, False otherwise
        """
        if not self._open_serial_connection():
            return False
        return True

    def disconnect(self) -> None:
        """Safely disconnect from HPLC pump."""
        # Send stop command before disconnect to ensure safe state
        if self.is_connected:
            self.stop_pump()
            time.sleep(self.command_delay)
        self._close_serial_connection()

    def send_command(self, command: str) -> Optional[str]:
        """Send command to HPLC pump and return response.

        Args:
            command: Command string to send

        Returns:
            Response string from device, or None if error
        """

        if not self.is_connected or not self.connection:
            self.logger.error("Not connected to HPLC pump")
            return None
        try:
            # Store current command for response parsing
            self._last_command = command

            # Send command with terminator
            full_command_bytes = (command + self.terminator).encode("ascii")
            self.connection.write(full_command_bytes)
            self.connection.flush()

            # Wait for response with timeout handling
            response = self._read_response()

            self._log_command(command, response)
            time.sleep(self.command_delay)  # Delay between commands

            return response

        except Exception as e:
            self.logger.error(f"Error sending command '{command}': {e}")
            return None

    def _read_response(self) -> Optional[str]:
        """Read response from pump, handling dual response pattern.

        The pump sends dual responses:
        - FM commands: 'OK/Er/' → return 'OK/'
        - CC commands: 'OK,data,Er/' → return 'OK,data/'
        - RU commands: 'OK,data,Er/' → return 'OK,data/'

        We take the complete response before the final 'Er/'.

        Returns:
            Complete response string ending with '/', or None if error/timeout
        """
        if not self.connection:
            return None

        try:
            response_buffer = ""
            start_time = time.time()
            timeout = getattr(self.config, "hplc_timeout", 2.0)

            while time.time() - start_time < timeout:
                if self.connection.in_waiting > 0:
                    # Read all available data at once
                    time.sleep(self.command_delay)  # Wait for full response
                    chunk = self.connection.read(self.connection.in_waiting)
                    chunk_str = chunk.decode("ascii", errors="ignore")
                    response_buffer += chunk_str

                    # Check if buffer starts with 'Er/' (leftover from previous command)
                    if response_buffer.startswith("Er/") and len(response_buffer) == 3:
                        # Just leftover 'Er/' from previous command, discard and continue
                        response_buffer = ""
                        time.sleep(0.01)
                        continue

                    # Look for pattern that ends with 'Er/' (final response)
                    elif response_buffer.endswith("Er/"):
                        # Dual response received - extract based on command type
                        full_response = response_buffer[:-3]  # Remove 'Er/'

                        if hasattr(self, "_last_command"):
                            cmd = self._last_command
                            # For flow commands (FM/FO), just return 'OK/'
                            if cmd.startswith(("FM", "FO")):
                                if full_response.startswith("OK/"):
                                    return "OK/"
                                else:
                                    return None  # Invalid response
                            # For data commands (CC/PI/RU), return the data part
                            elif cmd in ("CC", "PI", "RU"):
                                if (
                                    full_response.startswith("OK")
                                    and "/" in full_response
                                ):
                                    # Extract everything from 'OK' to first '/'
                                    return "OK" + full_response[2:].split("/")[0] + "/"
                                else:
                                    return None  # Invalid response
                            else:
                                # For other commands, return what we have before 'Er/'
                                return (
                                    full_response
                                    if full_response.endswith("/")
                                    else full_response + "/"
                                )

                        # Read and discard any remaining data to prevent contamination
                        time.sleep(0.01)
                        while self.connection.in_waiting > 0:
                            self.connection.read(self.connection.in_waiting)

                        return None

                    # If we have a complete response but no 'Er/' yet, return it
                    elif "/" in response_buffer:
                        # Return the part before first 'Er/' if present
                        if "Er/" in response_buffer:
                            parts = response_buffer.split("Er/")
                            return parts[0].strip()
                        else:
                            return response_buffer.strip()

            time.sleep(0.01)  # Small delay to prevent busy waiting

            # Timeout occurred
            if response_buffer:
                self.logger.warning(
                    f"Incomplete response (timeout): '{response_buffer}'"
                )
            else:
                self.logger.warning("No response received (timeout)")
            return None

        except Exception as e:
            self.logger.error(f"Error reading response: {e}")
            return None

    def run_pump(self) -> bool:
        """Start the pump.

        Returns:
            True if command successful, False otherwise
        """
        response = self.send_command("RU")
        if response and (response == "OK/" or response == "/"):
            self.logger.info("Pump started successfully")
            return True
        else:
            self.logger.error(f"Failed to start pump: '{response}'")
            return False

    def stop_pump(self) -> bool:
        """Stop the pump.

        Returns:
            True if command successful, False otherwise
        """
        response = self.send_command("ST")
        if response and (response == "OK/" or response == "/"):
            self.logger.info("Pump stopped successfully")
            return True
        else:
            self.logger.error(f"Failed to stop pump: '{response}'")
            return False

    def set_flow_rate(self, flow_rate_ml_min: float, microbore: bool = True) -> bool:
        """Set pump flow rate.

        Args:
            flow_rate_ml_min: Flow rate in ml/min

        Returns:
            True if command successful, False otherwise
        """
        if microbore:
            flow_rate_int = int(flow_rate_ml_min * 1000)
        else:
            flow_rate_int = int(flow_rate_ml_min * 100)

        if flow_rate_int > 9999:
            self.logger.error(f"Flow rate too high: {flow_rate_ml_min} ml/min")
            return False

        if microbore:
            command = f"FM{flow_rate_int:04d}"
        else:
            command = f"FO{flow_rate_int:04d}"
        response = self.send_command(command)

        if response and (response == "OK/" or response == "/"):
            self.logger.info(f"Flow rate set to {flow_rate_ml_min:.3f} ml/min")
            return True
        else:
            self.logger.error(f"Failed to set flow rate: '{response}'")
            return False

    def get_status(self) -> Optional[Dict[str, Union[str, int, float]]]:
        """Get comprehensive pump status.

        Returns:
            Dictionary with pump status information, or None if error
        """
        response = self.send_command("PI")
        if response and response.startswith("OK"):
            try:
                # Parse comma-delimited status response
                # Format: "OK flowrate,running,head_type,pressure_board,..."
                status_data = response[3:].rstrip("/")
                parts = [part.strip() for part in status_data.split(",")]

                status = {}
                if len(parts) >= 1:
                    status["flow_rate"] = float(parts[0])
                if len(parts) >= 2:
                    status["running"] = int(parts[1]) == 1
                if len(parts) >= 3:
                    status["head_type"] = int(parts[2])
                    head_types = {
                        1: "Stainless Steel 10ml",
                        2: "PEEK 10ml",
                        3: "Stainless Steel 40ml",
                        4: "PEEK 40ml",
                        5: "Stainless Steel 5ml",
                        6: "PEEK 5ml",
                    }
                    status["head_type_name"] = head_types.get(
                        status["head_type"], "Unknown"
                    )
                if len(parts) >= 4:
                    status["pressure_board"] = int(parts[3]) == 1
                if len(parts) >= 5:
                    status["external_voltage"] = int(parts[4]) == 1
                if len(parts) >= 6:
                    status["frequency_controlled"] = int(parts[5]) == 1
                if len(parts) >= 7:
                    status["voltage_controlled"] = int(parts[6]) == 1
                if len(parts) >= 8:
                    status["upper_pressure_fault"] = int(parts[7]) == 1
                if len(parts) >= 9:
                    status["under_pressure_fault"] = int(parts[8]) == 1
                if len(parts) >= 10:
                    status["priming"] = int(parts[9]) == 1
                if len(parts) >= 11:
                    status["keypad_lockout"] = int(parts[10]) == 1

                return status

            except (ValueError, IndexError) as e:
                self.logger.error(f"Failed to parse status: '{response}', error: {e}")
                return None
        else:
            self.logger.error(f"Failed to get status: '{response}'")
            return None

    def read_pressure_and_flow(self) -> Optional[Dict[str, float]]:
        """Get both pressure and flow rate in one command.

        Returns:
            Dictionary with 'pressure' and 'flow_rate' in ml/min and PSI, or None if error
        """
        response = self.send_command("CC")
        if response and response.startswith("OK"):
            try:
                # Format: "OK XXXX, XXX.X" where first is pressure, second is flow rate
                data = response[3:].rstrip("/")
                parts = [part.strip() for part in data.split(",")]

                if len(parts) >= 2:
                    pressure = float(parts[0])
                    flow_rate = float(parts[1])

                    return {"pressure": pressure, "flow_rate": flow_rate}
                else:
                    self.logger.error(
                        f"Invalid flow/pressure response format: '{response}'"
                    )
                    return None

            except (ValueError, IndexError) as e:
                self.logger.error(
                    f"Failed to parse flow/pressure: '{response}', error: {e}"
                )
                return None
        else:
            self.logger.error(f"Failed to get flow/pressure: '{response}'")
            return None
