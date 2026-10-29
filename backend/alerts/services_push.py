"""
Expo Push Notification Service for AirSense Mumbai.
Dispatches batch push notifications for active AlertNotification records
to registered mobile devices via the official Expo Push API.
Deactivates invalid or unregistered tokens (e.g. DeviceNotRegistered).
"""

import logging
import requests
from typing import List, Dict, Any, Optional
from alerts.models import DeviceToken, AlertNotification

logger = logging.getLogger(__name__)

class ExpoPushClient:
    """
    Client for dispatching notifications through the Expo Push Notification service.
    Implements batch chunking (max 100 messages per request) and automatic
    token invalidation upon receiving 'DeviceNotRegistered'.
    """
    EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"
    MAX_BATCH_SIZE = 100

    @classmethod
    def is_valid_token(cls, token: str) -> bool:
        """
        Validates token syntax: must be non-empty string, typically ExponentPushToken[...] or ExpoPushToken[...].
        """
        if not isinstance(token, str) or not token.strip():
            return False
        t = token.strip()
        return t.startswith("ExponentPushToken[") or t.startswith("ExpoPushToken[") or len(t) >= 20

    @classmethod
    def send_alert_push_notifications(
        cls,
        alerts: List[AlertNotification],
        device_tokens: Optional[List[DeviceToken]] = None,
        timeout: int = 10
    ) -> Dict[str, Any]:
        """
        Builds and sends push notification payloads in batches of up to 100 to Expo Push API.
        Matches station preferences (subscribers with station set only get alerts for that station;
        subscribers with station=None receive all alerts).
        Inspects tickets and deactivates tokens with 'DeviceNotRegistered'.
        """
        if not alerts:
            return {"sent": 0, "failed": 0, "deactivated": 0, "messages_created": 0}

        if device_tokens is None:
            active_tokens = list(DeviceToken.objects.filter(is_active=True).select_related('station'))
        else:
            active_tokens = [t for t in device_tokens if t.is_active]

        if not active_tokens:
            logger.info("No active device tokens found for push delivery.")
            return {"sent": 0, "failed": 0, "deactivated": 0, "messages_created": 0}

        messages = []
        token_map = []  # parallel list to map ticket index back to DeviceToken

        for alert in alerts:
            for dt in active_tokens:
                # If subscriber has station preference, only send if alert matches
                if dt.station_id is not None and alert.station_id != dt.station_id:
                    continue

                if not cls.is_valid_token(dt.token):
                    continue

                payload = {
                    "to": dt.token,
                    "sound": "default",
                    "title": alert.title,
                    "body": alert.message,
                    "priority": "high",
                    "data": {
                        "alert_id": alert.id,
                        "station_id": alert.station.station_id if alert.station else None,
                        "station_name": alert.station.name if alert.station else "Mumbai City",
                        "severity": alert.severity,
                        "category": alert.category,
                        "aqi": alert.aqi_value,
                        "is_forecast": alert.is_forecast_alert,
                        "horizon": alert.forecast_horizon_hours
                    }
                }
                messages.append(payload)
                token_map.append(dt)

        if not messages:
            logger.info("No relevant messages generated for current device tokens.")
            return {"sent": 0, "failed": 0, "deactivated": 0, "messages_created": 0}

        total_sent = 0
        total_failed = 0
        total_deactivated = 0

        # Chunk into batches of up to MAX_BATCH_SIZE (100)
        for i in range(0, len(messages), cls.MAX_BATCH_SIZE):
            chunk_msgs = messages[i:i + cls.MAX_BATCH_SIZE]
            chunk_tokens = token_map[i:i + cls.MAX_BATCH_SIZE]

            headers = {
                "Accept": "application/json",
                "Accept-Encoding": "gzip, deflate",
                "Content-Type": "application/json",
            }

            try:
                response = requests.post(
                    cls.EXPO_PUSH_URL,
                    json=chunk_msgs,
                    headers=headers,
                    timeout=timeout
                )
                if response.status_code == 200:
                    resp_json = response.json()
                    tickets = resp_json.get("data", [])
                    for idx, ticket in enumerate(tickets):
                        dt = chunk_tokens[idx]
                        ticket_status = ticket.get("status")
                        if ticket_status == "ok":
                            total_sent += 1
                        else:
                            total_failed += 1
                            err_details = ticket.get("details", {})
                            err_code = err_details.get("error")
                            if err_code in ["DeviceNotRegistered", "InvalidCredentials"]:
                                logger.warning(f"Deactivating invalid device token {dt.token[:15]}...: {err_code}")
                                dt.is_active = False
                                dt.save(update_fields=['is_active'])
                                total_deactivated += 1
                else:
                    logger.error(f"Expo push server returned HTTP {response.status_code}: {response.text}")
                    total_failed += len(chunk_msgs)
            except Exception as e:
                logger.error(f"Failed to deliver push batch to Expo: {e}")
                total_failed += len(chunk_msgs)

        logger.info(
            f"Push notification batch dispatched: {total_sent} succeeded, "
            f"{total_failed} failed, {total_deactivated} tokens deactivated."
        )
        return {
            "sent": total_sent,
            "failed": total_failed,
            "deactivated": total_deactivated,
            "messages_created": len(messages)
        }
