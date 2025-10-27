import json
from botocore.exceptions import ClientError
from ...config import metrics_table
from ...utils.utils import build_response


def get_total_users(body):
    """
    Fetches the all-time total user count.
    Corresponds to: User & Audience -> Total Users
    - Query: Get STAT#all#ALL, read `new_users`
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
    Fetches new and active users for a specific period (daily, weekly, monthly).
    Corresponds to:
    - User & Audience -> New Users (Time-series)
    - User & Audience -> Active Users (DAU/WAU/MAU)
    - Query: Get STAT#{period}#GENERAL, read `new_users`, `active_users`

    Expected body:
    {
        "queryType": "periodic_user_stats",
        "period_type": "daily" | "weekly" | "monthly",
        "period_start_date": "YYYY-MM-DD",
    }
    """
    try:
        period_type = body.get("period_type")
        period_start_date = body.get("period_start_date")

        if not period_type or not period_start_date:
            return build_response(
                400,
                {"error": "Request must include 'period_type' and 'period_start_date'"},
            )

        response = metrics_table.get_item(
            Key={
                "PK": f"STAT#{period_type}#{period_start_date}",
                "SK": "GENERAL",
            },
            ProjectionExpression="new_users, active_users",
        )

        # Default to 0 if the item or attributes don't exist for the period
        item = response.get("Item", {})
        new_users = item.get("new_users", 0)
        active_users = item.get("active_users", 0)

        return build_response(
            200, {"new_users": int(new_users), "active_users": int(active_users)}
        )

    except ClientError as e:
        print(f"Error getting periodic user stats: {e}")
        return build_response(500, {"error": "Could not retrieve periodic user stats"})
