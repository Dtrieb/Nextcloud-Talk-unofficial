"""Config Flow für Nextcloud Talk Integration."""
import logging
import voluptuous as vol
import aiohttp

from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, CONF_URL, CONF_USERNAME, CONF_PASSWORD

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

async def validate_input(hass, data: dict):
    """Prüfe die Serververbindung und Zugangsdaten über die Nextcloud OCS API."""
    url = data[CONF_URL].rstrip("/")
    auth = aiohttp.BasicAuth(data[CONF_USERNAME], data[CONF_PASSWORD])
    session = async_get_clientsession(hass)

    headers = {
        "OCS-APIRequest": "true",
        "Accept": "application/json",
    }

    # Test-Endpunkt 1: Allgemeine Capabilities prüfen
    test_url = f"{url}/ocs/v2.php/cloud/capabilities?format=json"

    try:
        async with session.get(test_url, auth=auth, headers=headers, timeout=10) as response:
            _LOGGER.debug("Nextcloud Auth Check HTTP Status: %s", response.status)
            if response.status in (401, 403):
                raise ValueError("invalid_auth")
            if response.status != 200:
                _LOGGER.error("Fehler von Nextcloud erhalten: HTTP Status %s", response.status)
                raise ConnectionError("cannot_connect")
                
            res_json = await response.json()
            # Prüfen, ob Nextcloud Talk (spreed) überhaupt auf dem Server installiert ist
            capabilities = res_json.get("ocs", {}).get("data", {}).get("capabilities", {})
            if "spreed" not in capabilities:
                _LOGGER.error("Nextcloud Talk (Spreed) ist auf diesem Server nicht installiert oder aktiviert.")
                raise ConnectionError("cannot_connect")

    except aiohttp.ClientError as err:
        _LOGGER.error("Netzwerk-/Verbindungsfehler zu Nextcloud: %s", err)
        raise ConnectionError("cannot_connect") from err

    return {"title": f"Nextcloud Talk ({data[CONF_USERNAME]})"}


class NextcloudTalkConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config Flow Handhabung."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Erster Schritt bei der Konfiguration via UI."""
        errors = {}

        if user_input is not None:
            await self.async_set_unique_id(f"{user_input[CONF_URL]}_{user_input[CONF_USERNAME]}")
            self._abort_if_unique_id_configured()

            try:
                info = await validate_input(self.hass, user_input)
                return self.async_create_entry(title=info["title"], data=user_input)
            except ValueError:
                errors["base"] = "invalid_auth"
            except ConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unerwarteter Fehler bei der Validierung")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )