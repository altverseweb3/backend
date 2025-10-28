import json
from boto3.dynamodb.conditions import Key
from ...config import metrics_table
from ...utils.utils import (
    build_response,
    get_past_periods,
    validate_period_type,
    validate_and_sanitize_limit,
)


def get_total_lending_stats(body):
    """
    Fetches all-time lending stats with breakdown by chain and market.

    QueryType: "total_lending_stats"
    Body: {}

    Returns:
        Response with total lending count and breakdown by chain and market
    """
    try:
        pk_all = "STAT#all#ALL"

        # Get total lending count from the GENERAL item
        response_general = metrics_table.get_item(
            Key={"PK": pk_all, "SK": "GENERAL"}, ProjectionExpression="lending_count"
        )
        total_count = response_general.get("Item", {}).get("lending_count", 0)

        # Get all-time breakdown by querying for LENDING# items
        response_breakdown = metrics_table.query(
            KeyConditionExpression=Key("PK").eq(pk_all)
            & Key("SK").begins_with("LENDING#"),
            ProjectionExpression="SK, #c",
            ExpressionAttributeNames={"#c": "count"},
        )

        breakdown = []
        for item in response_breakdown.get("Items", []):
            try:
                # SK is "LENDING#{chain}#{market_name}"
                parts = item["SK"].split("#")
                chain = parts[1]
                market = parts[2]
                count = item.get("count", 0)
                breakdown.append({"chain": chain, "market": market, "count": count})
            except (IndexError, TypeError):
                # Log error but continue processing other items
                print(f"Error parsing SK for total lending stats: {item.get('SK')}")
                continue

        return build_response(
            200, {"total_lending_count": total_count, "breakdown": breakdown}
        )

    except Exception as e:
        print(f"Error in get_total_lending_stats: {str(e)}")
        return build_response(500, {"error": "Could not fetch total lending stats"})


def get_periodic_lending_stats(body):
    """
    Fetches periodic lending stats for the last 'limit' periods.

    QueryType: "periodic_lending_stats"
    Body: {
        "period_type": "daily" | "weekly" | "monthly",
        "limit": 7
    }

    Returns:
        Response with period_type and array of period-based lending stats
        with breakdown by chain and market
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
        # Query for each period in the list
        for period_start in period_starts:
            pk = f"STAT#{period_type}#{period_start}"

            # Query for all LENDING# items for this specific period
            response = metrics_table.query(
                KeyConditionExpression=Key("PK").eq(pk)
                & Key("SK").begins_with("LENDING#"),
                ProjectionExpression="SK, #c",
                ExpressionAttributeNames={"#c": "count"},
            )

            period_breakdown = []
            period_total = 0
            for item in response.get("Items", []):
                try:
                    # SK is "LENDING#{chain}#{market_name}"
                    parts = item["SK"].split("#")
                    chain = parts[1]
                    market = parts[2]
                    count = item.get("count", 0)

                    period_breakdown.append(
                        {"chain": chain, "market": market, "count": count}
                    )
                    # We can calculate the period's total by summing the breakdown
                    period_total += count
                except (IndexError, TypeError):
                    print(f"Error parsing SK for periodic lending stats: {item.get('SK')}")
                    continue

            results.append(
                {
                    "period_start": period_start,
                    "total_lending_count": period_total,
                    "breakdown": period_breakdown,
                }
            )

        # Return the data in descending order (most recent first)
        return build_response(200, {"period_type": period_type, "data": results})

    except Exception as e:
        print(f"Error in get_periodic_lending_stats: {str(e)}")
        return build_response(500, {"error": "Could not fetch periodic lending stats"})
