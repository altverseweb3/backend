import json
from botocore.exceptions import ClientError
from ...config import dynamodb, metrics_table
from ...utils.utils import (
    build_response,
    get_past_periods,
    validate_period_type,
    validate_and_sanitize_limit,
)


def get_total_activity_stats(body):
    """
    Fetches the global, all-time activity stats from the STAT#all#ALL item.

    QueryType: "total_activity_stats"
    Body: {}

    Returns:
        Response with total transaction counts, swap/lending/earn breakdowns,
        dapp entrances, and total users
    """
    try:
        response = metrics_table.get_item(Key={"PK": "STAT#all#ALL", "SK": "GENERAL"})

        if "Item" not in response:
            # Return zeros if the item hasn't been created yet
            data = {
                "total_transactions": 0,
                "swap_count": 0,
                "lending_count": 0,
                "earn_count": 0,
                "dapp_entrances": 0,
                "total_users": 0,  # This is 'new_users' in the 'all' item
            }
            return build_response(200, data)

        item = response["Item"]

        # Get counts, defaulting to 0
        swap_count = item.get("swap_count", 0)
        lending_count = item.get("lending_count", 0)
        earn_count = item.get("earn_count", 0)

        data = {
            "total_transactions": swap_count + lending_count + earn_count,
            "swap_count": swap_count,
            "lending_count": lending_count,
            "earn_count": earn_count,
            "dapp_entrances": item.get("dapp_entrances", 0),
            "total_users": item.get("new_users", 0),
        }

        return build_response(200, data)

    except ClientError as e:
        print(f"Error fetching total activity stats: {e}")
        return build_response(500, {"error": "Could not fetch total activity stats"})


def get_periodic_activity_stats(body):
    """
    Fetches periodic activity stats for time-series charts.

    QueryType: "periodic_activity_stats"
    Body: {
        "period_type": "daily" | "weekly" | "monthly",
        "limit": 7
    }

    Returns:
        Response with array of period-based activity stats including transactions,
        swap/lending/earn counts, dapp entrances, active users, and tx per user
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

        # Get the list of past period start dates
        period_dates = get_past_periods(period_type, limit)

        # Prepare keys for BatchGetItem
        keys_to_get = [
            {"PK": f"STAT#{period_type}#{date}", "SK": "GENERAL"}
            for date in period_dates
        ]

        if not keys_to_get:
            return build_response(200, [])

        # Fetch items in a batch
        response = dynamodb.batch_get_item(
            RequestItems={
                metrics_table.name: {
                    "Keys": keys_to_get,
                    "ProjectionExpression": "PK, swap_count, lending_count, earn_count, dapp_entrances, active_users",
                }
            }
        )

        # Process the response into a map for easy lookup
        items = response.get("Responses", {}).get(metrics_table.name, [])
        stats_map = {item["PK"]: item for item in items}

        # Format the results, iterating over original dates to ensure order
        # and provide 0s for missing periods
        results = []
        for date in period_dates:
            pk = f"STAT#{period_type}#{date}"
            item = stats_map.get(pk, {})

            # Get counts, defaulting to 0
            swap = item.get("swap_count", 0)
            lending = item.get("lending_count", 0)
            earn = item.get("earn_count", 0)
            active_users = item.get("active_users", 0)
            dapp_entrances = item.get("dapp_entrances", 0)

            total_tx = swap + lending + earn
            tx_per_user = (total_tx / active_users) if active_users > 0 else 0
            results.append(
                {
                    "period_start": date,
                    "total_transactions": total_tx,
                    "swap_count": swap,
                    "lending_count": lending,
                    "earn_count": earn,
                    "dapp_entrances": dapp_entrances,
                    "active_users": active_users,
                    "transactions_per_active_user": tx_per_user,
                }
            )

        return build_response(200, results)

    except ClientError as e:
        print(f"Error fetching periodic activity stats: {e}")
        return build_response(500, {"error": "Could not fetch periodic activity stats"})
    except Exception as e:
        print(f"Unexpected error in get_periodic_activity_stats: {e}")
        return build_response(500, {"error": str(e)})
