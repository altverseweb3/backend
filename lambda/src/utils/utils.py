import json
from datetime import datetime, timedelta, timezone


def get_client_ip(event):
    """Extract client IP address from Lambda event."""
    if "requestContext" in event and "identity" in event["requestContext"]:
        return event["requestContext"]["identity"].get("sourceIp", "unknown")
    headers = event.get("headers", {})
    if headers and "X-Forwarded-For" in headers:
        # X-Forwarded-For may have a list; we take the first
        return headers["X-Forwarded-For"].split(",")[0].strip()
    return "unknown"


def get_time_periods(dt_object):
    """
    Calculates the start dates for day, week, and month for a given datetime object.
    It also returns the ISO week number for the leaderboard key.
    """
    # Ensure datetime is timezone-aware (UTC)
    dt_object = dt_object.astimezone(timezone.utc)

    # Daily: YYYY-MM-DD
    daily_start = dt_object.strftime("%Y-%m-%d")

    # Weekly (week starts on Monday): YYYY-MM-DD
    weekly_start_dt = dt_object - timedelta(days=dt_object.weekday())
    weekly_start = weekly_start_dt.strftime("%Y-%m-%d")

    # Monthly: YYYY-MM-01
    monthly_start = dt_object.strftime("%Y-%m-01")

    # Leaderboard Week: YYYY-WW (e.g., 2025-42)
    year, week_num, _ = dt_object.isocalendar()
    leaderboard_week = f"{year}-{week_num:02d}"

    return {
        "daily": daily_start,
        "weekly": weekly_start,
        "monthly": monthly_start,
        "leaderboard_week": leaderboard_week,
    }


def build_response(status_code, body):
    """
    Builds a standard API Gateway proxy response.
    """
    return {
        "statusCode": status_code,
        "headers": {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "**",
            "Access-Control-Allow-Methods": "ANY,OPTIONS,POST,GET",
            "Content-Type": "application/json",
        },
        "body": json.dumps(body).encode("utf-8"),
        "isBase64Encoded": True,
    }
