from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key
from ...config import metrics_table
from ...utils.utils import build_response


def get_total_swap_stats(body):
    """
    Fetches all-time aggregated swap statistics.

    This function queries the single STAT#all#ALL partition to get:
    1. The 'GENERAL' item for the overall total_swap_count.
    2. All 'SWAP#{direction}' items for a breakdown by route.
    It then aggregates this data to provide a total count, a route
    breakdown, and a cross-chain vs. same-chain summary.
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
    Fetches periodic aggregated swap statistics for a specific time period.

    Requires 'period_type' (daily, weekly, monthly) and 'start_date'
    (YYYY-MM-DD) in the request body.

    This function queries a single partition (e.g., 'STAT#daily#2023-10-27')
    and reads all items starting with 'SWAP#' to build the analytics.
    """
    try:
        period_type = body.get("period_type")
        start_date = body.get("start_date")

        if not period_type or not start_date:
            return build_response(
                400,
                {"error": "Missing required fields: 'period_type' and 'start_date'"},
            )

        pk = f"STAT#{period_type}#{start_date}"

        # Query for all 'SWAP#' items in the specific period partition
        response = metrics_table.query(
            KeyConditionExpression=Key("PK").eq(pk) & Key("SK").begins_with("SWAP#")
        )

        items = response.get("Items", [])

        swap_routes = {}
        cross_chain_count = 0
        same_chain_count = 0

        for item in items:
            sk = item.get("SK")

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
                print(f"Warning: Could not parse swap SK '{sk}' in {pk}: {e}")

        result = {
            "period": start_date,
            "period_type": period_type,
            "swap_routes": swap_routes,
            "cross_chain_count": cross_chain_count,
            "same_chain_count": same_chain_count,
        }

        return build_response(200, result)

    except ClientError as e:
        print(f"Error in get_periodic_swap_stats: {e}")
        return build_response(500, {"error": "Could not fetch periodic swap stats"})
