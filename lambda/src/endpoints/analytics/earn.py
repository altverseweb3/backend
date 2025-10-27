import json
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key
from ...config import metrics_table
from ...utils.utils import build_response, get_past_periods


def get_total_earn_stats(body):
    """
    Fetches the global, all-time total earn count and a
    breakdown by chain and protocol.
    This is used for top-level KPI scorecards and donut charts.

    QueryType: "total_earn_stats"
    Body: {}
    """
    try:
        # 1. Query the entire STAT#all#ALL partition
        # This efficiently gets both the GENERAL item and all EARN# items
        response = metrics_table.query(
            KeyConditionExpression=Key("PK").eq("STAT#all#ALL")
        )

        items = response.get("Items", [])

        # 2. Process the results
        total_earn_count = 0
        by_chain = {}
        by_protocol = {}
        by_chain_protocol = {}

        for item in items:
            sk = item.get("SK")

            # 2a. Get the total count from the GENERAL item
            if sk == "GENERAL":
                total_earn_count = item.get("earn_count", 0)

            # 2b. Process breakdown items
            elif sk and sk.startswith("EARN#"):
                count = item.get("count", 0)
                try:
                    # SK format is "EARN#{chain}#{protocol}"
                    parts = sk.split("#")
                    if len(parts) == 3:
                        chain = parts[1]
                        protocol = parts[2]

                        # Add to chain-protocol breakdown
                        by_chain_protocol[f"{chain}#{protocol}"] = count

                        # Aggregate by chain
                        by_chain[chain] = by_chain.get(chain, 0) + count

                        # Aggregate by protocol
                        by_protocol[protocol] = by_protocol.get(protocol, 0) + count

                except Exception as e:
                    print(f"Warning: Could not parse all-time earn SK '{sk}': {e}")

        # 3. Return the combined data
        return build_response(
            200,
            {
                "total_earn_count": total_earn_count,
                "by_chain": by_chain,
                "by_protocol": by_protocol,
                "by_chain_protocol": by_chain_protocol,
            },
        )

    except ClientError as e:
        print(f"Error in get_total_earn_stats: {e}")
        return build_response(500, {"error": "Could not fetch total earn stats"})


def get_periodic_earn_stats(body):
    """
    Fetches periodic aggregated earn statistics for the last 'limit' periods.
    This is used to populate time-series charts for earn activity breakdowns.

    QueryType: "periodic_earn_stats"
    Body: {
        "period_type": "daily" | "weekly" | "monthly",
        "limit": 8
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

        # 1. Get the list of period start dates (e.g., ["2023-10-27", "2023-10-26", ...])
        period_starts = get_past_periods(period_type, limit)

        results = []
        # 2. Query for each period in the list
        for period_start in period_starts:
            pk = f"STAT#{period_type}#{period_start}"

            # Query for all 'EARN#' items in the specific period partition
            response = metrics_table.query(
                KeyConditionExpression=Key("PK").eq(pk)
                & Key("SK").begins_with("EARN#"),
                ProjectionExpression="SK, #c",  # Only fetch the SK and count
                ExpressionAttributeNames={"#c": "count"},
            )

            items = response.get("Items", [])

            # --- 3. Aggregate stats for this single period ---
            period_by_chain = {}
            period_by_protocol = {}
            period_by_chain_protocol = {}  # This is the raw data from DDB
            period_total_earn = 0

            for item in items:
                sk = item.get("SK")
                count = item.get("count", 0)

                try:
                    # SK format is "EARN#{chain}#{protocol}"
                    parts = sk.split("#")
                    if len(parts) == 3:
                        chain = parts[1]
                        protocol = parts[2]

                        # 3a. Add to this period's total
                        period_total_earn += count

                        # 3b. Add to the chain-protocol breakdown
                        period_by_chain_protocol[f"{chain}#{protocol}"] = count

                        # 3c. Aggregate by chain
                        period_by_chain[chain] = period_by_chain.get(chain, 0) + count

                        # 3d. Aggregate by protocol
                        period_by_protocol[protocol] = (
                            period_by_protocol.get(protocol, 0) + count
                        )

                except Exception as e:
                    print(f"Warning: Could not parse earn SK '{sk}' in {pk}: {e}")

            # 4. Add this period's aggregated data to the main results list
            results.append(
                {
                    "period_start": period_start,
                    "total_earn_count": period_total_earn,
                    "by_chain": period_by_chain,
                    "by_protocol": period_by_protocol,
                    "by_chain_protocol": period_by_chain_protocol,
                }
            )

        # 5. Return the data in descending order (most recent first)
        return build_response(200, {"period_type": period_type, "data": results})

    except ClientError as e:
        print(f"Error in get_periodic_earn_stats: {e}")
        return build_response(500, {"error": "Could not fetch periodic earn stats"})
