"""Module contains the EheimDigitalAPIClient class, which manages REST API requests to EHEIM Digital."""

import json
from typing import Any

from aiohttp import BasicAuth, ClientError, ClientSession, ClientTimeout

from .const import DEVICE_ENDPOINTS, LOGGER
from .devices import EheimDevice

DEFAULT_TIMEOUT = 2


class EheimDigitalError(Exception):
    """Base EheimDigital exception."""


class EheimDigitalConnectionError(EheimDigitalError):
    """Raised to indicate connection error."""


class EheimDigitalConnectionTimeout(EheimDigitalError):
    """Raised to indicate connection timeout."""


class EheimDigitalAuthError(EheimDigitalError):
    """Raised to indicate auth error."""


class EheimDigitalNotFound(EheimDigitalError):
    """Raised to indicate not found error."""


class EheimDigitalAPIClient:
    """Class to manage REST API requests to EHEIM Digital."""

    def __init__(self, master_host_ip, username: str, password: str) -> None:
        """Initialize the REST client."""
        self._master_host_ip = master_host_ip
        self._auth = BasicAuth(username, password)
        self._session = ClientSession(
            auth=self._auth, timeout=ClientTimeout(total=DEFAULT_TIMEOUT)
        )

    async def _send_request(
        self,
        method: str,
        host: str,
        endpoint: str,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict:
        """Send HTTP request to the API."""

        url = f"http://{host}/api/{endpoint}"
        if method == "POST":
            LOGGER.debug(f"POST request {url}, data: {data}")
        else:
            LOGGER.debug(f"GET request {url}, params: {params}")

        try:
            async with self._session.request(
                method, url, json=data, params=params
            ) as response:
                response.raise_for_status()

                if response.status == 404:
                    raise EheimDigitalNotFound
                if response.status in [401, 403]:
                    raise EheimDigitalAuthError

                if response.status == 200:
                    content_type = response.headers.get("Content-Type", "")
                    if content_type == "text/json":
                        # Workaround for incorrect content_type
                        text = await response.text()
                        result = json.loads(text)
                    elif content_type == "application/json":
                        result = await response.json()
                    else:
                        result = await response.text()
                    LOGGER.debug("Response result: %s", result)
                    return result

        except ClientError as err:
            LOGGER.debug("Request error %s", err)
            raise EheimDigitalConnectionError from err
        except ConnectionError as err:
            LOGGER.debug("Connection error %s", err)
            raise EheimDigitalConnectionError from err
        except TimeoutError as err:
            LOGGER.debug("Request timeout %s", err)
            raise EheimDigitalConnectionTimeout from err

    async def get(
        self, host: str, endpoint: str, params: dict[str, Any] | None = None
    ) -> dict:
        """Make a GET request to the API."""
        return await self._send_request("GET", host, endpoint, params=params)

    async def post(self, host: str, endpoint: str, data: dict) -> dict:
        """Make a POST request to the API."""
        return await self._send_request("POST", host, endpoint, data=data)

    async def close(self) -> None:
        """Close the session."""
        if self._session:
            await self._session.close()

    # hi-level functions
    async def fetch_devices(self) -> list[EheimDevice]:
        """Fetch devices information and data."""
        LOGGER.debug("API Client: Called function fetch_devices")

        device_list = await self.get(self._master_host_ip, "devicelist")

        devices = []
        for ip in device_list["clientIPList"]:
            response = await self.get(ip, "userdata")
            device = EheimDevice(response, ip)
            devices.append(device)

        LOGGER.debug(f"API Client: Devices: {devices}")

        for device in devices:
            LOGGER.debug(
                f"API Client: Device Details: title={device.title}, mac={device.mac}, mac={device.ip}, name={device.name}, aq_name={device.aq_name}, mode={device.mode}, version={device.version}"
            )

        return devices

    async def get_device_data(
        self, device: EheimDevice, params: dict[str, Any] | None = None
    ) -> dict:
        """Fetch data for a specific device."""

        endpoint = DEVICE_ENDPOINTS[device.version]
        params = {"to": device.mac}
        return await self.get(self._master_host_ip, endpoint, params=params)
        # return await self.get(device.ip, endpoint)

    async def set_phcontrol_state(self, device: EheimDevice, state: bool) -> None:
        """Set pH control active."""
        await self.post(
            self._master_host_ip,
            "phcontrol/active",
            {"to": device.mac, "active": 1 if state else 0},
        )

    async def set_filter_state(self, device: EheimDevice, state: bool) -> None:
        """Set filter active."""
        await self.post(
            self._master_host_ip,
            "professionel5e/active",
            {"to": device.mac, "active": 1 if state else 0},
        )
