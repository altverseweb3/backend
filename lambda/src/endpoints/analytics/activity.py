import json
from botocore.exceptions import ClientError
from ...config import dynamodb, metrics_table
from ...utils.utils import (
    build_response,
    get_past_periods,
)


def get_total_activity_stats(body):
    """
    Fetches the global, all-time activity stats from the STAT#all#ALL item.
    Corresponds to the 'Total Transactions' KPI.
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

    Expected body:
    {
        "queryType": "periodic_activity_stats",
        "period_type": "daily" | "weekly" | "monthly",
        "limit": 7 | 4 | 54 | 12
    }
    """
    try:
        period_type = body.get("period_type", "daily")
        limit = body.get("limit", 7)

        # Basic Validation
        if period_type not in ["daily", "weekly", "monthly"]:
            return build_response(
                400,
                {
                    "error": "Invalid 'period_type'. Must be 'daily', 'weekly', or 'monthly'."
                },
            )
        if (
            not isinstance(limit, int) or limit < 1 or limit > 90
        ):  # 90-day/week/month max
            return build_response(
                400, {"error": "Invalid 'limit'. Must be an integer between 1 and 90."}
            )

        # 1. Get the list of past period start dates (e.g., ['2023-10-27', '2023-10-26', ...])
        # This assumes a utility function similar to your get_time_periods
        period_dates = get_past_periods(period_type, limit)

        # 2. Prepare keys for BatchGetItem
        keys_to_get = [
            {"PK": f"STAT#{period_type}#{date}", "SK": "GENERAL"}
            for date in period_dates
        ]

        if not keys_to_get:
            return build_response(200, [])

        # 3. Fetch items in a batch
        response = dynamodb.batch_get_item(
            RequestItems={
                metrics_table.name: {
                    "Keys": keys_to_get,
                    "ProjectionExpression": "PK, swap_count, lending_count, earn_count, dapp_entrances, active_users",
                }
            }
        )

        # 4. Process the response into a map for easy lookup
        items = response.get("Responses", {}).get(metrics_table.name, [])
        stats_map = {item["PK"]: item for item in items}

        # 5. Format the results, iterating over original dates to ensure order
        #    and provide 0s for missing periods.
        results = []
        for date in period_dates:
            pk = f"STAT#{period_type}#{date}"
            item = stats_map.get(
                pk, {}
            )  # Get item or empty dict if no data for that day

            # Get counts, defaulting to 0
            swap = item.get("swap_count", 0)
            lending = item.get("lending_count", 0)
            earn = item.get("earn_count", 0)
            active_users = item.get("active_users", 0)
            dapp_entrances = item.get("dapp_entrances", 0)

            total_tx = swap + lending + earn
            tx_per_user = (total_tx / active_users) if active_users > 0 else 0

            # This structure provides all data points for the "Overall Activity" charts
            results.append(
                {
                    "period": date,
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
