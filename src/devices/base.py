"""Base classes for device communication protocols."""

from abc import ABC, abstractmethod
from typing import Optional
import logging
import time
import sys
from pathlib import Path

SRC_PATH = Path(__file__).resolve().parent.parent.parent
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from src.core.config import DeviceConfig

# Set up basic logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class CommunicationProtocol(ABC):
    """Abstract base class for all hardware communication protocols."""

    def __init__(self, port: str, config: DeviceConfig):
        """Initialize the communication protocol.

        Args:
            port: Serial port name (e.g., 'COM4')
            config: Device configuration settings
        """
        self.port = port
        self.config = config
        self.is_connected = False
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to hardware.

        Returns:
            True if connection successful, False otherwise
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Close connection to hardware."""
        pass

    @abstractmethod
    def send_command(self, command: str) -> Optional[str]:
        """Send command to device and return response.

        Args:
            command: Command string to send

        Returns:
            Response string from device, or None if error
        """
        pass

    def _wait_between_attempts(self, delay: Optional[float] = None) -> None:
        """Wait between retry attempts.

        Args:
            delay: Wait time in seconds, defaults to config setting
        """
        if delay is None:
            delay = self.config.connection_retry_delay
        time.sleep(delay)

    def _log_connection_attempt(self, success: bool) -> None:
        """Log connection attempt result.

        Args:
            success: Whether connection was successful
        """
        if success:
            self.logger.info(f"Successfully connected to {self.port}")
        else:
            self.logger.error(f"Failed to connect to {self.port}")

    def _log_command(self, command: str, response: Optional[str] = None) -> None:
        """Log command and response.

        Args:
            command: Command that was sent
            response: Response received (if any)
        """
        self.logger.debug(f"Command: {command}")
        if response:
            self.logger.debug(f"Response: {response}")
        elif response is None:
            self.logger.warning(f"No response to command: {command}")


class SerialDevice(CommunicationProtocol):
    """Base class for serial communication devices."""

    def __init__(self, port: str, config: DeviceConfig, baudrate: Optional[int] = None):
        """Initialize serial device.

        Args:
            port: Serial port name
            config: Device configuration
            baudrate: Serial baud rate (overrides config if provided)
        """
        super().__init__(port, config)
        self.baudrate = baudrate if baudrate is not None else config.mfc_baudrate
        self.connection = None

    def _open_serial_connection(self) -> bool:
        """Open serial connection with retry logic.

        Returns:
            True if connection successful, False otherwise
        """
        import serial

        for attempt in range(self.config.connection_retry_attempts):
            try:
                self.connection = serial.Serial(
                    port=self.port,
                    baudrate=self.baudrate,
                    timeout=self.config.mfc_timeout
                    if hasattr(self.config, "mfc_timeout")
                    else self.config.connection_retry_delay,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                )

                # Give connection time to stabilize
                time.sleep(0.1)
                self.is_connected = True
                self._log_connection_attempt(True)
                return True

            except serial.SerialException as e:
                self.logger.error(f"Connection attempt {attempt + 1} failed: {e}")
                if attempt < self.config.connection_retry_attempts - 1:
                    self._wait_between_attempts()
                else:
                    self._log_connection_attempt(False)
                    return False

        return False

    def _close_serial_connection(self) -> None:
        """Close serial connection."""
        if self.connection and self.connection.is_open:
            self.connection.close()
            self.is_connected = False
            self.logger.info(f"Disconnected from {self.port}")

    def _send_serial_command(
        self, command: str, terminator: str = "\r\n"
    ) -> Optional[str]:
        """Send command via serial connection.

        Args:
            command: Command to send
            terminator: Command terminator string

        Returns:
            Response from device, or None if error
        """
        if not self.is_connected or not self.connection:
            self.logger.error("Not connected to device")
            return None

        try:
            # Send command
            full_command = command + terminator
            self.connection.write(full_command.encode("ascii"))
            self.connection.flush()

            # Read response
            response = self.connection.readline().decode("ascii").strip()
            self._log_command(command, response)
            return response

        except Exception as e:
            self.logger.error(f"Error sending command '{command}': {e}")
            return None


class ModbusDevice(CommunicationProtocol):
    """Base class for Modbus RTU devices."""

    def __init__(
        self,
        port: str,
        config: DeviceConfig,
        baudrate: int = 9600,
        slave_id: int = 1,
    ):
        """Initialize Modbus device.

        Args:
            port: Serial port name (e.g., 'COM6')
            config: Device configuration settings
            baudrate: Serial baud rate (default: 9600)
            slave_id: Modbus slave ID (default: 1)
        """
        super().__init__(port, config)
        self.baudrate = baudrate
        self.slave_id = slave_id
        self.client = None

    def _open_modbus_connection(self) -> bool:
        """Open Modbus RTU serial connection with retry logic.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            from pymodbus.client import ModbusSerialClient
        except ImportError as e:
            self.logger.error(f"pymodbus not installed: {e}")
            return False

        for attempt in range(self.config.connection_retry_attempts):
            try:
                self.client = ModbusSerialClient(
                    port=self.port,
                    baudrate=self.baudrate,
                    timeout=getattr(
                        self.config, "tc_timeout", self.config.connection_retry_delay
                    ),
                    bytesize=8,
                    parity="N",
                    stopbits=1,
                )

                if self.client.connect():
                    # Give connection time to stabilize
                    time.sleep(0.1)
                    self.is_connected = True
                    self._log_connection_attempt(True)
                    return True
                else:
                    self.logger.error(f"Modbus connection attempt {attempt + 1} failed")
                    if attempt < self.config.connection_retry_attempts - 1:
                        self._wait_between_attempts()

            except Exception as e:
                self.logger.error(
                    f"Modbus connection attempt {attempt + 1} failed: {e}"
                )
                if attempt < self.config.connection_retry_attempts - 1:
                    self._wait_between_attempts()

        self._log_connection_attempt(False)
        return False

    def _close_modbus_connection(self) -> None:
        """Close Modbus connection."""
        if self.client and self.client.connected:
            self.client.close()
            self.is_connected = False
            self.logger.info(f"Disconnected from {self.port}")

    def _read_holding_registers(
        self, address: int, count: int = 1
    ) -> Optional[list[int]]:
        """Read holding registers from Modbus device.

        Args:
            address: Starting register address
            count: Number of registers to read (default: 1)

        Returns:
            List of register values, or None if error
        """
        if not self.is_connected or not self.client:
            self.logger.error("Not connected to Modbus device")
            return None

        try:
            result = self.client.read_holding_registers(address=address, count=count)
            if result.isError():
                self.logger.error(f"Modbus read error at address {address}: {result}")
                return None
            return result.registers
        except Exception as e:
            self.logger.error(f"Error reading registers: {e}")
            return None

    def _write_registers(self, address: int, values: list[int]) -> bool:
        """Write registers to Modbus device.

        Args:
            address: Starting register address
            values: List of values to write

        Returns:
            True if successful, False otherwise
        """
        if not self.is_connected or not self.client:
            self.logger.error("Not connected to Modbus device")
            return False

        try:
            result = self.client.write_registers(address=address, values=values)
            if result.isError():
                self.logger.error(f"Modbus write error at address {address}: {result}")
                return False
            return True
        except Exception as e:
            self.logger.error(f"Error writing registers: {e}")
            return False

    def _read_coils(self, address: int, count: int = 1) -> Optional[list[bool]]:
        """Read coils/bits from Modbus device using function code 02H.

        Args:
            address: Starting coil/bit address
            count: Number of coils/bits to read (default: 1)

        Returns:
            List of boolean coil values, or None if error
        """
        if not self.is_connected or not self.client:
            self.logger.error("Not connected to Modbus device")
            return None

        try:
            result = self.client.read_coils(address=address, count=count)
            if result.isError():
                self.logger.error(
                    f"Modbus coil read error at address {address}: {result}"
                )
                return None
            return result.bits[:count]
        except Exception as e:
            self.logger.error(f"Error reading coils: {e}")
            return None

    def _write_coil(self, address: int, value: bool) -> bool:
        """Write single coil/bit to Modbus device using function code 05H.

        Args:
            address: Coil/bit address
            value: Boolean value to write

        Returns:
            True if successful, False otherwise
        """
        if not self.is_connected or not self.client:
            self.logger.error("Not connected to Modbus device")
            return False

        try:
            result = self.client.write_coil(address=address, value=value)
            if result.isError():
                self.logger.error(
                    f"Modbus coil write error at address {address}: {result}"
                )
                return False
            return True
        except Exception as e:
            self.logger.error(f"Error writing coil: {e}")
            return False
