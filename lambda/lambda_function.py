import json
import os
import requests
import boto3
import time
from botocore.exceptions import ClientError
from datetime import datetime, timedelta, timezone
from decimal import Decimal

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

    # Extract client IP address from Lambda event
    # Try to get IP from API Gateway
    if "requestContext" in event and "identity" in event["requestContext"]:
        return event["requestContext"]["identity"].get("sourceIp", "unknown")

    # If using ALB, check headers
    headers = event.get("headers", {})
    if headers and "X-Forwarded-For" in headers:
        # X-Forwarded-For contains a comma-separated list of IPs
        # The left-most IP address is the client
        forwarded_for = headers["X-Forwarded-For"].split(",")
        return forwarded_for[0].strip()

    # Fallback
    return "unknown"


def check_daily_reset():
    
    # Check if we need to perform a daily reset of the rate limit database.
    # This function checks if it's the first request after midnight UTC.
    # Returns True if a reset was performed, False otherwise.
    current_time = int(time.time())
    current_date = datetime.fromtimestamp(current_time, tz=timezone.utc).date()
    
    try:
        # Get the reset tracker record
        response = rate_limit_table.get_item(Key={"ip_address": RESET_TRACKER_KEY})
        
        if "Item" in response:
            # Get the last reset timestamp
            last_reset_time = int(response["Item"].get("last_reset_time", 0))
            last_reset_date = datetime.fromtimestamp(last_reset_time, tz=timezone.utc).date()
            
            # Check if we've passed midnight UTC since the last reset
            if current_date > last_reset_date:
                # It's a new day - perform the reset
                perform_daily_reset(current_time)
                return True
        else:
            #Create the tracker and don't reset
            rate_limit_table.put_item(
                Item={
                    "ip_address": RESET_TRACKER_KEY,
                    "last_reset_time": current_time
                }
            )
    except Exception as e:
        print(f"Error checking daily reset: {str(e)}")
    
    return False


def perform_daily_reset(current_time):

    # Reset the entire rate limit database by deleting all items except the tracker,
    # then update the reset tracker with the current time.
    try:
        print("Performing daily reset of rate limit database")
        
        # Scan to get all IP addresses
        response = rate_limit_table.scan(
            ProjectionExpression="ip_address"
        )
        
        # Delete all items except the reset tracker
        with rate_limit_table.batch_writer() as batch:
            for item in response.get("Items", []):
                ip = item.get("ip_address")
                if ip != RESET_TRACKER_KEY:
                    batch.delete_item(Key={"ip_address": ip})
        
        # Update the last reset time
        rate_limit_table.update_item(
            Key={"ip_address": RESET_TRACKER_KEY},
            UpdateExpression="SET last_reset_time = :time",
            ExpressionAttributeValues={
                ":time": current_time
            }
        )
        
        print("Daily reset completed successfully")
    except Exception as e:
        print(f"Error performing daily reset: {str(e)}")


# Check if the IP address has exceeded rate limits
def check_rate_limits(ip_address):
    
    # Returns (is_allowed, bucket_info):
        # is_allowed: boolean indicating if the request should be allowed
        # bucket_info: dict with information about rate limit (if exceeded)
    current_time = int(time.time())

    try:
        # Get current counts for this IP
        response = rate_limit_table.get_item(Key={"ip_address": ip_address})

        if "Item" not in response:
            # Store the IP with full credits
            update_new_ip(ip_address, current_time)
            return True, None

        item = response["Item"]
        
        # Get remaining credits and first query timestamp
        remaining_credits = int(item.get("credits", 0))
        first_query_time = int(item.get("first_query_time", 0))
        
        # Check if 5 minutes have passed since first query
        if current_time - first_query_time >= BUCKET_DURATION:
            # 5 minutes have passed, replenish credits
            replenish_credits(ip_address, current_time)
            return True, None
            
        # Check if credits are exhausted
        if remaining_credits <= 0:
            # Calculate when credits will be replenished
            reset_time = first_query_time + BUCKET_DURATION
            return False, {
                "limit": RATE_LIMIT,
                "reset_time": reset_time,
            }
            
        # Credits available, allow request
        return True, None

    except Exception as e:
        # Log the error but allow the request to proceed to avoid blocking legitimate users
        print(f"Error checking rate limits: {str(e)}")
        return True, None
    

# Create a new entry for an IP address with full credits
def update_new_ip(ip_address, current_time):
    
    try:
        # Set TTL to expire at midnight (in UTC+0)
        midnight = (datetime.now(timezone.utc) + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        ttl_timestamp = int(midnight.timestamp())
        
        # Create new entry with full credits
        rate_limit_table.put_item(
            Item={
                "ip_address": ip_address,
                "credits": RATE_LIMIT - 1,  # Subtract 1 for this request
                "first_query_time": current_time,
                "ttl": ttl_timestamp
            }
        )
    except Exception as e:
        print(f"Error creating new IP entry: {str(e)}")


def replenish_credits(ip_address, current_time):
    
    # Replenish credits for an IP address and update first query time
    try:
        # Set TTL to expire at midnight (in UTC+0)
        midnight = (datetime.now(timezone.utc) + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        ttl_timestamp = int(midnight.timestamp())
        
        # Update with replenished credits and new first query time
        rate_limit_table.update_item(
            Key={"ip_address": ip_address},
            UpdateExpression="SET credits = :credits, first_query_time = :time, ttl = :ttl",
            ExpressionAttributeValues={
                ":credits": RATE_LIMIT - 1,  # Subtract 1 for this request
                ":time": current_time,
                ":ttl": ttl_timestamp
            }
        )
    except Exception as e:
        print(f"Error replenishing credits: {str(e)}")


def update_rate_limits(ip_address):

    # Decrement the credits for the given IP address atomically.
    # Returns a 429 response dict if the condition fails (i.e. no credits left),
    try:
        # Decrement credits by 1 only if at least 1 credit is available
        rate_limit_table.update_item(
            Key={"ip_address": ip_address},
            UpdateExpression="SET credits = credits - :one",
            ConditionExpression="credits >= :one",
            ExpressionAttributeValues={":one": 1},
            ReturnValues="UPDATED_NEW"
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            # Credits have already been exhausted; get the first query time to calculate reset
            item = rate_limit_table.get_item(Key={"ip_address": ip_address}).get("Item", {})
            first_query_time = int(item.get("first_query_time", 0))
            reset_time = first_query_time + BUCKET_DURATION
            bucket_info = {"limit": RATE_LIMIT, "reset_time": reset_time}
            return build_rate_limit_response(bucket_info)
        else:
            print(f"Error updating rate limits: {str(e)}")
    return None


def build_rate_limit_response(bucket_info):
    
    # Build a 429 response with rate limit information
    reset_time = datetime.fromtimestamp(bucket_info["reset_time"]).strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )
    
    seconds_remaining = bucket_info["reset_time"] - int(time.time())
    # Return 429 if rate limited
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
            "message": f"Rate limit exceeded. Limit is {bucket_info['limit']} requests per 5 minutes.",
            "reset_at": reset_time,
            "retry_after_seconds": max(0, seconds_remaining)
        }),
    }


def rate_limit(event, context):

    # Perform a daily reset if needed
    check_daily_reset()
    
    # Extract client IP
    ip_address = get_client_ip(event)
    print("Extracted IP:", ip_address)

    # Skip rate limiting for unknown IPs
    if ip_address == "unknown":
        return

    # Check if IP is within rate limits
    is_allowed, bucket_info = check_rate_limits(ip_address)
    if not is_allowed:
        return build_rate_limit_response(bucket_info)

    # For existing IPs with available credits, attempt to decrement the credits atomically.
    if bucket_info is None:
        result = update_rate_limits(ip_address)
        if result is not None:
            # If update_rate_limits returned a response, then credits were exhausted.
            return result

    # If we reach here, rate limiting passed; the API call can proceed.
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
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Allow-Methods": "ANY,OPTIONS,POST,GET",
            "Content-Type": "application/json",
        },
        "body": json.dumps(body),
    }

# Expected event structure:
# {
#   "path": "/test" | "/balances" | "/allowance" | "/metadata" | "/prices",
#   "httpMethod": "GET" | "POST" | "ANY" | "PUT",
#   "body": "JSON string"
# }
def lambda_handler(event, context):
    res = rate_limit(event, context)
    if res:
        return res

    # Rest of your API handling code
    if event["path"] == "/test":
        if event["httpMethod"] == "GET":
            response_data = {"message": "Hello from altverse /test"}
            return build_response(200, response_data)

    elif event["path"] == "/balances":
        if event["httpMethod"] == "GET":
            return handle_balances(event)

    elif event["path"] == "/allowance":
        if event["httpMethod"] == "GET":
            return handle_allowance(event)

    elif event["path"] == "/metadata":
        if event["httpMethod"] == "GET":
            return handle_metadata(event)

    elif event["path"] == "/prices":
        if event["httpMethod"] == "GET":
            return handle_prices(event)

    return build_response(404, {"error": "Not found"})

