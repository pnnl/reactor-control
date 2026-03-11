"""Watlow PM Plus Temperature Controller implementation."""

from typing import Optional, Dict, Any
import struct

from .base import ModbusDevice
from core.config import DeviceConfig, default_config


class WatlowPMPlus(ModbusDevice):
    """Communication protocol for Watlow PM Plus temperature controllers.

    Supports Modbus RTU communication over RS-232 serial.
    Device stores temperatures in Fahrenheit internally; API uses Celsius.
    """

    # Modbus register addresses
    REG_CURRENT_TEMP = 360  # Current process temperature (32-bit float)
    REG_SET_TEMP = 2160  # Temperature setpoint (32-bit float, writable)
    REG_READ_SET_TEMP = 2172  # Read current setpoint (32-bit float)
    REG_ERROR_CODE = 362  # Error code register (16-bit int)

    # Temperature range validation (Celsius)
    MIN_TEMP_C = 0.0
    MAX_TEMP_C = 1000.0

    def __init__(
        self,
        port: str,
        config: Optional[DeviceConfig] = None,
        slave_id: int = 1,
    ):
        """Initialize Watlow PM Plus temperature controller.

        Args:
            port: Serial port name (e.g., 'COM6')
            config: Device configuration, uses default if None
            slave_id: Modbus slave ID (default: 1)
        """
        config = config or default_config
        super().__init__(
            port,
            config,
            baudrate=config.tc_baudrate,
            slave_id=slave_id if slave_id is not None else config.tc_slave_id,
        )
        self.safe_temperature_c = config.tc_safe_temperature_c

    def connect(self) -> bool:
        """Establish connection to Watlow PM Plus.

        Returns:
            True if connection successful, False otherwise
        """
        if not self._open_modbus_connection():
            return False

        # Test connection by reading temperature register
        temp = self.get_temperature()
        if temp is not None:
            self.logger.info(
                f"Watlow PM Plus connected on {self.port}, current temp: {temp}°C"
            )
            return True
        else:
            self.logger.warning(f"Watlow PM Plus connection test failed on {self.port}")
            return False

    def disconnect(self) -> None:
        """Disconnect from Watlow PM Plus."""
        self._close_modbus_connection()

    def send_command(self, command: str) -> Optional[str]:
        """Send command to device (not applicable for Modbus devices).

        This method is required by the base class but not used for Modbus RTU.
        Modbus devices use register read/write operations instead.

        Args:
            command: Command string (ignored)

        Returns:
            None (not implemented for Modbus devices)
        """
        self.logger.warning("send_command() not applicable for Modbus RTU devices")
        return None

    def get_temperature(self) -> Optional[float]:
        """Read current temperature from the temperature controller.

        Returns:
            Current temperature in Celsius, or None if error
        """
        registers = self._read_holding_registers(self.REG_CURRENT_TEMP, count=2)
        if registers is None:
            return None

        try:
            # Convert 2 registers to 32-bit float (big-endian)
            # Watlow stores floats as big-endian across 2 registers
            registers_bytes = struct.pack(">HH", registers[1], registers[0])
            temperature_c = struct.unpack(">f", registers_bytes)[0]
            # temperature_c = round(self._fahrenheit_to_celsius(temperature_f), 1)

            # # Validate temperature range
            # if not (self.MIN_TEMP_C < temperature_c < self.MAX_TEMP_C):
            #     self.logger.error(f"Temperature out of range: {temperature_c}°C")
            #     # Check for error code
            #     error_code = self.get_error_code()
            #     if error_code:
            #         self.logger.error(f"Error code: {error_code}")
            #     return None

            return temperature_c

        except (struct.error, IndexError, ValueError) as e:
            self.logger.error(f"Failed to parse temperature: {e}")
            return None

    def set_temperature(self, temperature_c: float) -> bool:
        """Set temperature setpoint on the temperature controller.
        Args:
            temperature_c: Desired temperature in Celsius
        Returns:
            True if successful, False otherwise
        """
        # Validate temperature
        # (The user manual indicates the range is -1128 to 5537°C for setpoints)
        if not (-200 < temperature_c < 800):  # Using a more practical RTD range
            self.logger.error(f"Invalid temperature {temperature_c}°C.")
            return False
        try:
            # Encode as 32-bit float (big-endian)
            data_bytes = struct.pack(">f", temperature_c)
            reg_hi, reg_lo = struct.unpack(">HH", data_bytes)

            # CORRECTED: Write registers in high-then-low order (no swap)
            success = self._write_registers(self.REG_SET_TEMP, [reg_hi, reg_lo])

            if success:
                self.logger.info(f"Temperature setpoint updated to {temperature_c}°C")
            else:
                self.logger.error("Failed to set temperature setpoint.")
            return success
        except (struct.error, ValueError) as e:
            self.logger.error(f"Failed to encode temperature: {e}")
            return False

    def get_setpoint(self) -> Optional[float]:
        """Read the current temperature setpoint.

        Returns:
            Current setpoint in Celsius, or None if error
        """
        registers = self._read_holding_registers(self.REG_READ_SET_TEMP, count=2)
        if registers is None:
            return None

        try:
            # Convert 2 registers to 32-bit float (big-endian)
            registers_bytes = struct.pack(">HH", registers[1], registers[0])
            setpoint_f = struct.unpack(">f", registers_bytes)[0]
            setpoint_c = round(self._fahrenheit_to_celsius(setpoint_f), 1)

            # Validate temperature range
            if not (self.MIN_TEMP_C < setpoint_c < self.MAX_TEMP_C):
                self.logger.error(f"Setpoint out of range: {setpoint_c}°C")
                return None

            return setpoint_c

        except (struct.error, IndexError, ValueError) as e:
            self.logger.error(f"Failed to parse setpoint: {e}")
            return None

    def get_error_code(self) -> Optional[int]:
        """Read the error code from the temperature controller.

        Returns:
            Error code as integer, or None if error
        """
        registers = self._read_holding_registers(self.REG_ERROR_CODE, count=1)
        if registers is None:
            return None

        try:
            return int(registers[0])
        except (ValueError, IndexError) as e:
            self.logger.error(f"Failed to parse error code: {e}")
            return None

    def set_safe_temperature(self) -> bool:
        """Set temperature to safe fallback value.

        This is useful when an error is detected to return the system
        to a known safe state.

        Returns:
            True if successful, False otherwise
        """
        return self.set_temperature(self.safe_temperature_c)

    def _fahrenheit_to_celsius(self, fahrenheit: float) -> float:
        """Convert Fahrenheit to Celsius.

        Args:
            fahrenheit: Temperature in Fahrenheit

        Returns:
            Temperature in Celsius
        """
        return (fahrenheit - 32.0) * 5.0 / 9.0

    def _celsius_to_fahrenheit(self, celsius: float) -> float:
        """Convert Celsius to Fahrenheit.

        Args:
            celsius: Temperature in Celsius

        Returns:
            Temperature in Fahrenheit
        """
        return (celsius * 9.0 / 5.0) + 32.0

    def get_device_info(self) -> Dict[str, Any]:
        """Get device information and current status.

        Returns:
            Dictionary containing device information and status
        """
        info = {
            "port": self.port,
            "slave_id": self.slave_id,
            "is_connected": self.is_connected,
        }

        if self.is_connected:
            info["current_temperature_c"] = self.get_temperature()
            info["setpoint_c"] = self.get_setpoint()
            info["error_code"] = self.get_error_code()
            info["safe_temperature_c"] = self.safe_temperature_c

        return info
