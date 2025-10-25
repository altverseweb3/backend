import json
import time
from datetime import datetime, timedelta, timezone
from botocore.exceptions import ClientError
from ..config import rate_limit_table, RATE_LIMIT, BUCKET_DURATION
from .utils import get_client_ip


# Check the rate limits for an IP address.
def check_rate_limits(ip_address):
    """
    SIMPLE TIME-BASED RULE:
    - IF current time - last_replenish_time >= BUCKET_DURATION (300 seconds),
      THEN completely reset the IP data with 500 fresh credits and a new timestamp.
    - IF credits <= 0 THEN return a 429 response.
    """
    current_time = int(time.time())
    print(f"Rate limit check for {ip_address} at time {current_time}")

    try:
        # Use a consistent read to ensure up-to-date data
        response = rate_limit_table.get_item(
            Key={"ip_address": ip_address}, ConsistentRead=True
        )

        if "Item" not in response:
            # New IP: create a new record with full credits
            print(f"New IP: {ip_address} - Creating new record")
            update_new_ip(ip_address, current_time)
            return True, None

        # Get the current credit count and last replenishment time
        item = response["Item"]
        credits = int(item.get("credits", 0))
        last_replenish_time = int(item.get("last_replenish_time", 0))
        time_since_last_replenish = current_time - last_replenish_time

        print(
            f"IP: {ip_address}, Credits: {credits}, Last replenish: {last_replenish_time}, Time since: {time_since_last_replenish}s"
        )

        # TIME-BASED RULE:
        # If the bucket duration has passed, completely reset the record
        if time_since_last_replenish >= BUCKET_DURATION:
            print(
                f"Time passed: Completely resetting record for {ip_address} after {time_since_last_replenish}s"
            )

            # Set the TTL for tomorrow midnight
            midnight = (datetime.now(timezone.utc) + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            ttl_timestamp = int(midnight.timestamp())

            # IMPORTANT: Use put_item to completely replace the record
            # This ensures we don't have any leftover values from the previous record
            rate_limit_table.put_item(
                Item={
                    "ip_address": ip_address,
                    "credits": RATE_LIMIT,
                    "last_replenish_time": current_time,
                    "ttl": ttl_timestamp,
                }
            )

            # Since we completely reset the record, update our local variables
            credits = RATE_LIMIT
            last_replenish_time = current_time

            print(
                f"Replenishment complete: {ip_address} now has {credits} credits, new timestamp: {last_replenish_time}"
            )

        # After all the checks, if credits are 0 or negative, block the request
        if credits <= 0:
            reset_time = last_replenish_time + BUCKET_DURATION
            time_until_reset = max(0, reset_time - current_time)

            print(
                f"Rate limited: {ip_address} has no credits. Reset in {time_until_reset}s at {reset_time}"
            )

            return False, {
                "limit": RATE_LIMIT,
                "reset_time": reset_time,
                "ip_address": ip_address,
            }

        # If we reach here, there are credits available
        return True, None

    except Exception as e:
        print(f"Error in check_rate_limits: {str(e)}")
        # Allow the request if there's an error checking limits
        return True, None


# Create a new record for an IP address.
def update_new_ip(ip_address, current_time):
    """
    Sets credits to RATE_LIMIT - 1 (deducting one for the current request)
    and sets 'last_replenish_time' to the current time.
    """
    midnight = (datetime.now(timezone.utc) + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    ttl_timestamp = int(midnight.timestamp())

    # Use put_item to ensure a clean record - this will completely replace any existing item
    rate_limit_table.put_item(
        Item={
            "ip_address": ip_address,
            "credits": RATE_LIMIT
            - 1,  # Start with one credit already used for this request
            "last_replenish_time": current_time,
            "ttl": ttl_timestamp,
        }
    )
    print(
        f"Created new record for {ip_address} with {RATE_LIMIT - 1} credits and timestamp {current_time}"
    )


def build_rate_limit_response(bucket_info):
    """
    Build a 429 response with rate limit information.
    """
    current_time = int(time.time())
    reset_time = bucket_info["reset_time"]
    reset_time_str = datetime.fromtimestamp(reset_time).strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )
    seconds_remaining = max(0, reset_time - current_time)

    # Normal case: return 429 response
    return {
        "statusCode": 429,
        "headers": {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Allow-Methods": "ANY,OPTIONS,POST,GET",
            "Content-Type": "application/json",
        },
        "body": json.dumps(
            {
                "error": "Too Many Requests",
                "message": f"Rate limit exceeded. Limit is {bucket_info['limit']} requests per {BUCKET_DURATION} seconds.",
                "reset_at": reset_time_str,
                "retry_after_seconds": seconds_remaining,
            }
        ),
    }


# Main rate-limit handler
def rate_limit(event, context):
    """
    1. Check rate limits - if time has passed, completely reset the record
    2. If allowed, subtract one token; otherwise, return a 429 response
    """
    # Get the client IP
    ip_address = get_client_ip(event)
    if ip_address == "unknown":
        return

    # SIMPLE FLOW:
    # 1. Check if rate limits allow this request
    allowed, bucket_info = check_rate_limits(ip_address)

    # 2. If not allowed (credits are 0), return 429 rate limit response
    if not allowed:
        print(f"Rate limit triggered for {ip_address}")
        return build_rate_limit_response(bucket_info)

    # 3. Decrement one credit for this request
    try:
        response = rate_limit_table.update_item(
            Key={"ip_address": ip_address},
            UpdateExpression="SET credits = credits - :one",
            ConditionExpression="credits > :zero",
            ExpressionAttributeValues={":one": 1, ":zero": 0},
            ReturnValues="UPDATED_NEW",
        )

        if "Attributes" in response:
            new_credits = int(response["Attributes"].get("credits", 0))
            print(f"Credit used: {ip_address} now has {new_credits} credits remaining")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            # This means credits would go negative - return 429 response
            print(f"Condition check failed for {ip_address} - no credits available")

            # Get the current record to build the rate limit response
            item = rate_limit_table.get_item(Key={"ip_address": ip_address}).get(
                "Item", {}
            )
            last_replenish_time = int(item.get("last_replenish_time", 0))
            reset_time = last_replenish_time + BUCKET_DURATION

            bucket_info = {
                "limit": RATE_LIMIT,
                "reset_time": reset_time,
                "ip_address": ip_address,
            }
            return build_rate_limit_response(bucket_info)
        else:
            print(f"Error in update_rate_limits: {str(e)}")

    # 4. If we reach here, the request is allowed
    return
