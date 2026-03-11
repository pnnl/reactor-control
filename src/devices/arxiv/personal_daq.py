"""Personal DAQ/56 Data Acquisition Device implementation.

Implements minimal "read one temperature" feature using vendor's
pdaqx.dll (PDAQX.DLL) API via ctypes.

Implementation based on hardware manual: personalDAQ_plus.md
"""

from typing import Optional
import ctypes
import logging

from .base import CommunicationProtocol
from core.config import DeviceConfig, default_config


# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(f"{__name__}.{__name__}")


# ============================================================================
# DLL and Data Type Definitions
# ============================================================================

# Global DLL handle (will be loaded in PersonalDAQ.__init__)
dll = None

# Define Windows data types
DWORD = ctypes.c_ulong
PDWORD = ctypes.c_ulong
PFLOAT = ctypes.c_float
BOOL = ctypes.c_int


# ============================================================================
# API Function Prototypes
# ============================================================================


def _load_dll(dll_path: str) -> ctypes.WinDLL:
    """Load the Personal DAQ DLL from specified path.

    Args:
        dll_path: Full path to pdaqx.dll (typically C:\\Windows\\System32\\pdaqx.dll)

    Returns:
        ctypes.WinDLL handle, or raises RuntimeError if loading fails

    Raises:
        RuntimeError: If DLL cannot be loaded
    """
    try:
        dll = ctypes.WinDLL(dll_path)
        logger.info(f"Successfully loaded Personal DAQ DLL: {dll_path}")
        return dll
    except OSError as e:
        logger.error(f"Failed to load DLL from {dll_path}: {e}")
        logger.error("Ensure Personal DAQ driver is installed and DLL exists")
        raise RuntimeError(f"Failed to load {dll_path}")


def _declare_prototypes(dll_handle: ctypes.WinDLL) -> None:
    """Declare all DLL function prototypes.

    Args:
        dll_handle: Loaded ctypes WinDLL handle
    """
    # --- Device Initialization Functions ---
    dll_handle.daqOpen.argtypes = [ctypes.c_char_p]
    dll_handle.daqOpen.restype = ctypes.POINTER(DaHandleT)

    dll_handle.daqClose.argtypes = [DaHandleT]
    dll_handle.daqClose.restype = ctypes.c_ulong

    dll_handle.daqOnline.argtypes = [DaHandleT]
    dll_handle.daqOnline.restype = ctypes.c_int

    dll_handle.daqGetDeviceCount.argtypes = [DaHandleT]
    dll_handle.daqGetDeviceCount.restype = ctypes.c_int

    dll_handle.daqGetDeviceList.argtypes = [DaHandleT, ctypes.POINTER(PDWORD)]
    dll_handle.daqGetDeviceList.restype = ctypes.c_int

    # --- Error Handler Functions ---
    dll_handle.daqSetErrorHandler.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    dll_handle.daqSetErrorHandler.restype = ctypes.c_ulong

    dll_handle.daqSetDefaultErrorHandler.argtypes = [ctypes.c_void_p]
    dll_handle.daqSetDefaultErrorHandler.restype = ctypes.c_ulong

    dll_handle.daqSetTimeout.argtypes = [DaHandleT, ctypes.c_ulong]
    dll_handle.daqSetTimeout.restype = ctypes.c_ulong

    dll_handle.daqGetDriverVersion.argtypes = [DaHandleT]
    dll_handle.daqGetDriverVersion.restype = ctypes.c_ulong

    # --- Data Format Functions ---
    dll_handle.daqAdcSetDataFormat.argtypes = [DaHandleT, DWORD, DWORD]
    dll_handle.daqAdcSetDataFormat.restype = ctypes.c_ulong

    dll_handle.daqAdcSetFilter.argtypes = [DaHandleT, ctypes.c_ulong, ctypes.c_float]
    dll_handle.daqAdcSetFilter.restype = ctypes.c_ulong

    # --- ADC Acquisition Control ---
    dll_handle.daqAdcArm.argtypes = [DaHandleT]
    dll_handle.daqAdcArm.restype = ctypes.c_ulong

    dll_handle.daqAdcDisarm.argtypes = [DaHandleT]
    dll_handle.daqAdcDisarm.restype = ctypes.c_ulong

    dll_handle.daqAdcAcqGetStat.argtypes = [
        DaHandleT,
        PDWORD,
        PDWORD,
        PDWORD,
        PDWORD,
        DWORD,
    ]
    dll_handle.daqAdcAcqGetStat.restype = ctypes.c_ulong

    # --- ADC Read Functions ---
    dll_handle.daqAdcRd.argtypes = [DaHandleT, DWORD, ctypes.c_void_p, DWORD, DWORD]
    dll_handle.daqAdcRd.restype = ctypes.c_ulong


# ============================================================================
# API Constants and Flags
# ============================================================================

# Data format constants (from vendor headers - TODO: Extract numeric values)
# Using reasonable defaults based on documentation
DardfNative = 0
DardfPacked = 1
DardfFloat = 2  # Raw format is floating point (required for °C)

# Post-processing format constants
DappdfRaw = 0  # Raw data follows rawFormat
DappdfTenthsDegC = 1  # Used to read thermocouple data with TempBook/66

# Gain constants for Personal DAQ
PGainDiv5 = 8
PGainX1 = 0  # ×1 gain
PGainX2 = 1  # ×2 gain
PGainX4 = 16
PGainX8 = 17
PGainX16 = 18
PGainX32 = 19
PGainX64 = 20
PGainX128 = 21

DafAnalog = 0x00  # Analog input channel
DafDifferential = 0x08  # Differential mode
DafTcTypeK = 0x100  # Thermocouple Type K
DafMeasDuration110 = 0x400000  # Measurement duration: 110 ms
FLAGS_TC_K_DIFF_110MS = (
    DafAnalog | DafDifferential | DafTcTypeK | DafMeasDuration110
)  # 0x400108 = 67109120

# Error codes
DerrNoError = 0  # Success


# ============================================================================
# Device Handles
# ============================================================================

DaHandleT = ctypes.c_void_p  # Handle for Personal DAQ device


# ============================================================================
# Personal DAQ Class
# ============================================================================


class PersonalDAQ(CommunicationProtocol):
    """Communication protocol for Personal DAQ/56 USB Data Acquisition.

    Implements minimal "read one temperature" feature using vendor's
    pdaqx.dll (PDAQX.DLL) API via ctypes.

    Features:
    - Single temperature read from thermocouple channel
    - USB communication (not serial)
    - Windows DLL API (pdaqx.dll)
    - Configurable gain and measurement duration
    """

    def __init__(
        self,
        port: str,
        config: Optional[DeviceConfig] = None,
        device_name: Optional[str] = None,
        channel: int = 1,
        gain: float = 1.0,
        dll_path: Optional[str] = None,
    ):
        """Initialize Personal DAQ/56 temperature reader.

        Args:
            port: Port name (not used for USB devices, kept for consistency)
            config: Device configuration, uses default if None
            device_name: Device name for daqOpen (default from config)
            channel: ADC channel number (PD1_A01 = channel 1)
            gain: Channel gain multiplier (default: 1.0)
            dll_path: Path to pdaqx.dll (default from config or System32)

        Raises:
            RuntimeError: If DLL not available or initialization fails
        """
        config = config or default_config

        # Set device name from parameter or config
        self.device_name = device_name or config.personal_daq_device_name

        # Store channel and gain
        self.channel = channel
        self.gain = gain

        # Initialize base class
        super().__init__(port, config)

        # Load DLL from specified path or config
        dll_path_to_use = dll_path or getattr(
            config, "personal_daq_dll_path", r"C:\Windows\System32\pdaqx.dll"
        )
        self.dll = _load_dll(dll_path_to_use)

        # Declare DLL prototypes
        _declare_prototypes(self.dll)

        # Device handle
        self.handle: Optional[DaHandleT] = None
        self.is_connected = False

    def connect(self) -> bool:
        """Establish connection to Personal DAQ/56.

        Opens session and configures ADC format to read temperature.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Open device session
            # Note: device_name parameter expects C string (not Python str)
            device_name_c = self.device_name.encode("ascii")
            handle = self.dll.daqOpen(device_name_c)

            if not handle:
                self.logger.error("daqOpen returned null handle")
                return False

            self.handle = ctypes.cast(handle, DaHandleT)

            # Set ADC data format to floating point
            # Required for thermocouple to return °C instead of raw ADC counts
            err = self.dll.daqAdcSetDataFormat(
                self.handle,
                ctypes.c_ulong(DardfFloat),  # rawFormat
                ctypes.c_ulong(DappdfRaw),  # postProcFormat
            )

            if err != DerrNoError:
                self.logger.error(f"daqAdcSetDataFormat error: {err}")
                self._close()
                return False

            self.is_connected = True
            self.logger.info(
                f"Personal DAQ connected: device={self.device_name}, channel={self.channel}"
            )
            return True

        except Exception as e:
            self.logger.error(f"Connection failed: {e}")
            self._close()
            return False

    def disconnect(self) -> None:
        """Close connection to Personal DAQ/56.

        Releases device handle and cleans up resources.
        """
        self._close()

    def send_command(self, command: str) -> Optional[str]:
        """Send command to device (not applicable for DAQ).

        This method is required by the base class but not used for
        Personal DAQ which uses DLL API instead of text commands.

        Args:
            command: Command string (ignored)

        Returns:
            None (not implemented)
        """
        self.logger.warning("send_command() not applicable for Personal DAQ")
        return None

    def read_temperature(self) -> Optional[float]:
        """Read current temperature from thermocouple channel.

        Reads one temperature sample from the configured ADC channel.
        Returns temperature in °C (calibrated by driver).

        Args:
            None

        Returns:
            Temperature in °C, or None if error
        """
        if not self.is_connected or not self.handle:
            self.logger.error("Not connected to Personal DAQ")
            return None

        try:
            # Sample pointer to hold ADC value
            sample = ctypes.c_float()

            # Read one sample from specified channel
            # Flags: DafAnalog | DafDifferential | DafTcTypeK | DafMeasDuration110
            err = self.dll.daqAdcRd(
                self.handle,
                ctypes.c_ulong(self.channel),  # chan
                ctypes.byref(sample),  # sample
                ctypes.c_ulong(PGainX1),  # gain (PGainX1 = 0)
                ctypes.c_ulong(FLAGS_TC_K_DIFF_110MS),  # flags
            )

            if err != DerrNoError:
                self.logger.error(f"daqAdcRd error: {err}")
                return None

            # Temperature is returned in floating point format (°C)
            temperature_c = float(sample.value)

            # Validate temperature range (Type K: -200 to 1250°C)
            if not (-200 <= temperature_c <= 1250):
                self.logger.warning(f"Temperature out of range: {temperature_c}°C")
                # Still return value as it may be valid for different TC types

            return temperature_c

        except Exception as e:
            self.logger.error(f"Failed to read temperature: {e}")
            return None

    def _close(self) -> None:
        """Internal method to close DAQ session safely."""
        if self.handle:
            self.dll.daqClose(self.handle)
            self.handle = None
            self.is_connected = False

    def get_device_info(self) -> dict:
        """Get device information and current status.

        Returns:
            Dictionary containing device information
        """
        info = {
            "device_name": self.device_name,
            "port": self.port,
            "channel": self.channel,
            "gain": self.gain,
            "is_connected": self.is_connected,
        }

        if self.is_connected:
            info["current_temperature_c"] = self.read_temperature()

        return info


# ============================================================================
# Module Initialization
# ============================================================================

# Note: Prototypes are now declared in PersonalDAQ.__init__ for each instance
# to support configurable DLL paths.
