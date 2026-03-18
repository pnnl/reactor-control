"""MKS ToolWEB interface client."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional
from urllib import error, request
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

SRC_PATH = Path(__file__).resolve().parent.parent.parent
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from .base import CommunicationProtocol
from src.core.config import DeviceConfig, default_config
from src.core.mg2000_setup import ToolWebAddinConfig, ensure_toolweb_addin

logger = logging.getLogger(__name__)


class MKSToolWeb(CommunicationProtocol):
    """Client for the MKS ToolWEB interface (ToolSide Protocol).

    Supports polling for EVID values and SetRequest actions for key controls.
    """

    def __init__(
        self,
        host: Optional[str] = None,
        config: Optional[DeviceConfig] = None,
        port: Optional[int] = None,
        sub_sensor: Optional[str] = None,
    ) -> None:
        """Initialize the ToolWEB client.

        Args:
            host: ToolWEB server host or IP address
            config: Device configuration, uses default if None
            port: Optional override for ToolWEB server port
            sub_sensor: Optional sub-sensor name for ToolWEB path
        """
        config = config or default_config
        super().__init__(port=host, config=config)
        self.host: str = host if host is not None else config.mks_toolweb_host
        self.port: int = port if port is not None else config.mks_toolweb_port
        self.sub_sensor: str = sub_sensor or config.mks_toolweb_sub_sensor
        self.base_path: str = config.mks_toolweb_base_path
        self.timeout_s: float = config.mks_toolweb_timeout
        self.default_recipe: str = config.mks_toolweb_default_recipe
        self.is_valid: bool = True

        if not isinstance(self.host, str) or not self.host:
            self.logger.error("ToolWEB host must be a non-empty string")
            self.is_valid = False
        if not isinstance(self.port, int):
            self.logger.error("ToolWEB port must be an integer")
            self.is_valid = False
        if self.sub_sensor and not isinstance(self.sub_sensor, str):
            self.logger.error("ToolWEB sub-sensor must be a string")
            self.is_valid = False
        if not isinstance(self.base_path, str) or not self.base_path:
            self.logger.error("ToolWEB base path must be a non-empty string")
            self.is_valid = False

    def connect(self) -> bool:
        """Validate ToolWEB connectivity with a capabilities request.

        Returns:
            True if the request succeeds, False otherwise
        """
        if not self.is_valid:
            self.logger.error("ToolWEB client initialization is invalid")
            self.is_connected = False
            return False

        if not self._ensure_toolweb_configured():
            self.logger.error(
                "ToolWEB add-in not configured in MG2000. "
                "Ensure MG2000 is not running and TOOLWEB is in the add-ins list."
            )
            return False

        original_sub_sensor = self.sub_sensor
        self.sub_sensor = ""
        response = self.send_command(self._build_capabilities_request())
        if response is not None and original_sub_sensor:
            self.logger.info(
                f"Discovery succeeded with empty sub_sensor, using configured: {original_sub_sensor}"
            )
            self.sub_sensor = original_sub_sensor
        elif response is None and original_sub_sensor:
            self.logger.warning(
                f"Discovery failed with empty sub_sensor, trying configured: {original_sub_sensor}"
            )
            self.sub_sensor = original_sub_sensor
            response = self.send_command(self._build_capabilities_request())
        if response is None:
            self.is_connected = False
            return False
        self.is_connected = True
        return True

    def _ensure_toolweb_configured(self) -> bool:
        """Ensure TOOLWEB is configured in MG2000 config files.

        Returns:
            True if TOOLWEB is configured or successfully added, False otherwise
        """
        ini_path = Path(self.config.mg2000_ini_path)
        mgrcp_path = Path(self.config.mg2000_mgrcp_path)
        addins_dir = Path(self.config.mg2000_addins_dir)

        if not ini_path.exists():
            self.logger.warning(
                f"MG2000 INI not found at {ini_path}, skipping add-in check"
            )
            return True

        if not addins_dir.exists():
            self.logger.warning(
                f"MG2000 ADDINS directory not found at {addins_dir}, skipping add-in check"
            )
            return True

        addin_config = ToolWebAddinConfig(
            ini_path=ini_path,
            mgrcp_path=mgrcp_path,
            addins_dir=addins_dir,
        )

        result = ensure_toolweb_addin(addin_config)
        if result:
            self.logger.info("ToolWEB add-in verified in MG2000 configuration")
        else:
            self.logger.error(
                "Failed to verify/add ToolWEB add-in in MG2000 configuration"
            )
        return result

    def disconnect(self) -> None:
        """Mark the client as disconnected (no persistent connection)."""
        self.is_connected = False

    def send_command(self, command: str) -> Optional[str]:
        """Send an XML command to ToolWEB and return the response body.

        Args:
            command: XML payload to send

        Returns:
            Response body string, or None if error
        """
        if not self.is_valid:
            self.logger.error("ToolWEB client initialization is invalid")
            return None
        if not command:
            self.logger.error("ToolWEB command is empty")
            return None
        return self._post_xml(command)

    def read_instrument_state(self) -> Optional[str]:
        """Read the instrument state string (EVID 1).

        Returns:
            Instrument state string, or None if error
        """
        if not self.is_valid:
            self.logger.error("ToolWEB client initialization is invalid")
            return None
        poll_request = self._build_poll_request_names(["EVID_1"])
        response = self.send_command(poll_request)
        if response is None:
            return None
        return self._parse_poll_response(response, evid=1)

    def start_run(self) -> bool:
        """Trigger start of measurement run (EVID_31).

        Returns:
            True if trigger accepted, False otherwise
        """
        return self._send_trigger_poll("EVID_31", 31)

    def stop_run(self) -> bool:
        """Trigger stop of measurement run (EVID_33).

        Returns:
            True if trigger accepted, False otherwise
        """
        return self._send_trigger_poll("EVID_33", 33)

    def set_recipe(self, recipe_name: str) -> bool:
        """Set the active analysis recipe (EVID_22).

        Args:
            recipe_name: Recipe name to set

        Returns:
            True if accepted, False otherwise
        """
        if not isinstance(recipe_name, str) or not recipe_name.strip():
            self.logger.error("Recipe name must be a non-empty string")
            return False
        return self._send_set_request("EVID_22", recipe_name, "22")

    def set_default_recipe(self) -> bool:
        """Set the default analysis recipe from configuration.

        Returns:
            True if accepted, False otherwise
        """
        return self.set_recipe(self.default_recipe)

    def read_recipe_list(self) -> Optional[str]:
        """Read the available recipe list (EVID 20).

        Returns:
            Recipe list string, or None if error
        """
        return self._read_evid_by_name("EVID_20", 20)

    def read_recipe_reject_code(self) -> Optional[str]:
        """Read the recipe reject code (EVID 23).

        Returns:
            Reject code string, or None if error
        """
        return self._read_evid_by_name("EVID_23", 23)

    def read_trigger_status(self) -> Optional[str]:
        """Read the last trigger status (EVID 30).

        Returns:
            Trigger status string, or None if error
        """
        return self._read_evid_by_name("EVID_30", 30)

    def set_prn_path(self, prn_path: str) -> bool:
        """Set the PRN storage path/filename (EVID_71).

        This method automatically handles the required sequence:
        1. Disable PRN storage (in case it's already enabled from previous session)
        2. Disable rollover (must be done while PRN is disabled)
        3. Enable PRN storage
        4. Set the PRN path/filename

        Args:
            prn_path: Full filename or path for PRN storage

        Returns:
            True if accepted, False otherwise
        """
        if not isinstance(prn_path, str) or not prn_path.strip():
            self.logger.error("PRN path must be a non-empty string")
            return False

        # Step 1: Disable PRN (in case already enabled from previous session)
        if not self.set_prn_enabled(False):
            self.logger.warning("Failed to disable PRN storage, continuing anyway")

        # Step 2: Disable rollover (must be done while PRN is disabled)
        if not self.set_prn_rollover_enabled(False):
            self.logger.error("Failed to disable PRN rollover")
            return False

        # Step 3: Enable PRN storage
        if not self.set_prn_enabled(True):
            self.logger.error("Failed to enable PRN storage")
            return False

        # Step 4: Set the PRN path/filename
        return self._send_set_request("EVID_71", prn_path, "71")

    def set_prn_enabled(self, enabled: bool) -> bool:
        """Enable or disable PRN file storage (EVID_70).

        Args:
            enabled: True to enable PRN storage, False to disable

        Returns:
            True if accepted, False otherwise
        """
        value = "True" if enabled else "False"
        return self._send_set_request("EVID_70", value, "70")

    def set_prn_rollover_enabled(self, enabled: bool) -> bool:
        """Enable or disable PRN rollover mechanism (EVID_72).

        Args:
            enabled: True to enable rollover, False to disable

        Returns:
            True if accepted, False otherwise
        """
        value = "True" if enabled else "False"
        return self._send_set_request("EVID_72", value, "72")

    def set_spectra_path(self, spectra_path: str) -> bool:
        """Set the spectra storage base path (EVID_81).

        Args:
            spectra_path: Base directory for spectra storage

        Returns:
            True if accepted, False otherwise
        """
        if not isinstance(spectra_path, str) or not spectra_path.strip():
            self.logger.error("Spectra path must be a non-empty string")
            return False
        return self._send_set_request("EVID_81", spectra_path, "81")

    def _build_capabilities_request(self) -> str:
        """Build a ToolWEB capabilities request XML document.

        Returns:
            XML string for capabilities request
        """
        return '<?xml version="1.0"?><CapabilitiesRequest />'

    def _build_poll_request(self, evid: int) -> str:
        """Build a ToolWEB poll request XML document.

        Args:
            evid: EVID to request

        Returns:
            XML string for poll request
        """
        if not isinstance(evid, int):
            self.logger.error(f"EVID must be an integer, got: {type(evid).__name__}")
            return ""
        if evid < 1:
            self.logger.error(f"Invalid EVID requested: {evid}")
            return ""
        return f'<?xml version="1.0"?><PollRequest><V Name="{evid}"/></PollRequest>'

    def _build_poll_request_names(self, evid_names: list[str]) -> str:
        """Build a ToolWEB poll request for multiple EVID names.

        Args:
            evid_names: List of EVID names to request

        Returns:
            XML string for poll request
        """
        if not evid_names:
            self.logger.error("EVID name list is empty")
            return ""
        for name in evid_names:
            if not isinstance(name, str) or not name:
                self.logger.error(f"Invalid EVID name: {name}")
                return ""

        evid_elements = "".join(f'<V Name="{name}"/>' for name in evid_names)
        return f'<?xml version="1.0"?><PollRequest>{evid_elements}</PollRequest>'

    def _build_set_request(self, evid_name: str, value: str) -> str:
        """Build a ToolWEB set request XML document.

        Args:
            evid_name: EVID name to set
            value: Value to write

        Returns:
            XML string for set request
        """
        if not evid_name or not isinstance(evid_name, str):
            self.logger.error("EVID name must be a non-empty string")
            return ""
        if value is None:
            self.logger.error("SetRequest value must not be None")
            return ""
        safe_value = escape(str(value))
        return (
            '<?xml version="1.0"?>'
            f'<SetRequest><V Name="{evid_name}">{safe_value}</V></SetRequest>'
        )

    def _build_cmd_path(self) -> str:
        """Build the ToolWEB command path.

        Returns:
            URL path for ToolWEB commands
        """
        base = self.base_path.strip()
        if not base.startswith("/"):
            base = f"/{base}"
        base = base.rstrip("/")
        if self.sub_sensor:
            return f"{base}/{self.sub_sensor}/Cmd"
        return f"{base}/Cmd"

    def _build_url(self) -> str:
        """Build the full ToolWEB endpoint URL.

        Returns:
            Full URL string
        """
        path = self._build_cmd_path()
        return f"http://{self.host}:{self.port}{path}"

    def _post_xml(self, xml_body: str) -> Optional[str]:
        """POST XML payload to ToolWEB and return response body.

        Args:
            xml_body: XML payload to send

        Returns:
            Response body string, or None if error
        """
        if not self._validate_request(xml_body):
            return None
        url = self._build_url()
        data = xml_body.encode("utf-8")
        headers = {"Content-Type": "text/xml"}
        request_obj = request.Request(url, data=data, headers=headers, method="POST")

        try:
            with request.urlopen(request_obj, timeout=self.timeout_s) as response:
                body = response.read().decode("utf-8", errors="replace")
                self.is_connected = True
                return body
        except error.HTTPError as exc:
            self.is_connected = False
            self.logger.error(f"HTTP error {exc.code} for ToolWEB request: {exc}")
            return None
        except error.URLError as exc:
            self.is_connected = False
            self.logger.error(f"ToolWEB connection error: {exc}")
            return None
        except Exception as exc:
            self.is_connected = False
            self.logger.error(f"Unexpected ToolWEB error: {exc}")
            return None

    def _parse_poll_response(self, xml_body: str, evid: int) -> Optional[str]:
        """Parse a ToolWEB PollResponse for a specific EVID.

        Args:
            xml_body: PollResponse XML string
            evid: EVID to extract

        Returns:
            Value string for the requested EVID, or None if not found
        """
        if not isinstance(evid, int):
            self.logger.error(f"EVID must be an integer, got: {type(evid).__name__}")
            return None
        if not xml_body:
            self.logger.error("PollResponse XML body is empty")
            return None
        try:
            root = ET.fromstring(xml_body)
        except ET.ParseError as exc:
            self.logger.error(f"Failed to parse PollResponse XML: {exc}")
            return None

        evid_name = str(evid)
        evid_alt_name = f"EVID_{evid}"
        for element in root.findall(".//V"):
            name = element.attrib.get("Name", "")
            if name in (evid_name, evid_alt_name):
                if element.text is None:
                    self.logger.warning("PollResponse contained empty value")
                    return ""
                return element.text.strip()

        self.logger.error(f"EVID {evid} not found in PollResponse")
        return None

    def _parse_set_response(self, xml_body: str, evid_name: str) -> bool:
        """Parse a ToolWEB SetResponse for a specific EVID.

        Args:
            xml_body: SetResponse XML string
            evid_name: EVID name to extract

        Returns:
            True if set accepted, False otherwise
        """
        if not evid_name or not isinstance(evid_name, str):
            self.logger.error("EVID name must be a non-empty string")
            return False
        if not xml_body:
            self.logger.error("SetResponse XML body is empty")
            return False
        try:
            root = ET.fromstring(xml_body)
        except ET.ParseError as exc:
            self.logger.error(f"Failed to parse SetResponse XML: {exc}")
            return False

        for element in root.findall(".//V"):
            name = element.attrib.get("Name", "")
            if name == evid_name:
                feedback = element.attrib.get("Feedback", "")
                if feedback in ("0", "Acknowledge", "ACK", "Ack", "100"):
                    return True
                if feedback:
                    self.logger.error(
                        f"SetResponse rejected for {evid_name}: {feedback}"
                    )
                    return False
                self.logger.error(f"SetResponse missing feedback for {evid_name}")
                return False

        self.logger.error(f"EVID {evid_name} not found in SetResponse")
        return False

    def _send_set_request(
        self, evid_name: str, value: str, fallback_name: Optional[str] = None
    ) -> bool:
        """Send a set request and parse the response.

        Args:
            evid_name: EVID name to set
            value: Value to write

        Returns:
            True if accepted, False otherwise
        """
        if not self.is_valid:
            self.logger.error("ToolWEB client initialization is invalid")
            return False
        if not evid_name or not isinstance(evid_name, str):
            self.logger.error("EVID name must be a non-empty string")
            return False
        if value is None:
            self.logger.error("SetRequest value must not be None")
            return False

        response = self._send_set_request_once(evid_name, str(value))
        if response is None and fallback_name:
            self.logger.warning(
                f"Retrying SetRequest with fallback EVID name {fallback_name}"
            )
            response = self._send_set_request_once(fallback_name, str(value))
            if response is None:
                return False
            return self._parse_set_response(response, fallback_name)
        if response is None:
            return False
        return self._parse_set_response(response, evid_name)

    def _send_trigger_poll(self, evid_name: str, evid_numeric: int) -> bool:
        """Trigger an action by polling the trigger EVID.

        Args:
            evid_name: Trigger EVID name
            evid_numeric: Numeric EVID for response parsing

        Returns:
            True if PollResponse received, False otherwise
        """
        if not self.is_valid:
            self.logger.error("ToolWEB client initialization is invalid")
            return False
        poll_request = self._build_poll_request_names([evid_name])
        if not poll_request:
            return False
        response = self.send_command(poll_request)
        if response is None:
            return False
        value = self._parse_poll_response(response, evid_numeric)
        if value is None:
            self.logger.error(f"Trigger poll did not return value for {evid_name}")
            return False
        return True

    def _read_evid_by_name(self, evid_name: str, evid_numeric: int) -> Optional[str]:
        """Read an EVID by name and parse by numeric id.

        Args:
            evid_name: EVID name to request
            evid_numeric: Numeric EVID for parsing

        Returns:
            Value string, or None if error
        """
        if not self.is_valid:
            self.logger.error("ToolWEB client initialization is invalid")
            return None
        poll_request = self._build_poll_request_names([evid_name])
        if not poll_request:
            return None
        response = self.send_command(poll_request)
        if response is None:
            return None
        return self._parse_poll_response(response, evid_numeric)

    def _send_set_request_once(self, evid_name: str, value: str) -> Optional[str]:
        """Send a set request and return raw response.

        Args:
            evid_name: EVID name to set
            value: Value to write

        Returns:
            Raw response string, or None if error
        """
        set_request = self._build_set_request(evid_name, value)
        if not set_request:
            return None
        return self.send_command(set_request)

    def _validate_request(self, xml_body: str) -> bool:
        """Validate ToolWEB request settings and payload.

        Args:
            xml_body: XML payload to send

        Returns:
            True if request is valid, False otherwise
        """
        if not self.host:
            self.logger.error("ToolWEB host is not set")
            return False
        if not self.is_valid:
            self.logger.error("ToolWEB client initialization is invalid")
            return False
        if not 1 <= self.port <= 65535:
            self.logger.error(f"Invalid ToolWEB port: {self.port}")
            return False
        if self.timeout_s <= 0:
            self.logger.error(
                f"Invalid ToolWEB timeout: {self.timeout_s} (must be > 0)"
            )
            return False
        if not xml_body:
            self.logger.error("ToolWEB XML body is empty")
            return False
        return True
