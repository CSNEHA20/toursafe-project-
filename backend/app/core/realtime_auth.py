import logging
from typing import List, Optional, Dict, Any

logger = logging.getLogger("toursafe.realtime.auth")


def can_subscribe_to_channel(
    user_id: str,
    role: str,
    channel: str,
    user_profile: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Evaluates role-based permissions for a client attempting to subscribe to a channel.

    Authorization Rules:
    1. 'user:{target_user_id}' -> Allowed only if target_user_id == user_id (or role is admin).
    2. 'tourist:{tourist_id}' -> Allowed if tourist_id matches user's tourist_id, or role is authority/admin.
    3. 'authority:{authority_id}' -> Allowed if authority_id matches user's authority_id/user_id, or role is admin.
    4. 'authority:operations' -> Allowed ONLY for role in ['authority', 'admin']. Blocked for tourists.
    5. 'zone:{zone_id}' -> Allowed for all authenticated users (tourists, authorities, admins).
    6. 'incident:{incident_id}' -> Allowed for authorities/admins and involved tourists.
    """
    if not channel or not isinstance(channel, str):
        return False

    # Admins have full operational visibility
    if role == "admin":
        return True

    # Parse channel prefix and identifier
    if ":" not in channel:
        return False

    prefix, target = channel.split(":", 1)

    if prefix == "user":
        # Direct user private channel
        return target == user_id

    elif prefix == "tourist":
        # Tourist profile channel
        if role in ["authority", "admin"]:
            return True
        # For tourist role, check if target matches user_id or tourist_id
        if user_profile and user_profile.get("id") == target:
            return True
        return target == user_id

    elif prefix == "authority":
        if target == "operations":
            # Operational broadcast channel - strictly authority/admin only
            return role in ["authority", "admin"]
        # Individual authority channel
        if role in ["authority", "admin"]:
            if user_profile and user_profile.get("id") == target:
                return True
            return target == user_id
        return False

    elif prefix == "zone":
        # Zone channels are public to all authenticated users in TourSafe
        return True

    elif prefix == "incident":
        # Incidents can be monitored by authority/admin or involved tourist
        if role in ["authority", "admin"]:
            return True
        # If user is the reporting tourist for this incident
        if user_profile and user_profile.get("active_incident_id") == target:
            return True
        return False

    return False


def get_default_channels(
    user_id: str,
    role: str,
    user_profile: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """
    Determines the baseline authorized channels automatically assigned on connection.
    """
    channels = [f"user:{user_id}"]

    if role == "tourist":
        tourist_id = user_profile.get("id", user_id) if user_profile else user_id
        channels.append(f"tourist:{tourist_id}")
    elif role in ["authority", "admin"]:
        channels.append("authority:operations")
        authority_id = user_profile.get("id", user_id) if user_profile else user_id
        channels.append(f"authority:{authority_id}")

    return channels
