import decimal
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


def get_past_periods(period_type, limit):
    """
    Generates a list of the last 'limit' period start dates
    based on the period_type ('daily', 'weekly', 'monthly').

    The list is in descending order (most recent first).
    """
    periods = []
    now_utc = datetime.now(timezone.utc)

    # Get the start date of the current period to begin iteration
    current_period_starts = get_time_periods(now_utc)

    if period_type == "daily":
        # Parse the start date string back into a date object
        current_date = datetime.strptime(
            current_period_starts["daily"], "%Y-%m-%d"
        ).date()
        for _ in range(limit):
            periods.append(current_date.strftime("%Y-%m-%d"))
            current_date -= timedelta(days=1)

    elif period_type == "weekly":
        # Parse the start date string back into a date object
        current_date = datetime.strptime(
            current_period_starts["weekly"], "%Y-%m-%d"
        ).date()
        for _ in range(limit):
            periods.append(current_date.strftime("%Y-%m-%d"))
            current_date -= timedelta(weeks=1)  # Go back 7 days

    elif period_type == "monthly":
        # Parse the start date string back into a date object
        current_date = datetime.strptime(
            current_period_starts["monthly"], "%Y-%m-01"
        ).date()
        for _ in range(limit):
            periods.append(current_date.strftime("%Y-%m-01"))
            # Go to the previous day (guaranteed to be in the previous month)
            last_day_of_prev_month = current_date - timedelta(days=1)
            # Find the first day of that new month
            current_date = last_day_of_prev_month.replace(day=1)

    return periods


class CustomDecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, decimal.Decimal):
            # Convert Decimal to int or float
            if o % 1 == 0:
                return int(o)
            else:
                return float(o)
        # Let the base class default method raise the TypeError for other types
        return super(CustomDecimalEncoder, self).default(o)


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
        "body": json.dumps(body, cls=CustomDecimalEncoder).encode("utf-8"),
        "isBase64Encoded": True,
    }


def validate_period_type(period_type):
    """
    Validates that the period_type is one of the allowed values.

    Args:
        period_type: The period type to validate

    Returns:
        tuple: (is_valid, error_response)
               is_valid is True if valid, False otherwise
               error_response is the response to return if invalid
    """
    if period_type not in ["daily", "weekly", "monthly"]:
        return False, build_response(
            400,
            {"error": "Invalid period_type. Must be 'daily', 'weekly', or 'monthly'."},
        )
    return True, None


def validate_and_sanitize_limit(limit, default=7, min_val=1, max_val=90):
    """
    Validates and sanitizes the limit parameter for analytics queries.

    Args:
        limit: The limit value to validate (can be string, int, or None)
        default: Default value to use if limit is invalid
        min_val: Minimum allowed value
        max_val: Maximum allowed value

    Returns:
        int: Sanitized limit value within bounds
    """
    try:
        # Set reasonable bounds for limit to prevent abuse
        return min(max(int(limit), min_val), max_val)
    except (ValueError, TypeError):
        return default
