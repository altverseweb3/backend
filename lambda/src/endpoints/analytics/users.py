import json
from botocore.exceptions import ClientError
from ...config import metrics_table
from ...utils.utils import (
    build_response,
    get_past_periods,
    validate_period_type,
    validate_and_sanitize_limit,
)


def get_total_users(body):
    """
    Fetches the all-time total user count.

    QueryType: "total_users"
    Body: {}

    Returns:
        Response with total_users count
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
    Fetches new and active users for the last 'limit' periods.

    QueryType: "periodic_user_stats"
    Body: {
        "period_type": "daily" | "weekly" | "monthly",
        "limit": 7
    }

    Returns:
        Response with period_type and array of period-based user stats
        with new_users and active_users counts
    """
    try:
        period_type = body.get("period_type", "daily")
        limit = body.get("limit", 7)

        # Validate period type
        is_valid, error_response = validate_period_type(period_type)
        if not is_valid:
            return error_response

        # Sanitize limit
        limit = validate_and_sanitize_limit(limit, default=7, min_val=1, max_val=90)

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

        # Return data in descending order (most recent first)
        return build_response(200, {"period_type": period_type, "data": results})

    except ClientError as e:
        print(f"Error getting periodic user stats: {e}")
        return build_response(500, {"error": "Could not retrieve periodic user stats"})
