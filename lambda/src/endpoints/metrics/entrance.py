from datetime import datetime, timezone
from botocore.exceptions import ClientError
from ...config import metrics_table
from ...utils.utils import build_response, get_time_periods


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
