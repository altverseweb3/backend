from datetime import datetime, timezone
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key
from ...config import dynamodb, metrics_table
from ...utils.utils import build_response, get_time_periods


def get_leaderboard(payload):
    """
    Fetches paginated leaderboard data from the GSIs.
    Payload:
    {
        "scope": "global" | "weekly",
        "limit": 1000, // Optional, default 50, max 1000
        "lastKey": { ... } // Optional, for pagination
    }
    """
    try:
        # Define a max limit to prevent abuse
        MAX_LEADERBOARD_LIMIT = 1000

        scope = payload.get("scope")

        # Get limit from payload, default to 100, and cap it at the max
        limit = min(int(payload.get("limit", 100)), MAX_LEADERBOARD_LIMIT)

        last_key = payload.get("lastKey")

        if scope not in ["global", "weekly"]:
            return build_response(
                400, {"error": "Invalid scope. Must be 'global' or 'weekly'."}
            )

        query_args = {
            "Limit": limit,
            "ScanIndexForward": False,  # Sort descending by XP
        }

        if last_key:
            query_args["ExclusiveStartKey"] = last_key

        if scope == "global":
            query_args["IndexName"] = "global-leaderboard-by-xp-gsi"
            query_args["KeyConditionExpression"] = Key("leaderboard_scope").eq("GLOBAL")

        elif scope == "weekly":
            now_dt = datetime.now(timezone.utc)
            current_week = get_time_periods(now_dt)["leaderboard_week"]
            query_args["IndexName"] = "leaderboard-by-xp-gsi"
            query_args["KeyConditionExpression"] = Key("PK").eq(
                f"LEADERBOARD#{current_week}"
            )

        # Execute the query
        response = metrics_table.query(**query_args)

        # Format the items for a clean API response
        formatted_items = []
        for item in response.get("Items", []):
            if scope == "global":
                # Base item is USER#{...}#STATS
                formatted_items.append(
                    {
                        "user_address": item["PK"].split("#")[1],
                        "total_xp": int(item.get("total_xp", 0)),
                        "first_active_timestamp": item.get("first_active_timestamp"),
                    }
                )
            elif scope == "weekly":
                # Base item is LEADERBOARD#{...}#USER#{...}
                formatted_items.append(
                    {
                        "user_address": item["SK"].split("#")[1],
                        "xp": int(item.get("xp", 0)),
                        "first_xp_timestamp": item.get("first_xp_timestamp"),
                    }
                )

        return build_response(
            200, {"items": formatted_items, "lastKey": response.get("LastEvaluatedKey")}
        )

    except ClientError as e:
        print(
            f"DynamoDB Query Error in get_leaderboard: {e.response['Error']['Message']}"
        )
        return build_response(500, {"error": "Could not query leaderboard data"})
    except Exception as e:
        print(f"An unexpected error occurred in get_leaderboard: {str(e)}")
        return build_response(500, {"error": "An internal server error occurred"})


def get_user_entry(payload):
    """
    Fetches the global and weekly leaderboard XP for a single user.
    Note: This returns the user's XP, not their numerical rank.
    Payload:
    {
        "user_address": "string" // Required
    }
    """
    try:
        user_address = payload.get("user_address")
        if not user_address:
            return build_response(
                400, {"error": "Missing required parameter: user_address"}
            )

        # Get current week for the weekly leaderboard PK
        now_dt = datetime.now(timezone.utc)
        current_week = get_time_periods(now_dt)["leaderboard_week"]

        # Define the keys for the batch-get
        global_key = {"PK": f"USER#{user_address}", "SK": "STATS"}
        weekly_key = {"PK": f"LEADERBOARD#{current_week}", "SK": f"USER#{user_address}"}

        # Use batch_get_item for efficiency
        response = dynamodb.meta.client.batch_get_item(
            RequestItems={
                metrics_table.name: {
                    "Keys": [global_key, weekly_key],
                    # Optimize read capacity by only projecting needed attributes
                    "ProjectionExpression": "PK, total_xp, xp",
                }
            }
        )

        # Process the response
        items = response.get("Responses", {}).get(metrics_table.name, [])
        result = {"user_address": user_address, "global_total_xp": 0, "weekly_xp": 0}

        for item in items:
            if item["PK"].startswith("USER#"):
                result["global_total_xp"] = int(item.get("total_xp", 0))
            elif item["PK"].startswith("LEADERBOARD#"):
                result["weekly_xp"] = int(item.get("xp", 0))

        return build_response(200, result)

    except ClientError as e:
        print(
            f"DynamoDB BatchGet Error in get_user_entry: {e.response['Error']['Message']}"
        )
        return build_response(500, {"error": "Could not query user rank data"})
    except Exception as e:
        print(f"An unexpected error occurred in get_user_entry: {str(e)}")
        return build_response(500, {"error": "An internal server error occurred"})
