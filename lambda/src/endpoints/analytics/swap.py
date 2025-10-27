import json
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key
from ...config import metrics_table
from ...utils.utils import build_response, get_past_periods


def get_total_swap_stats(body):
    """
    Fetches all-time aggregated swap statistics.

    This function queries the single STAT#all#ALL partition to get:
    1. The 'GENERAL' item for the overall total_swap_count.
    2. All 'SWAP#{direction}' items for a breakdown by route.
    It then aggregates this data to provide a total count, a route
    breakdown, and a cross-chain vs. same-chain summary.

    QueryType: "total_swap_stats"
    Body: {}
    """
    try:
        # Query for all items in the STAT#all#ALL partition
        response = metrics_table.query(
            KeyConditionExpression=Key("PK").eq("STAT#all#ALL")
        )

        items = response.get("Items", [])

        total_swap_count = 0
        swap_routes = {}
        cross_chain_count = 0
        same_chain_count = 0

        for item in items:
            sk = item.get("SK")

            if sk == "GENERAL":
                # Get the master total swap count from the GENERAL item
                total_swap_count = item.get("swap_count", 0)

            elif sk and sk.startswith("SWAP#"):
                try:
                    direction = sk.split("#", 1)[1]
                    count = item.get("count", 0)

                    # 1. Add to swap_routes breakdown
                    swap_routes[direction] = count

                    # 2. Add to cross-chain vs. same-chain breakdown
                    chains = direction.split(",")
                    if len(chains) == 2:
                        if chains[0] == chains[1]:
                            same_chain_count += count
                        else:
                            cross_chain_count += count
                except Exception as e:
                    print(
                        f"Warning: Could not parse swap SK '{sk}' in STAT#all#ALL: {e}"
                    )

        result = {
            "total_swap_count": total_swap_count,
            "swap_routes": swap_routes,
            "cross_chain_count": cross_chain_count,
            "same_chain_count": same_chain_count,
        }

        return build_response(200, result)

    except ClientError as e:
        print(f"Error in get_total_swap_stats: {e}")
        return build_response(500, {"error": "Could not fetch total swap stats"})


def get_periodic_swap_stats(body):
    """
    Fetches periodic aggregated swap statistics for the last 'limit' periods.
    This is used to populate time-series charts.

    QueryType: "periodic_swap_stats"
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
        # Query for each period in the list
        for period_start in period_starts:
            pk = f"STAT#{period_type}#{period_start}"

            # Query for all 'SWAP#' items in the specific period partition
            response = metrics_table.query(
                KeyConditionExpression=Key("PK").eq(pk)
                & Key("SK").begins_with("SWAP#"),
                ProjectionExpression="SK, #c",
                ExpressionAttributeNames={"#c": "count"},
            )

            items = response.get("Items", [])

            # --- Aggregate stats for this single period ---
            period_swap_routes = {}
            period_cross_chain_count = 0
            period_same_chain_count = 0
            period_total_swaps = 0

            for item in items:
                sk = item.get("SK")
                try:
                    direction = sk.split("#", 1)[1]
                    count = item.get("count", 0)

                    # 1. Add to this period's swap_routes breakdown
                    period_swap_routes[direction] = count

                    # 2. Sum for this period's total
                    period_total_swaps += count

                    # 3. Add to this period's cross-chain vs. same-chain
                    chains = direction.split(",")
                    if len(chains) == 2:
                        if chains[0] == chains[1]:
                            period_same_chain_count += count
                        else:
                            period_cross_chain_count += count
                except Exception as e:
                    print(f"Warning: Could not parse swap SK '{sk}' in {pk}: {e}")

            # Add this period's aggregated data to the main results list
            results.append(
                {
                    "period_start": period_start,
                    "total_swap_count": period_total_swaps,
                    "swap_routes": period_swap_routes,
                    "cross_chain_count": period_cross_chain_count,
                    "same_chain_count": period_same_chain_count,
                }
            )

        # Return the data in descending order (most recent first)
        return build_response(200, {"period_type": period_type, "data": results})

    except ClientError as e:
        print(f"Error in get_periodic_swap_stats: {e}")
        return build_response(500, {"error": "Could not fetch periodic swap stats"})
