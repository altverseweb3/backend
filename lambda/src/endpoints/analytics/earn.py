import json
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key
from ...config import metrics_table
from ...utils.utils import (
    build_response,
    get_past_periods,
    validate_period_type,
    validate_and_sanitize_limit,
)


def get_total_earn_stats(body):
    """
    Fetches the global, all-time total earn count and breakdown by chain and protocol.

    QueryType: "total_earn_stats"
    Body: {}

    Returns:
        Response with total earn count and breakdowns by chain, protocol,
        and chain-protocol combinations
    """
    try:
        # Query the entire STAT#all#ALL partition
        # This efficiently gets both the GENERAL item and all EARN# items
        response = metrics_table.query(
            KeyConditionExpression=Key("PK").eq("STAT#all#ALL")
        )

        items = response.get("Items", [])

        # Process the results
        total_earn_count = 0
        by_chain = {}
        by_protocol = {}
        by_chain_protocol = {}

        for item in items:
            sk = item.get("SK")

            # Get the total count from the GENERAL item
            if sk == "GENERAL":
                total_earn_count = item.get("earn_count", 0)

            # Process breakdown items
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

        # Return the combined data
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

    QueryType: "periodic_earn_stats"
    Body: {
        "period_type": "daily" | "weekly" | "monthly",
        "limit": 7
    }

    Returns:
        Response with period_type and array of period-based earn stats with
        breakdowns by chain, protocol, and chain-protocol combinations
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

        # Get the list of period start dates
        period_starts = get_past_periods(period_type, limit)

        results = []
        # Query for each period in the list
        for period_start in period_starts:
            pk = f"STAT#{period_type}#{period_start}"

            # Query for all 'EARN#' items in the specific period partition
            response = metrics_table.query(
                KeyConditionExpression=Key("PK").eq(pk)
                & Key("SK").begins_with("EARN#"),
                ProjectionExpression="SK, #c",
                ExpressionAttributeNames={"#c": "count"},
            )

            items = response.get("Items", [])

            # Aggregate stats for this single period
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

                        # Add to this period's total
                        period_total_earn += count

                        # Add to the chain-protocol breakdown
                        period_by_chain_protocol[f"{chain}#{protocol}"] = count

                        # Aggregate by chain
                        period_by_chain[chain] = period_by_chain.get(chain, 0) + count

                        # Aggregate by protocol
                        period_by_protocol[protocol] = (
                            period_by_protocol.get(protocol, 0) + count
                        )

                except Exception as e:
                    print(f"Warning: Could not parse earn SK '{sk}' in {pk}: {e}")

            # Add this period's aggregated data to the main results list
            results.append(
                {
                    "period_start": period_start,
                    "total_earn_count": period_total_earn,
                    "by_chain": period_by_chain,
                    "by_protocol": period_by_protocol,
                    "by_chain_protocol": period_by_chain_protocol,
                }
            )

        # Return the data in descending order (most recent first)
        return build_response(200, results)

    except ClientError as e:
        print(f"Error in get_periodic_earn_stats: {e}")
        return build_response(500, {"error": "Could not fetch periodic earn stats"})
