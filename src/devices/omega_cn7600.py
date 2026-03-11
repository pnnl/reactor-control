"""Omega CN7600 Temperature Controller implementation."""

import sys
from pathlib import Path
from typing import Optional, Dict, Any

SRC_PATH = Path(__file__).resolve().parent.parent.parent
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from .base import ModbusDevice
from src.core.config import DeviceConfig, default_config


class OmegaCN7600(ModbusDevice):
    """Communication protocol for Omega CN7600 temperature controllers.

    Supports Modbus RTU/ASCII communication over RS-485 serial.
    Device uses 16-bit integer registers with 0.1 unit scaling for temperature.

    Implements P0 and P1 features:
    - P0: Connection, temperature reading, setpoint reading/write
    - P1: Control status, RUN/STOP, error handling, safe temperature
    """

    # Modbus register addresses (converted from hex to decimal)
    # Example: 1000H = 0x1000 = 4096 decimal
    REG_PROCESS_VALUE = 0x1000  # Process value (PV), unit 0.1, updates every 0.4s
    REG_SET_POINT = 0x1001  # Set point (SV), unit 0.1°C or °F, writable
    REG_SCALE_HIGH_LIMIT = 0x1002  # Upper limit of temperature range, unit 0.1
    REG_SCALE_LOW_LIMIT = 0x1003  # Lower limit of temperature range, unit 0.1
    REG_INPUT_SENSOR_TYPE = 0x1004  # Input temperature sensor type
    REG_CONTROL_METHOD = 0x1005  # Control method: 0=PID, 1=ON/OFF, 2=Manual, 3=Program
    REG_HEAT_COOL_SELECT = 0x1006  # Heat/Cool selection: 0=Heat, 1=Cool, 2=H1C2, 3=C1H2

    # LED status register
    REG_LED_STATUS = 0x102A  # Bit field: b0=Alm3, b1=Alm2, b2=F, b3=_, b4=Alm1, b5=OUT2, b6=OUT1, b7=AT

    # Setting lock status
    REG_SETTING_LOCK = 0x102C  # 0=Normal, 1=All lock, 11=Lock others than SV

    # Software version
    REG_SOFTWARE_VERSION = 0x102F  # V1.00 indicates 0x100

    # Bit registers
    BIT_REG_COMM_WRITE = 0x0810  # Communication write enable: 0=disabled, 1=enabled
    BIT_REG_TEMP_UNIT = 0x0811  # Temperature unit: 1=°C/default, 0=°F
    BIT_REG_DECIMAL_POS = 0x0812  # Decimal point position: 0 or 1 (not for B,S,R types)
    BIT_REG_AUTO_TUNE = 0x0813  # Auto-tune: 0=OFF, 1=ON
    BIT_REG_CONTROL_RUN_STOP = 0x0814  # Control RUN/STOP: 0=STOP, 1=RUN
    BIT_REG_PROGRAM_STOP = 0x0815  # Program STOP: 0=RUN, 1=STOP
    BIT_REG_PROGRAM_TEMP_STOP = 0x0816  # Program temp STOP: 0=RUN, 1=STOP

    # Error codes in PV register
    ERROR_INITIAL_PROCESS = 0x8002  # Initial process (temperature not yet available)
    ERROR_SENSOR_DISCONNECTED = 0x8003  # Temperature sensor not connected
    ERROR_SENSOR_INPUT_ERROR = 0x8004  # Temperature sensor input error
    ERROR_ADC_INPUT_ERROR = 0x8006  # Cannot get temperature value, ADC input error
    ERROR_MEMORY_ERROR = 0x8007  # Memory read/write error

    # Default temperature range validation (Celsius) - default Pt100 range
    DEFAULT_MIN_TEMP_C = 0.0
    DEFAULT_MAX_TEMP_C = 800.0

    # Valid 16-bit signed integer range for temperature values (in 0.1°C units)
    MIN_RAW_VALUE = -32768  # -3276.8°C
    MAX_RAW_VALUE = 32767  # 3276.7°C

    def __init__(
        self,
        port: str = "COM10",
        config: Optional[DeviceConfig] = None,
        slave_id: int = 1,
    ):
        """Initialize Omega CN7600 temperature controller.

        Args:
            port: Serial port name (e.g., 'COM9')
            config: Device configuration, uses default if None
            slave_id: Modbus slave ID (default: 1)
        """
        config = config or default_config
        super().__init__(
            port,
            config,
            baudrate=config.omega_baudrate,
            slave_id=slave_id if slave_id is not None else config.omega_slave_id,
        )
        self.safe_temperature_c = config.omega_safe_temperature_c

        # Temperature range limits - will be read from device on connection
        # Use default Pt100 range until device is connected
        self.min_temp_c = self.DEFAULT_MIN_TEMP_C
        self.max_temp_c = self.DEFAULT_MAX_TEMP_C
    
    def connect(self) -> bool:
        """Establish connection to Omega CN7600.

        Returns:
            True if connection successful, False otherwise
        """
        if not self._open_modbus_connection():
            return False

        self.logger.info(f"Omega CN7600 connected on {self.port}")
        return True

    def disconnect(self) -> None:
        """Disconnect from Omega CN7600."""
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
        """Read current process temperature from the temperature controller.

        Returns:
            Current temperature in °C, or None if error
        """
        registers = self._read_holding_registers(self.REG_PROCESS_VALUE, count=1)
        if registers is None:
            return None

        try:
            raw_value = registers[0]

            # Check for error codes
            if raw_value == self.ERROR_INITIAL_PROCESS:
                self.logger.warning("Temperature not yet available (initial process)")
                return None
            elif raw_value == self.ERROR_SENSOR_DISCONNECTED:
                self.logger.error("Temperature sensor not connected")
                return None
            elif raw_value == self.ERROR_SENSOR_INPUT_ERROR:
                self.logger.error("Temperature sensor input error")
                return None
            elif raw_value == self.ERROR_ADC_INPUT_ERROR:
                self.logger.error("ADC input error - cannot get temperature value")
                return None
            elif raw_value == self.ERROR_MEMORY_ERROR:
                self.logger.error("Memory read/write error")
                return None

            # Check if value is negative (signed 16-bit integer)
            if raw_value > 32767:
                raw_value -= 65536

            # Convert from 0.1 unit to actual temperature
            temperature_c = raw_value / 10.0

            # Validate temperature range
            if not (self.min_temp_c <= temperature_c <= self.max_temp_c):
                self.logger.warning(f"Temperature out of range: {temperature_c}°C")
                # Still return the value as it may be valid for different sensor types

            return temperature_c

        except (ValueError, IndexError, TypeError) as e:
            self.logger.error(f"Failed to parse temperature: {e}")
            return None

    def get_setpoint(self) -> Optional[float]:
        """Read the current temperature setpoint.

        Returns:
            Current setpoint in °C, or None if error
        """
        registers = self._read_holding_registers(self.REG_SET_POINT, count=1)
        if registers is None:
            return None

        try:
            raw_value = registers[0]

            # Check if value is negative (signed 16-bit integer)
            if raw_value > 32767:
                raw_value -= 65536

            # Convert from 0.1 unit to actual temperature
            setpoint_c = raw_value / 10.0

            # Validate temperature range
            if not (self.min_temp_c <= setpoint_c <= self.max_temp_c):
                self.logger.warning(f"Setpoint out of range: {setpoint_c}°C")
                # Still return as value as it may be valid for different sensor types

            return setpoint_c

        except (ValueError, IndexError, TypeError) as e:
            self.logger.error(f"Failed to parse setpoint: {e}")
            return None

    def set_setpoint(self, temperature_c: float) -> bool:
        """Set temperature setpoint on the temperature controller.

        Args:
            temperature_c: Desired temperature in °C

        Returns:
            True if successful, False otherwise
        """
        # Validate temperature
        if not (self.min_temp_c <= temperature_c <= self.max_temp_c):
            self.logger.error(
                f"Invalid temperature {temperature_c}°C. "
                f"Must be between {self.min_temp_c} and {self.max_temp_c}°C"
            )
            return False

        try:
            # Enable communication write if disabled
            write_enabled = self._read_bit_register(self.BIT_REG_COMM_WRITE)
            if write_enabled is None:
                self.logger.error("Failed to check communication write enable")
                return False

            if not write_enabled:
                self.logger.info("Enabling communication write...")
                if not self._write_bit_register(self.BIT_REG_COMM_WRITE, True):
                    self.logger.error("Failed to enable communication write")
                    return False

            # Convert to 0.1 unit and to integer
            raw_value = int(round(temperature_c * 10))

            # Clamp to valid signed 16-bit range to prevent overflow
            raw_value = max(self.MIN_RAW_VALUE, min(self.MAX_RAW_VALUE, raw_value))

            # Handle negative values for Modbus unsigned encoding
            if raw_value < 0:
                raw_value += 65536

            # Write setpoint
            success = self._write_registers(self.REG_SET_POINT, [raw_value])

            if success:
                self.logger.debug(f"Setpoint updated to {temperature_c}°C")
            else:
                self.logger.error("Failed to set setpoint")

            return success

        except (ValueError, TypeError, OverflowError) as e:
            self.logger.error(f"Failed to encode setpoint: {e}")
            return False

    def get_control_mode(self) -> Optional[int]:
        """Read the current control mode.

        Returns:
            Control mode code (0=PID, 1=ON/OFF, 2=Manual, 3=Program), or None if error
        """
        registers = self._read_holding_registers(self.REG_CONTROL_METHOD, count=1)
        if registers is None:
            return None

        try:
            mode = int(registers[0])
            valid_modes = {0: "PID", 1: "ON/OFF", 2: "Manual", 3: "Program"}
            if mode in valid_modes:
                return mode
            else:
                self.logger.warning(f"Unknown control mode: {mode}")
                return mode
        except (ValueError, IndexError) as e:
            self.logger.error(f"Failed to parse control mode: {e}")
            return None

    def get_control_status(self) -> Dict[str, Any]:
        """Read comprehensive control status.

        Returns:
            Dictionary with status information including:
            - running: bool (RUN/STOP status)
            - auto_tuning: bool (auto-tune in progress)
            - alarm_1: bool (alarm 1 active)
            - alarm_2: bool (alarm 2 active)
            - alarm_3: bool (alarm 3 active)
            - fault: bool (fault detected)
            - output_1_active: bool (output 1 active)
            - output_2_active: bool (output 2 active)
            - lock_status_code: int (raw lock status value)
            - lock_status: str (human-readable lock status description)
        """
        status: Dict[str, Any] = {}

        # Read RUN/STOP status
        running = self._read_bit_register(self.BIT_REG_CONTROL_RUN_STOP)
        status["running"] = running if running is not None else False

        # Read LED status (bit field)
        led_reg = self._read_holding_registers(self.REG_LED_STATUS, count=1)
        if led_reg is not None:
            led_bits = led_reg[0]
            status["alarm_3"] = bool(led_bits & 0x01)  # b0
            status["alarm_2"] = bool(led_bits & 0x02)  # b1
            status["fault"] = bool(led_bits & 0x04)  # b2
            status["alarm_1"] = bool(led_bits & 0x10)  # b4
            status["output_2_active"] = bool(led_bits & 0x20)  # b5
            status["output_1_active"] = bool(led_bits & 0x40)  # b6
            status["auto_tuning"] = bool(led_bits & 0x80)  # b7
        else:
            status["alarm_3"] = False
            status["alarm_2"] = False
            status["fault"] = False
            status["alarm_1"] = False
            status["output_2_active"] = False
            status["output_1_active"] = False
            status["auto_tuning"] = False

        # Read lock status
        lock_reg = self._read_holding_registers(self.REG_SETTING_LOCK, count=1)
        if lock_reg is not None:
            lock_code = int(lock_reg[0])
            status["lock_status_code"] = lock_code

            # Map lock status codes to human-readable descriptions
            lock_status_map = {
                0: "Normal",
                1: "All settings locked",
                11: "Lock except setpoint",  # As per manual: "Lock others than SV"
            }
            status["lock_status"] = lock_status_map.get(
                lock_code, f"Unknown ({lock_code})"
            )
        else:
            status["lock_status_code"] = 0
            status["lock_status"] = "Normal"

        return status

    def set_control_run(self, run: bool) -> bool:
        """Set control RUN (True) or STOP (False).

        Args:
            run: True to start control, False to stop control

        Returns:
            True if successful, False otherwise
        """
        return self._write_bit_register(self.BIT_REG_CONTROL_RUN_STOP, run)

    def get_error_status(self) -> Optional[str]:
        """Read error status from process value register.

        Returns:
            Error description string, or None if no error
        """
        registers = self._read_holding_registers(self.REG_PROCESS_VALUE, count=1)
        if registers is None:
            return None

        try:
            raw_value = registers[0]

            if raw_value == self.ERROR_INITIAL_PROCESS:
                return "Initial process - temperature not yet available"
            elif raw_value == self.ERROR_SENSOR_DISCONNECTED:
                return "Temperature sensor not connected"
            elif raw_value == self.ERROR_SENSOR_INPUT_ERROR:
                return "Temperature sensor input error"
            elif raw_value == self.ERROR_ADC_INPUT_ERROR:
                return "ADC input error - cannot get temperature value"
            elif raw_value == self.ERROR_MEMORY_ERROR:
                return "Memory read/write error"
            else:
                return None

        except (ValueError, IndexError) as e:
            self.logger.error(f"Failed to parse error status: {e}")
            return None

    def set_safe_temperature(self) -> bool:
        """Set temperature to safe fallback value.

        This is useful when an error is detected to return the system
        to a known safe state.

        Returns:
            True if successful, False otherwise
        """
        return self.set_setpoint(self.safe_temperature_c)

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
            info["control_mode"] = self.get_control_mode()
            info["control_status"] = self.get_control_status()
            info["error_status"] = self.get_error_status()
            info["safe_temperature_c"] = self.safe_temperature_c

        return info

    def _read_temperature_range(self) -> None:
        """Read temperature range limits from device registers.

        Updates min_temp_c and max_temp_c instance variables with actual
        device limits. Falls back to default values if read fails.
        """
        # Read scale high limit
        high_reg = self._read_holding_registers(self.REG_SCALE_HIGH_LIMIT, count=1)
        # Read scale low limit
        low_reg = self._read_holding_registers(self.REG_SCALE_LOW_LIMIT, count=1)

        if high_reg is not None and low_reg is not None:
            try:
                # Convert from 0.1 unit to actual temperature
                raw_high = high_reg[0]
                raw_low = low_reg[0]

                # Handle negative values
                if raw_high > 32767:
                    raw_high -= 65536
                if raw_low > 32767:
                    raw_low -= 65536

                self.max_temp_c = raw_high / 10.0
                self.min_temp_c = raw_low / 10.0

                self.logger.debug(
                    f"Temperature range read from device: "
                    f"{self.min_temp_c} to {self.max_temp_c}°C"
                )
            except (ValueError, TypeError) as e:
                self.logger.warning(
                    f"Failed to parse temperature range from device: {e}. "
                    f"Using default range: {self.DEFAULT_MIN_TEMP_C} to {self.DEFAULT_MAX_TEMP_C}°C"
                )
                self.min_temp_c = self.DEFAULT_MIN_TEMP_C
                self.max_temp_c = self.DEFAULT_MAX_TEMP_C
        else:
            self.logger.warning(
                "Failed to read temperature range from device. "
                f"Using default range: {self.DEFAULT_MIN_TEMP_C} to {self.DEFAULT_MAX_TEMP_C}°C"
            )
    
    def _read_bit_register(self, address: int) -> Optional[bool]:
        """Read a single bit from a bit register.

        Args:
            address: Bit register address

        Returns:
            Bit value (True/False), or None if error
        """
        # Use function code 02H to read bits (coils)
        # Omega CN7600 bit registers (0810H-0816H) must be read via coils
        bits = self._read_coils(address, count=1)
        if bits is None or len(bits) == 0:
            return None

        try:
            return bits[0]
        except (IndexError, TypeError) as e:
            self.logger.error(f"Failed to parse bit register: {e}")
            return None

    def _write_bit_register(self, address: int, value: bool) -> bool:
        """Write a single bit to a bit register.

        Args:
            address: Bit register address
            value: Bit value to write (True/False)

        Returns:
            True if successful, False otherwise
        """
        # Use function code 05H to write single bit (coil)
        # Omega CN7600 bit registers must be written via coils, not holding registers
        return self._write_coil(address, value)