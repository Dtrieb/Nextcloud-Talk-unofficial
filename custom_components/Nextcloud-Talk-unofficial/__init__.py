"""Die Nextcloud Talk Integration."""
import logging
import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN, CONF_URL, CONF_USERNAME, CONF_PASSWORD

_LOGGER = logging.getLogger(__name__)

SERVICE_SEND_MESSAGE = "send_message"

SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required("message"): cv.string,
        vol.Required("target"): cv.string,
        vol.Optional("title"): cv.string,
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Richte die Integration anhand eines Config Entries ein."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    async def async_handle_send_message(call: ServiceCall) -> None:
        """Handle den Sendevorgang."""
        message = call.data.get("message")
        target = call.data.get("target")
        title = call.data.get("title")

        url = entry.data[CONF_URL].rstrip("/")
        username = entry.data[CONF_USERNAME]
        password = entry.data[CONF_PASSWORD]

        session = async_get_clientsession(hass)
        auth = aiohttp.BasicAuth(username, password)
        headers = {
            "OCS-APIRequest": "true",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        full_message = f"{title}\n\n{message}" if title else message
        endpoint = f"{url}/ocs/v2.php/apps/spreed/api/v1/chat/{target}"
        payload = {"token": str(target), "message": full_message}

        try:
            async with session.post(
                endpoint, json=payload, auth=auth, headers=headers, timeout=10
            ) as response:
                if response.status in (200, 201):
                    _LOGGER.debug("Nachricht erfolgreich an Raum %s gesendet.", target)
                else:
                    resp_text = await response.text()
                    _LOGGER.error(
                        "Fehler beim Senden an Nextcloud Talk (%s): HTTP %s - %s",
                        target,
                        response.status,
                        resp_text,
                    )
        except aiohttp.ClientError as err:
            _LOGGER.error("Verbindungsfehler beim Senden an %s: %s", target, err)

    # Registriere die Aktion: nextcloud_talk.send_message
    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_MESSAGE,
        async_handle_send_message,
        schema=SERVICE_SCHEMA,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Entferne einen Config Entry."""
    hass.data[DOMAIN].pop(entry.entry_id, None)
    if not hass.data[DOMAIN]:
        hass.services.async_remove(DOMAIN, SERVICE_SEND_MESSAGE)
    return True