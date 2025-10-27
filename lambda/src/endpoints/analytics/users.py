import json
from botocore.exceptions import ClientError
from ...config import metrics_table
from ...utils.utils import build_response, get_past_periods


def get_total_users(body):
    """
    Fetches the all-time total user count.
    Corresponds to: User & Audience -> Total Users
    - Query: Get STAT#all#ALL, read `new_users`

    QueryType: "total_users"
    Body: {}
    """
    try:
        response = metrics_table.get_item(
            Key={"PK": "STAT#all#ALL", "SK": "GENERAL"},
            ProjectionExpression="new_users",
        )

        # Default to 0 if the item or attribute doesn't exist yet
        item = response.get("Item", {})
        total_users = item.get("new_users", 0)

        return build_response(200, {"total_users": int(total_users)})

    except ClientError as e:
        print(f"Error getting total users: {e}")
        return build_response(500, {"error": "Could not retrieve total user count"})


def get_periodic_user_stats(body):
    """
    Fetches new and active users for the last 'limit' periods (daily, weekly, monthly).
    This is used to populate time-series charts for New Users and Active Users (DAU/WAU/MAU).

    QueryType: "periodic_user_stats"
    Body: {
        "period_type": "daily" | "weekly" | "monthly",
        "limit": 7
    }
    """
    try:
        period_type = body.get("period_type", "daily")
        try:
            # Set reasonable bounds for limit to prevent abuse
            limit = min(max(int(body.get("limit", 7)), 1), 90)
        except (ValueError, TypeError):
            limit = 7  # Default limit

        if period_type not in ["daily", "weekly", "monthly"]:
            return build_response(
                400,
                {
                    "error": "Invalid period_type. Must be 'daily', 'weekly', or 'monthly'."
                },
            )

        # Get the list of period start dates (e.g., ["2023-10-27", "2023-10-26", ...])
        period_starts = get_past_periods(period_type, limit)

        results = []
        # Get stats for each period in the list
        for period_start in period_starts:
            pk = f"STAT#{period_type}#{period_start}"

            response = metrics_table.get_item(
                Key={"PK": pk, "SK": "GENERAL"},
                ProjectionExpression="new_users, active_users",
            )

            # Default to 0 if the item or attributes don't exist for the period
            item = response.get("Item", {})
            new_users = item.get("new_users", 0)
            active_users = item.get("active_users", 0)

            results.append(
                {
                    "period_start": period_start,
                    "new_users": int(new_users),
                    "active_users": int(active_users),
                }
            )

        # Return the data in descending order (most recent first)
        return build_response(200, {"period_type": period_type, "data": results})

    except ClientError as e:
        print(f"Error getting periodic user stats: {e}")
        return build_response(500, {"error": "Could not retrieve periodic user stats"})
