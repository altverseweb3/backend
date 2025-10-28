from datetime import datetime, timezone
from botocore.exceptions import ClientError
from ...config import dynamodb, metrics_table
from ...utils.utils import build_response, get_time_periods, get_user_state


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
