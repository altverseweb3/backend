import json
from datetime import datetime, timezone
from botocore.exceptions import ClientError
from ..config import dynamodb, metrics_table
from ..utils.utils import build_response, get_time_periods, get_client_ip


def get_user_state(user_address):
    """
    Checks if a user is new and returns their last active time.
    Returns:
        (is_new_user, last_active_timestamp)
    """
    try:
        response = metrics_table.get_item(
            Key={"PK": f"USER#{user_address}", "SK": "STATS"},
            ProjectionExpression="last_active_timestamp",
        )
        if "Item" not in response:
            return (True, None)  # User is new
        else:
            # User exists, return their last active time
            return (False, response["Item"].get("last_active_timestamp"))

    except ClientError as e:
        print(f"Error checking for new user {user_address}: {e}")
        # Fail safe: assume not new and not active to prevent overcounting
        return (False, datetime.now(timezone.utc).isoformat())


def process_entrance():
    """Handles the logic for a DApp entrance event."""
    try:
        now = datetime.now(timezone.utc)
        periods = get_time_periods(now)
        period_keys = {
            "daily": periods["daily"],
            "weekly": periods["weekly"],
            "monthly": periods["monthly"],
        }

        # 1. Update All-Time General Stats
        metrics_table.update_item(
            Key={"PK": "STAT#all#ALL", "SK": "GENERAL"},
            UpdateExpression="SET dapp_entrances = if_not_exists(dapp_entrances, :start) + :inc",
            ExpressionAttributeValues={":inc": 1, ":start": 0},
        )

        # 2. Update Periodic Stats
        for period_type, start_date in period_keys.items():
            metrics_table.update_item(
                Key={"PK": f"STAT#{period_type}#{start_date}", "SK": "GENERAL"},
                UpdateExpression="SET dapp_entrances = if_not_exists(dapp_entrances, :start) + :inc",
                ExpressionAttributeValues={":inc": 1, ":start": 0},
            )

        return build_response(200, {"message": "Entrance recorded successfully"})
    except ClientError as e:
        print(f"Error in process_entrance: {e}")
        return build_response(500, {"error": "Could not record entrance event"})


def process_swap(payload, ip_address):
    """Processes a swap payload to update all relevant metrics."""
    try:
        required = [
            "user_address",
            "tx_hash",
            "protocol",
            "swap_provider",
            "source_chain",
            "source_token_address",
            "source_token_symbol",
            "amount_in",
            "destination_chain",
            "destination_token_address",
            "destination_token_symbol",
            "amount_out",
            "timestamp",
        ]
        if not all(field in payload for field in required):
            return build_response(
                400,
                {
                    "error": f"Swap payload missing one or more required fields: {required}"
                },
            )

        user_address = payload["user_address"]
        now_dt = datetime.now(timezone.utc)
        now_ts_iso = now_dt.isoformat()

        # 1. Get the user's state before the transaction
        is_new, last_active_ts = get_user_state(user_address)

        # 2. Get time periods for now
        current_periods = get_time_periods(now_dt)

        # 3. Determine if this is the user's first action in each period
        active_inc = {"daily": 0, "weekly": 0, "monthly": 0}

        if is_new:
            # If they are a new user, they are active in all periods
            active_inc = {"daily": 1, "weekly": 1, "monthly": 1}
        elif last_active_ts:
            # If they are an existing user, compare their last active time
            last_active_dt = datetime.fromisoformat(last_active_ts)
            last_active_periods = get_time_periods(last_active_dt)

            if last_active_periods["daily"] != current_periods["daily"]:
                active_inc["daily"] = 1
            if last_active_periods["weekly"] != current_periods["weekly"]:
                active_inc["weekly"] = 1
            if last_active_periods["monthly"] != current_periods["monthly"]:
                active_inc["monthly"] = 1

        transaction_items = []

        # 1. Record Individual Swap
        swap_item = payload.copy()
        swap_item["PK"] = f"USER#{user_address}"
        swap_item["SK"] = f"SWAP#{payload['timestamp']}#{payload['tx_hash']}"
        swap_item["tx_type"] = "SWAP"
        transaction_items.append(
            {"Put": {"TableName": metrics_table.name, "Item": swap_item}}
        )

        # 2. Update User Stats
        xp_to_add = 50
        user_stats_expr = (
            "SET total_swap_count = if_not_exists(total_swap_count, :z) + :o, "
            "last_active_timestamp = :ts, "
            "total_xp = if_not_exists(total_xp, :z) + :xp_val"
        )
        user_stats_vals = {
            ":o": 1,
            ":z": 0,
            ":ts": now_ts_iso,
            ":xp_val": xp_to_add,
        }
        if is_new:
            user_stats_expr += ", first_active_timestamp = :ts, ip_address = :ip, leaderboard_scope = :scope"
            user_stats_vals[":ip"] = ip_address
            user_stats_vals[":scope"] = "GLOBAL"

        transaction_items.append(
            {
                "Update": {
                    "TableName": metrics_table.name,
                    "Key": {"PK": f"USER#{user_address}", "SK": "STATS"},
                    "UpdateExpression": user_stats_expr,
                    "ExpressionAttributeValues": user_stats_vals,
                }
            }
        )

        # 3. Update ALL-TIME General Stats
        all_time_general_expr = "SET swap_count = if_not_exists(swap_count, :z) + :o"
        all_time_general_vals = {":o": 1, ":z": 0}
        if is_new:
            all_time_general_expr += ", new_users = if_not_exists(new_users, :z) + :o"

        transaction_items.append(
            {
                "Update": {
                    "TableName": metrics_table.name,
                    "Key": {"PK": "STAT#all#ALL", "SK": "GENERAL"},
                    "UpdateExpression": all_time_general_expr,
                    "ExpressionAttributeValues": all_time_general_vals,
                }
            }
        )

        # 4. Update ALL-TIME Swap-Specific Stats
        all_time_direction_sk = (
            f"SWAP#{payload['source_chain']},{payload['destination_chain']}"
        )
        transaction_items.append(
            {
                "Update": {
                    "TableName": metrics_table.name,
                    "Key": {"PK": "STAT#all#ALL", "SK": all_time_direction_sk},
                    "UpdateExpression": "SET #c = if_not_exists(#c, :z) + :o",
                    "ExpressionAttributeNames": {"#c": "count"},
                    "ExpressionAttributeValues": {":o": 1, ":z": 0},
                }
            }
        )

        # 5. & 6. Update Periodic Stats (General and Swap-Specific)
        period_keys = {
            "daily": current_periods["daily"],
            "weekly": current_periods["weekly"],
            "monthly": current_periods["monthly"],
        }

        for period_type, start_date in period_keys.items():
            # General Stats
            general_stats_expr = (
                "SET swap_count = if_not_exists(swap_count, :z) + :o, "
                "active_users = if_not_exists(active_users, :z) + :active_inc"
            )
            general_stats_vals = {
                ":o": 1,
                ":z": 0,
                ":active_inc": active_inc[period_type],
            }

            if is_new:
                general_stats_expr += ", new_users = if_not_exists(new_users, :z) + :o"

            transaction_items.append(
                {
                    "Update": {
                        "TableName": metrics_table.name,
                        "Key": {
                            "PK": f"STAT#{period_type}#{start_date}",
                            "SK": "GENERAL",
                        },
                        "UpdateExpression": general_stats_expr,
                        "ExpressionAttributeValues": general_stats_vals,
                    }
                }
            )

            # Swap Stats
            direction_sk = (
                f"SWAP#{payload['source_chain']},{payload['destination_chain']}"
            )
            transaction_items.append(
                {
                    "Update": {
                        "TableName": metrics_table.name,
                        "Key": {
                            "PK": f"STAT#{period_type}#{start_date}",
                            "SK": direction_sk,
                        },
                        "UpdateExpression": "SET #c = if_not_exists(#c, :z) + :o",
                        "ExpressionAttributeNames": {"#c": "count"},
                        "ExpressionAttributeValues": {":o": 1, ":z": 0},
                    }
                }
            )

        # 7. Update Leaderboard
        transaction_items.append(
            {
                "Update": {
                    "TableName": metrics_table.name,
                    "Key": {
                        "PK": f'LEADERBOARD#{current_periods["leaderboard_week"]}',
                        "SK": f"USER#{user_address}",
                    },
                    "UpdateExpression": "SET xp = if_not_exists(xp, :z) + :xp_val, first_xp_timestamp = if_not_exists(first_xp_timestamp, :ts)",
                    "ExpressionAttributeValues": {
                        ":xp_val": 50,
                        ":z": 0,
                        ":ts": now_ts_iso,
                    },
                }
            }
        )

        dynamodb.meta.client.transact_write_items(TransactItems=transaction_items)
        return build_response(200, {"message": "Swap event processed successfully"})

    except ClientError as e:
        print(
            f"DynamoDB Transaction Error in process_swap: {e.response['Error']['Message']}"
        )
        return build_response(500, {"error": "Could not process swap transaction"})


def process_lending(payload, ip_address):
    """Processes a lending payload to update all relevant metrics."""
    try:
        required = [
            "user_address",
            "tx_hash",
            "protocol",
            "action",
            "chain",
            "market_name",
            "token_address",
            "token_symbol",
            "amount",
            "timestamp",
        ]
        if not all(field in payload for field in required):
            return build_response(
                400,
                {
                    "error": f"Lending payload missing one or more required fields: {required}"
                },
            )

        user_address = payload["user_address"]
        now_dt = datetime.now(timezone.utc)
        now_ts_iso = now_dt.isoformat()

        is_new, last_active_ts = get_user_state(user_address)
        current_periods = get_time_periods(now_dt)

        active_inc = {"daily": 0, "weekly": 0, "monthly": 0}
        if is_new:
            active_inc = {"daily": 1, "weekly": 1, "monthly": 1}
        elif last_active_ts:
            last_active_dt = datetime.fromisoformat(last_active_ts)
            last_active_periods = get_time_periods(last_active_dt)
            if last_active_periods["daily"] != current_periods["daily"]:
                active_inc["daily"] = 1
            if last_active_periods["weekly"] != current_periods["weekly"]:
                active_inc["weekly"] = 1
            if last_active_periods["monthly"] != current_periods["monthly"]:
                active_inc["monthly"] = 1

        transaction_items = []

        # 1. Record Individual Lending Action
        lending_item = payload.copy()
        lending_item["PK"] = f"USER#{user_address}"
        lending_item["SK"] = f"LEND#{payload['timestamp']}#{payload['tx_hash']}"
        lending_item["tx_type"] = "LEND"
        transaction_items.append(
            {"Put": {"TableName": metrics_table.name, "Item": lending_item}}
        )

        # 2. Update User Stats
        xp_to_add = 100
        user_stats_expr = (
            "SET total_lending_count = if_not_exists(total_lending_count, :z) + :o, "
            "last_active_timestamp = :ts, "
            "total_xp = if_not_exists(total_xp, :z) + :xp_val"
        )
        user_stats_vals = {
            ":o": 1,
            ":z": 0,
            ":ts": now_ts_iso,
            ":xp_val": xp_to_add,
        }
        if is_new:
            user_stats_expr += ", first_active_timestamp = :ts, ip_address = :ip, leaderboard_scope = :scope"
            user_stats_vals[":ip"] = ip_address
            user_stats_vals[":scope"] = "GLOBAL"

        transaction_items.append(
            {
                "Update": {
                    "TableName": metrics_table.name,
                    "Key": {"PK": f"USER#{user_address}", "SK": "STATS"},
                    "UpdateExpression": user_stats_expr,
                    "ExpressionAttributeValues": user_stats_vals,
                }
            }
        )

        # 3. Update ALL-TIME General Stats
        all_time_general_expr = (
            "SET lending_count = if_not_exists(lending_count, :z) + :o"
        )
        all_time_general_vals = {":o": 1, ":z": 0}
        if is_new:
            all_time_general_expr += ", new_users = if_not_exists(new_users, :z) + :o"

        transaction_items.append(
            {
                "Update": {
                    "TableName": metrics_table.name,
                    "Key": {"PK": "STAT#all#ALL", "SK": "GENERAL"},
                    "UpdateExpression": all_time_general_expr,
                    "ExpressionAttributeValues": all_time_general_vals,
                }
            }
        )

        # 4. Update ALL-TIME Lending-Specific Stats
        all_time_lending_sk = f"LENDING#{payload['chain']}#{payload['market_name']}"
        transaction_items.append(
            {
                "Update": {
                    "TableName": metrics_table.name,
                    "Key": {"PK": "STAT#all#ALL", "SK": all_time_lending_sk},
                    "UpdateExpression": "SET #c = if_not_exists(#c, :z) + :o",
                    "ExpressionAttributeNames": {"#c": "count"},
                    "ExpressionAttributeValues": {":o": 1, ":z": 0},
                }
            }
        )

        # 5. & 6. Update Periodic Stats
        period_keys = {
            "daily": current_periods["daily"],
            "weekly": current_periods["weekly"],
            "monthly": current_periods["monthly"],
        }

        for period_type, start_date in period_keys.items():
            # General Stats
            general_stats_expr = (
                "SET lending_count = if_not_exists(lending_count, :z) + :o, "
                "active_users = if_not_exists(active_users, :z) + :active_inc"
            )
            general_stats_vals = {
                ":o": 1,
                ":z": 0,
                ":active_inc": active_inc[period_type],
            }

            if is_new:
                general_stats_expr += ", new_users = if_not_exists(new_users, :z) + :o"

            transaction_items.append(
                {
                    "Update": {
                        "TableName": metrics_table.name,
                        "Key": {
                            "PK": f"STAT#{period_type}#{start_date}",
                            "SK": "GENERAL",
                        },
                        "UpdateExpression": general_stats_expr,
                        "ExpressionAttributeValues": general_stats_vals,
                    }
                }
            )

            # Lending Stats
            lending_sk = f"LENDING#{payload['chain']}#{payload['market_name']}"
            transaction_items.append(
                {
                    "Update": {
                        "TableName": metrics_table.name,
                        "Key": {
                            "PK": f"STAT#{period_type}#{start_date}",
                            "SK": lending_sk,
                        },
                        "UpdateExpression": "SET #c = if_not_exists(#c, :z) + :o",
                        "ExpressionAttributeNames": {"#c": "count"},
                        "ExpressionAttributeValues": {":o": 1, ":z": 0},
                    }
                }
            )

        # 7. Update Leaderboard
        transaction_items.append(
            {
                "Update": {
                    "TableName": metrics_table.name,
                    "Key": {
                        "PK": f'LEADERBOARD#{current_periods["leaderboard_week"]}',
                        "SK": f"USER#{user_address}",
                    },
                    "UpdateExpression": "SET xp = if_not_exists(xp, :z) + :xp_val, first_xp_timestamp = if_not_exists(first_xp_timestamp, :ts)",
                    "ExpressionAttributeValues": {
                        ":xp_val": xp_to_add,
                        ":z": 0,
                        ":ts": now_ts_iso,
                    },
                }
            }
        )

        dynamodb.meta.client.transact_write_items(TransactItems=transaction_items)
        return build_response(200, {"message": "Lending event processed successfully"})

    except ClientError as e:
        print(
            f"DynamoDB TransactionError in process_lending: {e.response['Error']['Message']}"
        )
        return build_response(500, {"error": "Could not process lending transaction"})


def process_earn(payload, ip_address):
    """Processes an earn payload to update all relevant metrics."""
    try:
        required = [
            "user_address",
            "tx_hash",
            "protocol",
            "action",
            "chain",
            "vault_name",
            "vault_address",
            "token_address",
            "token_symbol",
            "amount",
            "timestamp",
        ]
        if not all(field in payload for field in required):
            return build_response(
                400,
                {
                    "error": f"Earn payload missing one or more required fields: {required}"
                },
            )

        user_address = payload["user_address"]
        now_dt = datetime.now(timezone.utc)
        now_ts_iso = now_dt.isoformat()

        is_new, last_active_ts = get_user_state(user_address)
        current_periods = get_time_periods(now_dt)

        active_inc = {"daily": 0, "weekly": 0, "monthly": 0}
        if is_new:
            active_inc = {"daily": 1, "weekly": 1, "monthly": 1}
        elif last_active_ts:
            last_active_dt = datetime.fromisoformat(last_active_ts)
            last_active_periods = get_time_periods(last_active_dt)
            if last_active_periods["daily"] != current_periods["daily"]:
                active_inc["daily"] = 1
            if last_active_periods["weekly"] != current_periods["weekly"]:
                active_inc["weekly"] = 1
            if last_active_periods["monthly"] != current_periods["monthly"]:
                active_inc["monthly"] = 1

        transaction_items = []

        # 1. Record Individual Earn Action
        earn_item = payload.copy()
        earn_item["PK"] = f"USER#{user_address}"
        earn_item["SK"] = f"EARN#{payload['timestamp']}#{payload['tx_hash']}"
        earn_item["tx_type"] = "EARN"
        transaction_items.append(
            {"Put": {"TableName": metrics_table.name, "Item": earn_item}}
        )

        # 2. Update User Stats
        xp_to_add = 100
        user_stats_expr = (
            "SET total_earn_count = if_not_exists(total_earn_count, :z) + :o, "
            "last_active_timestamp = :ts, "
            "total_xp = if_not_exists(total_xp, :z) + :xp_val"
        )
        user_stats_vals = {
            ":o": 1,
            ":z": 0,
            ":ts": now_ts_iso,
            ":xp_val": xp_to_add,
        }
        if is_new:
            user_stats_expr += ", first_active_timestamp = :ts, ip_address = :ip, leaderboard_scope = :scope"
            user_stats_vals[":ip"] = ip_address
            user_stats_vals[":scope"] = "GLOBAL"

        transaction_items.append(
            {
                "Update": {
                    "TableName": metrics_table.name,
                    "Key": {"PK": f"USER#{user_address}", "SK": "STATS"},
                    "UpdateExpression": user_stats_expr,
                    "ExpressionAttributeValues": user_stats_vals,
                }
            }
        )

        # 3. Update ALL-TIME General Stats
        all_time_general_expr = "SET earn_count = if_not_exists(earn_count, :z) + :o"
        all_time_general_vals = {":o": 1, ":z": 0}
        if is_new:
            all_time_general_expr += ", new_users = if_not_exists(new_users, :z) + :o"

        transaction_items.append(
            {
                "Update": {
                    "TableName": metrics_table.name,
                    "Key": {"PK": "STAT#all#ALL", "SK": "GENERAL"},
                    "UpdateExpression": all_time_general_expr,
                    "ExpressionAttributeValues": all_time_general_vals,
                }
            }
        )

        # 4. Update ALL-TIME Earn-Specific Stats
        all_time_earn_sk = f"EARN#{payload['chain']}#{payload['protocol']}"
        transaction_items.append(
            {
                "Update": {
                    "TableName": metrics_table.name,
                    "Key": {"PK": "STAT#all#ALL", "SK": all_time_earn_sk},
                    "UpdateExpression": "SET #c = if_not_exists(#c, :z) + :o",
                    "ExpressionAttributeNames": {"#c": "count"},
                    "ExpressionAttributeValues": {":o": 1, ":z": 0},
                }
            }
        )

        # 5. & 6. Update Periodic Stats (General and Earn-Specific)
        period_keys = {
            "daily": current_periods["daily"],
            "weekly": current_periods["weekly"],
            "monthly": current_periods["monthly"],
        }
        for period_type, start_date in period_keys.items():
            # General Stats
            general_stats_expr = (
                "SET earn_count = if_not_exists(earn_count, :z) + :o, "
                "active_users = if_not_exists(active_users, :z) + :active_inc"
            )
            general_stats_vals = {
                ":o": 1,
                ":z": 0,
                ":active_inc": active_inc[period_type],
            }

            if is_new:
                general_stats_expr += ", new_users = if_not_exists(new_users, :z) + :o"

            transaction_items.append(
                {
                    "Update": {
                        "TableName": metrics_table.name,
                        "Key": {
                            "PK": f"STAT#{period_type}#{start_date}",
                            "SK": "GENERAL",
                        },
                        "UpdateExpression": general_stats_expr,
                        "ExpressionAttributeValues": general_stats_vals,
                    }
                }
            )

            # Periodic Earn Stats
            earn_sk = f"EARN#{payload['chain']}#{payload['protocol']}"
            transaction_items.append(
                {
                    "Update": {
                        "TableName": metrics_table.name,
                        "Key": {
                            "PK": f"STAT#{period_type}#{start_date}",
                            "SK": earn_sk,
                        },
                        "UpdateExpression": "SET #c = if_not_exists(#c, :z) + :o",
                        "ExpressionAttributeNames": {"#c": "count"},
                        "ExpressionAttributeValues": {":o": 1, ":z": 0},
                    }
                }
            )

        # 7. Update Leaderboard
        transaction_items.append(
            {
                "Update": {
                    "TableName": metrics_table.name,
                    "Key": {
                        "PK": f'LEADERBOARD#{current_periods["leaderboard_week"]}',
                        "SK": f"USER#{user_address}",
                    },
                    "UpdateExpression": "SET xp = if_not_exists(xp, :z) + :xp_val, first_xp_timestamp = if_not_exists(first_xp_timestamp, :ts)",
                    "ExpressionAttributeValues": {
                        ":xp_val": xp_to_add,
                        ":z": 0,
                        ":ts": now_ts_iso,
                    },
                }
            }
        )

        # Execute the entire transaction
        dynamodb.meta.client.transact_write_items(TransactItems=transaction_items)
        return build_response(200, {"message": "Earn event processed successfully"})

    except ClientError as e:
        print(
            f"DynamoDB Transaction Error in process_earn: {e.response['Error']['Message']}"
        )
        return build_response(500, {"error": "Could not process earn transaction"})


# Expected event body structure for the /metrics endpoint:
# {
#   "eventType": "entrance' | "swap" | "lending" | "earn",
#   "payload": { ...event specific data... }
# }
# Note: "payload" is not required for "entrance" eventType.
def handle(event):
    """
    Single endpoint to handle various metric events (swap, lend, earn, entrance).
    Routes to the appropriate processor based on the 'eventType' in the request body.
    """
    try:
        body = json.loads(event.get("body", "{}"))
        event_type = body.get("eventType")
        payload = body.get("payload", {})  # Default to empty dict if not present

        if not event_type:
            return build_response(
                400, {"error": "Request body must include 'eventType'"}
            )

        # Extract client IP once for potential use in processors
        ip_address = get_client_ip(event)

        if event_type == "entrance":
            return process_entrance()
        elif event_type == "swap":
            return process_swap(payload, ip_address)
        elif event_type == "lending":
            return process_lending(payload, ip_address)
        elif event_type == "earn":
            return process_earn(payload, ip_address)
        else:
            return build_response(400, {"error": f"Unknown eventType: '{event_type}'"})

    except json.JSONDecodeError:
        return build_response(400, {"error": "Invalid JSON body"})
    except Exception as e:
        print(f"An unexpected error occurred in handle_metrics: {str(e)}")
        return build_response(500, {"error": "An internal server error occurred"})
