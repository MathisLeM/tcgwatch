"""Channel dispatcher — routes a notification to email or Discord."""
from api.services.discord_service import send_discord
from api.services.email_service import send_email


def send_notification(
    *, channel: str, destination: str, subject: str, message: str
) -> tuple[bool, str]:
    """Send `message` to `destination` over `channel`. Returns (ok, detail)."""
    if channel == "email":
        return send_email(destination, subject, message)
    if channel == "discord":
        return send_discord(destination, f"**{subject}**\n{message}")
    return False, f"canal inconnu: {channel}"
