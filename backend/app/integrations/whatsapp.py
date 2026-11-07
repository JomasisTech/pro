"""Send sign-in codes through the WhatsApp Business Platform (Cloud API).

WhatsApp requires one-time codes to go out as an approved AUTHENTICATION template. The code must be
supplied twice: once as the body parameter and once as the parameter of the template's copy-code button.
"""

import logging

import httpx

from app.config import Settings

log = logging.getLogger(__name__)


def send_login_code(settings: Settings, phone_e164: str, code: str) -> bool:
    """Deliver `code` to `phone_e164`. Returns True when WhatsApp accepted the message. Never raises.

    Callers run this in a background task so the HTTP answer is the same whether or not delivery works.
    """
    if not settings.whatsapp_login_configured:
        if settings.app_env.lower() == "development":
            # Development convenience only, like the password-reset email.
            log.warning("WhatsApp not configured; development sign-in code for %s is %s", phone_e164, code)
        else:
            log.error("WhatsApp is not configured; a sign-in code was not sent")
        return False

    url = f"https://graph.facebook.com/{settings.whatsapp_graph_api_version}/{settings.whatsapp_phone_number_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_e164.lstrip("+"),
        "type": "template",
        "template": {
            "name": settings.whatsapp_otp_template_name,
            "language": {"code": settings.whatsapp_template_language},
            "components": [
                {"type": "body", "parameters": [{"type": "text", "text": code}]},
                {"type": "button", "sub_type": "url", "index": "0", "parameters": [{"type": "text", "text": code}]},
            ],
        },
    }
    try:
        response = httpx.post(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {settings.whatsapp_access_token}"},
            timeout=15.0,
        )
        response.raise_for_status()
        return True
    except httpx.HTTPStatusError as error:
        # Log the provider's reason but never the code or the access token.
        log.error("WhatsApp rejected the sign-in code message (HTTP %s): %s", error.response.status_code, error.response.text[:300])
    except httpx.HTTPError:
        log.exception("Could not reach the WhatsApp API")
    return False
