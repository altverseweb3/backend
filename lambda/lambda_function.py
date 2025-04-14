import json
import os
import requests
import boto3
import time
from botocore.exceptions import ClientError
from datetime import datetime, timedelta, timezone

# Configure the DynamoDB client
dynamodb = boto3.resource("dynamodb")
rate_limit_table = dynamodb.Table(
    os.environ.get("RATE_LIMIT_TABLE_NAME", "api_rate_limits")
)

# Rate limit configuration
RATE_LIMIT = 500  # Number of requests allowed in 5 minutes
BUCKET_DURATION = 300  # 5 minutes in seconds

# Special key for tracking the last database reset
RESET_TRACKER_KEY = "daily_reset_tracker"

def get_client_ip(event):
    """Extract client IP address from Lambda event."""
    if "requestContext" in event and "identity" in event["requestContext"]:
        return event["requestContext"]["identity"].get("sourceIp", "unknown")
    headers = event.get("headers", {})
    if headers and "X-Forwarded-For" in headers:
        # X-Forwarded-For may have a list; we take the first
        return headers["X-Forwarded-For"].split(",")[0].strip()
    return "unknown"

# Check for daily Reset IP credits
def check_daily_reset():
    """
    Check if a new day has begun.
    If so, purge the entire DynamoDB table (except for the tracker) and update the tracker.
    """
    current_time = int(time.time())
    current_date = datetime.fromtimestamp(current_time, tz=timezone.utc).date()
    try:
        response = rate_limit_table.get_item(Key={"ip_address": RESET_TRACKER_KEY})
        if "Item" in response:
            last_reset_time = int(response["Item"].get("last_reset_time", 0))
            last_reset_date = datetime.fromtimestamp(last_reset_time, tz=timezone.utc).date()
            if current_date > last_reset_date:
                perform_daily_reset(current_time)
                return True
        else:
            # If no tracker exists, create one.
            rate_limit_table.put_item(
                Item={
                    "ip_address": RESET_TRACKER_KEY,
                    "last_reset_time": current_time
                }
            )
    except Exception as e:
        print(f"Error in check_daily_reset: {str(e)}")
    return False

# Perform reset of credits
def perform_daily_reset(current_time):
    """
    Purge all IP records (except the daily reset tracker) from the DynamoDB table.
    """
    try:
        response = rate_limit_table.scan(ProjectionExpression="ip_address")
        with rate_limit_table.batch_writer() as batch:
            for item in response.get("Items", []):
                ip = item.get("ip_address")
                if ip != RESET_TRACKER_KEY:
                    batch.delete_item(Key={"ip_address": ip})
        rate_limit_table.update_item(
            Key={"ip_address": RESET_TRACKER_KEY},
            UpdateExpression="SET last_reset_time = :time",
            ExpressionAttributeValues={":time": current_time}
        )
        print("Daily reset completed successfully.")
    except Exception as e:
        print(f"Error in perform_daily_reset: {str(e)}")

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
        
        print(f"IP: {ip_address}, Credits: {credits}, Last replenish: {last_replenish_time}, Time since: {time_since_last_replenish}s")
        
        # TIME-BASED RULE:
        # If the bucket duration has passed, completely reset the record
        if time_since_last_replenish >= BUCKET_DURATION:
            print(f"Time passed: Completely resetting record for {ip_address} after {time_since_last_replenish}s")
            
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
                    "ttl": ttl_timestamp
                }
            )
            
            # Since we completely reset the record, update our local variables
            credits = RATE_LIMIT
            last_replenish_time = current_time
            
            print(f"Replenishment complete: {ip_address} now has {credits} credits, new timestamp: {last_replenish_time}")
        
        # After all the checks, if credits are 0 or negative, block the request
        if credits <= 0:
            reset_time = last_replenish_time + BUCKET_DURATION
            time_until_reset = max(0, reset_time - current_time)
            
            print(f"Rate limited: {ip_address} has no credits. Reset in {time_until_reset}s at {reset_time}")
            
            return False, {
                "limit": RATE_LIMIT,
                "reset_time": reset_time,
                "ip_address": ip_address
            }
        
        # If we reach here, there are credits available
        return True, None

    except Exception as e:
        print(f"Error in check_rate_limits: {str(e)}")
        # Allow the request if there's an error checking limits
        return True, None

#Create a new record for an IP address.
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
            "credits": RATE_LIMIT - 1,  # Start with one credit already used for this request
            "last_replenish_time": current_time,
            "ttl": ttl_timestamp
        }
    )
    print(f"Created new record for {ip_address} with {RATE_LIMIT - 1} credits and timestamp {current_time}")


def build_rate_limit_response(bucket_info):
    """
    Build a 429 response with rate limit information.
    """
    current_time = int(time.time())
    reset_time = bucket_info["reset_time"]
    reset_time_str = datetime.fromtimestamp(reset_time).strftime("%Y-%m-%d %H:%M:%S UTC")
    seconds_remaining = max(0, reset_time - current_time)
    
    # Fail-safe: If reset time has already passed, reset the record and allow the request
    if current_time > reset_time:
        ip_address = bucket_info.get("ip_address", "unknown")
        if ip_address != "unknown":
            print(f"Failsafe: Reset time ({reset_time}) has passed current time ({current_time}). Resetting record.")
            
            # This is a sanity check - if the time has passed, 
            # completely reset the record and allow the request
            midnight = (datetime.now(timezone.utc) + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            ttl_timestamp = int(midnight.timestamp())
            
            # Completely replace the record
            rate_limit_table.put_item(
                Item={
                    "ip_address": ip_address,
                    "credits": RATE_LIMIT,
                    "last_replenish_time": current_time,
                    "ttl": ttl_timestamp
                }
            )
            print(f"Record reset for {ip_address} - allowing request")
            return None  # Return None to signal that the request should be allowed
    
    # Normal case: return 429 response
    return {
        "statusCode": 429,
        "headers": {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Allow-Methods": "ANY,OPTIONS,POST,GET",
            "Content-Type": "application/json",
        },
        "body": json.dumps({
            "error": "Too Many Requests",
            "message": f"Rate limit exceeded. Limit is {bucket_info['limit']} requests per {BUCKET_DURATION} seconds.",
            "reset_at": reset_time_str,
            "retry_after_seconds": seconds_remaining
        }),
    }

# Main rate-limit handler
def rate_limit(event, context):
    """
    1. Check for daily reset
    2. Check rate limits - if time has passed, completely reset the record
    3. If allowed, subtract one token; otherwise, return a 429 response
    """
    # Check for daily database reset first
    check_daily_reset()
    
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
            ReturnValues="UPDATED_NEW"
        )
        
        if "Attributes" in response:
            new_credits = int(response["Attributes"].get("credits", 0))
            print(f"Credit used: {ip_address} now has {new_credits} credits remaining")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            # This means credits would go negative - return 429 response
            print(f"Condition check failed for {ip_address} - no credits available")
            
            # Get the current record to build the rate limit response
            item = rate_limit_table.get_item(Key={"ip_address": ip_address}).get("Item", {})
            last_replenish_time = int(item.get("last_replenish_time", 0))
            reset_time = last_replenish_time + BUCKET_DURATION
            
            bucket_info = {"limit": RATE_LIMIT, "reset_time": reset_time, "ip_address": ip_address}
            return build_rate_limit_response(bucket_info)
        else:
            print(f"Error in update_rate_limits: {str(e)}")
    
    # 4. If we reach here, the request is allowed
    return


# Expected event structure for /balances:
# {
#   "body": {
#     "network": "string", // Required: EVM network name (e.g., "eth-mainnet")
#     "userAddress": "string", // Required: EVM wallet address
#     "contractAddresses": "string" // Optional: Comma-separated list of token contract addresses
#   }
# }
# Response structure:
# [
#   {
#     "contractAddress": "string",
#     "tokenBalance": "string" // Hex string
#   }
# ]
# https://docs.alchemy.com/reference/alchemy-gettokenbalances
def handle_balances(event):
    try:
        body = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        return build_response(400, {"error": "Invalid JSON body"})

    network = body.get("network")
    user_address = body.get("userAddress")
    contract_addresses = body.get("contractAddresses")

    if not network or not user_address:
        return build_response(
            400, {"error": "Missing required parameters: network and userAddress"}
        )

    try:
        params = [user_address]
        if contract_addresses:
            if "," in contract_addresses:
                params.append(contract_addresses.split(","))
            else:
                params.append([contract_addresses])

        alchemy_response = call_alchemy(network, "alchemy_getTokenBalances", params)

        if "result" not in alchemy_response:
            return build_response(
                500, {"error": "Failed to retrieve data from Alchemy API"}
            )

        token_balances = alchemy_response["result"]["tokenBalances"]
        formatted_balances = []

        for balance in token_balances:
            token_info = {
                "contractAddress": balance["contractAddress"],
                "tokenBalance": balance["tokenBalance"],
            }
            formatted_balances.append(token_info)

        return build_response(200, formatted_balances)

    except Exception as e:
        return build_response(500, {"error": f"An error occurred: {str(e)}"})


# Expected event structure for /allowance:
# {
#   "body": {
#     "network": "string", // Required: EVM network name
#     "userAddress": "string", // Required: Owner's EVM wallet address
#     "contractAddress": "string", // Required: Token contract address
#     "spenderAddress": "string" // Required: Address of the spender
#   }
# }
# Response structure:
# {
#   "allowance": "string" // Hex string representing token allowance
# }
# https://docs.alchemy.com/reference/alchemy-gettokenallowance
def handle_allowance(event):
    try:
        body = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        return build_response(400, {"error": "Invalid JSON body"})

    network = body.get("network")
    user_address = body.get("userAddress")
    contract_address = body.get("contractAddress")
    spender_address = body.get("spenderAddress")

    if not network or not user_address or not contract_address or not spender_address:
        return build_response(
            400,
            {
                "error": "Missing required parameters: network, userAddress, contractAddress, spenderAddress"
            },
        )

    try:
        params = [
            {
                "owner": user_address,
                "contract": contract_address,
                "spender": spender_address,
            }
        ]

        alchemy_response = call_alchemy(network, "alchemy_getTokenAllowance", params)

        if "result" not in alchemy_response:
            return build_response(
                500, {"error": "Failed to retrieve data from Alchemy API"}
            )

        allowance = alchemy_response["result"]
        return build_response(200, {"allowance": allowance})

    except Exception as e:
        return build_response(500, {"error": f"An error occurred: {str(e)}"})


# Expected event structure for /metadata:
# {
#   "body": {
#     "network": "string", // Required: EVM network name
#     "contractAddress": "string" // Required: Token contract address
#   }
# }
# Response structure:
# {
#   "name": "string",
#   "symbol": "string",
#   "decimals": number,
#   "logo": "string", // URL to token logo
#   "totalSupply": "string" // Optional, hex string
# }
# https://docs.alchemy.com/reference/alchemy-gettokenmetadata
def handle_metadata(event):
    try:
        body = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        return build_response(400, {"error": "Invalid JSON body"})

    network = body.get("network")
    contract_address = body.get("contractAddress")

    if not network or not contract_address:
        return build_response(
            400, {"error": "Missing required parameters: network and contractAddress"}
        )

    try:
        params = [contract_address]

        alchemy_response = call_alchemy(network, "alchemy_getTokenMetadata", params)

        if "result" not in alchemy_response:
            return build_response(
                500, {"error": "Failed to retrieve token metadata from Alchemy API"}
            )

        return build_response(200, alchemy_response["result"])

    except Exception as e:
        return build_response(500, {"error": f"An error occurred: {str(e)}"})


# Expected event structure for /prices:
# {
#   "body": {
#     "addresses": [
#       {
#         "network": "string", // Required: EVM network name (e.g., "eth-mainnet")
#         "address": "string" // Required: Token contract address
#       }
#     ]
#   }
# }
# Response structure:
# {
#   "data": [
#     {
#       "network": "string",
#       "address": "string",
#       "prices": [
#         {
#           "currency": "string",
#           "value": "string",
#           "lastUpdatedAt": "string"
#         }
#       ],
#       "error": string | null
#     }
#   ]
# }
# https://docs.alchemy.com/reference/get-token-prices-by-address
def handle_prices(event):
    try:
        body = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        return build_response(400, {"error": "Invalid JSON body"})

    addresses = body.get("addresses", [])

    if not addresses or not isinstance(addresses, list) or len(addresses) == 0:
        return build_response(
            400, {"error": "Missing required parameter: addresses array"}
        )

    if len(addresses) > 25:
        return build_response(400, {"error": "Too many addresses: maximum 25 allowed"})

    # Validate each address entry
    for i, entry in enumerate(addresses):
        if not isinstance(entry, dict):
            return build_response(
                400, {"error": f"Invalid address entry at index {i}: must be an object"}
            )
        if "network" not in entry:
            return build_response(
                400, {"error": f"Missing network in address entry at index {i}"}
            )
        if "address" not in entry:
            return build_response(
                400, {"error": f"Missing address in address entry at index {i}"}
            )

    try:
        api_key = os.environ.get("ALCHEMY_API_KEY")
        url = f"https://api.g.alchemy.com/prices/v1/{api_key}/tokens/by-address"

        response = requests.post(
            url,
            headers={"Content-Type": "application/json"},
            json={"addresses": addresses},
            timeout=10,
        )

        if response.status_code != 200:
            return build_response(
                response.status_code,
                {"error": f"Failed to retrieve data from Alchemy API: {response.text}"},
            )

        alchemy_response = response.json()
        return build_response(200, alchemy_response)

    except Exception as e:
        return build_response(500, {"error": f"An error occurred: {str(e)}"})


# Expected parameters:
# - network: String, e.g., "eth-mainnet", "polygon-mainnet"
# - method: String, Alchemy API method name
# - params: Array, parameters for the Alchemy API call
# Response structure:
# {
#   "jsonrpc": "2.0",
#   "id": 1,
#   "result": {...} // Varies based on the method called
# }
def call_alchemy(network, method, params):
    api_key = os.environ.get("ALCHEMY_API_KEY")
    url = f"https://{network}.g.alchemy.com/v2/{api_key}"

    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}

    response = requests.post(
        url, headers={"Content-Type": "application/json"}, json=payload, timeout=10
    )

    return response.json()


# Expected parameters:
# - status_code: Integer HTTP status code
# - body: Dictionary/object to be serialized to JSON
# Response structure:
# {
#   "statusCode": number,
#   "headers": {...},
#   "body": "string" // JSON string
# }
def build_response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "**",
            "Access-Control-Allow-Methods": "ANY,OPTIONS,POST,GET",
            "Content-Type": "application/json",
        },
        "body": json.dumps(body).encode("utf-8"),
        "isBase64Encoded": True 
    }

# Expected event structure:
# {
#   "path": "/test" | "/balances" | "/allowance" | "/metadata" | "/prices",
#   "httpMethod": "GET" | "POST" | "ANY" | "PUT",
#   "body": "JSON string"
# }
def lambda_handler(event, context):
    print("Event:", json.dumps(event))

    res = rate_limit(event, context)
    if res:
        return res
    
    path = event.get("path", "")

    if not path and "requestContext" in event and "resourcePath" in event["requestContext"]:
        path = event["requestContext"]["resourcePath"]

    if path == "/test" or path.endswith("/test"):
        if event["httpMethod"] == "GET":
            response_data = {"message": "Hello from altverse /test"}
            return build_response(200, response_data)

    elif path == "/balances" or path.endswith("/balances"):
        if event["httpMethod"] == "POST":
            return handle_balances(event)

    elif path == "/allowance" or path.endswith("/allowance"):
        if event["httpMethod"] == "POST":
            return handle_allowance(event)

    elif path == "/metadata" or path.endswith("/metadata"):
        if event["httpMethod"] == "POST":
            return handle_metadata(event)

    elif path == "/prices" or path.endswith("/prices"):
        if event["httpMethod"] == "POST":
            return handle_prices(event)

    return build_response(404, {"error": "Not found"})