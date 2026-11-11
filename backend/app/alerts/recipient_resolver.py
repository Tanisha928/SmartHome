"""Resolve alert recipients from house membership and notification preferences."""

from __future__ import annotations

from typing import Any


SEVERITY_RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1}


class RecipientResolver:
    def resolve(
        self,
        alert: Any,
        users: list[Any],
        preferences: list[Any],
    ) -> list[dict[str, Any]]:
        prefs_by_user = {
            (int(pref.user_id), str(pref.alert_category)): pref for pref in preferences
        }
        recipients: list[dict[str, Any]] = []
        for user in users:
            pref = prefs_by_user.get((int(user.user_id), str(alert.alert_category)))
            if pref is None:
                if user.role != "owner" or alert.severity not in {"critical", "high"}:
                    continue
                channels = ["email", "sms"]
            else:
                if SEVERITY_RANK[alert.severity] < SEVERITY_RANK[str(pref.min_severity)]:
                    continue
                channels = []
                if pref.email:
                    channels.append("email")
                if pref.sms and getattr(user, "phone", None):
                    channels.append("sms")
            for channel in channels:
                recipients.append(
                    {
                        "recipient_id": int(user.user_id),
                        "recipient_label": (
                            getattr(user, "phone", None)
                            if channel == "sms"
                            else getattr(user, "email", str(user.user_id))
                        ),
                        "email": getattr(user, "email", None),
                        "phone": getattr(user, "phone", None),
                        "channel": channel,
                    }
                )
        return recipients
