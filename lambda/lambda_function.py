import json
import os
import requests
import boto3
import time
from decimal import Decimal
from botocore.exceptions import ClientError
from datetime import datetime, timedelta, timezone

# Configure the DynamoDB client
dynamodb = boto3.resource("dynamodb")
rate_limit_table = dynamodb.Table(
    os.environ.get("RATE_LIMIT_TABLE_NAME", "api_rate_limits")
)
metrics_table = dynamodb.Table(os.environ.get("METRICS_TABLE_NAME", "metrics"))

# Rate limit configuration
RATE_LIMIT = 5000  # Number of requests allowed in 5 minutes
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
            last_reset_date = datetime.fromtimestamp(
                last_reset_time, tz=timezone.utc
            ).date()
            if current_date > last_reset_date:
                perform_daily_reset(current_time)
                return True
        else:
            # If no tracker exists, create one.
            rate_limit_table.put_item(
                Item={"ip_address": RESET_TRACKER_KEY, "last_reset_time": current_time}
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
            ExpressionAttributeValues={":time": current_time},
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

    # Fail-safe: If reset time has already passed, reset the record and allow the request
    if current_time > reset_time:
        ip_address = bucket_info.get("ip_address", "unknown")
        if ip_address != "unknown":
            print(
                f"Failsafe: Reset time ({reset_time}) has passed current time ({current_time}). Resetting record."
            )

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
                    "ttl": ttl_timestamp,
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


# Expected event structure for /balances:
# {
#   "body": {
#     "network": "string", // Required: alchemy network name (e.g., "eth-mainnet")
#     "userAddress": "string", // Required: wallet address
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
        formatted_balances = []

        # Get native token balance
        native_params = [user_address, "latest"]
        native_response = call_alchemy(network, "eth_getBalance", native_params)

        if "result" in native_response:
            native_balance = native_response["result"]

            # Pad the native balance to match ERC20 token format (32 bytes)
            # First, remove '0x' prefix, then pad to 64 characters (32 bytes), then add '0x' back
            if native_balance.startswith("0x"):
                padded_balance = "0x" + native_balance[2:].zfill(64)
            else:
                padded_balance = "0x" + native_balance.zfill(64)

            native_token_info = {
                "contractAddress": (
                    "0x0000000000000000000000000000000000000000"
                    if network != "polygon-mainnet"
                    else "0x0000000000000000000000000000000000001010"
                ),
                "tokenBalance": padded_balance,
            }
            formatted_balances.append(native_token_info)
        else:
            print(f"Failed to retrieve native token balance: {native_response}")

        # Get ERC20 token balances
        params = [user_address]
        if contract_addresses:
            if "," in contract_addresses:
                params.append(contract_addresses.split(","))
            else:
                params.append([contract_addresses])

        alchemy_response = call_alchemy(network, "alchemy_getTokenBalances", params)

        if "result" not in alchemy_response:
            # If we have at least the native token balance, return that
            if formatted_balances:
                return build_response(200, formatted_balances)
            return build_response(
                500, {"error": "Failed to retrieve data from Alchemy API"}
            )

        token_balances = alchemy_response["result"]["tokenBalances"]

        for balance in token_balances:
            # Skip tokens with zero balance if they're in the "0x" format
            if balance["tokenBalance"] == "0x0":
                continue

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


# Expected event structure for /spl-balances:
# {
#   "body": {
#     "network": "string", // Required: Solana network name (e.g., "solana-mainnet")
#     "userAddress": "string", // Required: Solana wallet address
#     "programId": "string", // Optional: The SPL token program ID to filter by
#     "mint": "string" // Optional: The SPL token mint address to filter by
#   }
# }
# Response structure:
# [
#   {
#     "pubkey": "string", // The token account address
#     "mint": "string", // The token mint address
#     "owner": "string", // The token account owner address
#     "amount": "string", // Token amount
#     "decimals": number, // Token decimals
#     "uiAmount": number, // Token amount with decimals applied
#     "uiAmountString": "string" // Token amount as a string with decimals applied
#   }
# ]
# https://docs.alchemy.com/reference/solana-getTokenAccountsByOwner
def handle_spl_balances(event):
    try:
        body = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        return build_response(400, {"error": "Invalid JSON body"})

    network = body.get("network")
    user_address = body.get("userAddress")
    program_id = body.get("programId")
    mint = body.get("mint")

    if not network or not user_address:
        return build_response(
            400, {"error": "Missing required parameters: network and userAddress"}
        )

    try:
        # Get native SOL balance first with getAccountInfo
        native_params = [user_address, {"encoding": "jsonParsed"}]
        native_response = call_alchemy(network, "getAccountInfo", native_params)

        formatted_balances = []

        # Process native SOL balance
        if "result" in native_response and native_response["result"]["value"]:
            account_info = native_response["result"]["value"]
            native_balance = account_info["lamports"]

            # Format native SOL similar to SPL tokens but mark it as native
            native_token_info = {
                "pubkey": "native",
                "mint": "11111111111111111111111111111111",  # System Program address for native SOL
                "owner": user_address,
                "amount": str(native_balance),
                "decimals": 9,  # SOL has 9 decimals
                "uiAmount": native_balance / 10**9,  # Convert to SOL from lamports
                "uiAmountString": str(native_balance / 10**9),
                "isNative": True,
            }
            formatted_balances.append(native_token_info)
        else:
            print(f"Failed to retrieve native SOL balance: {native_response}")

        # Build filter parameter based on provided parameters
        filter_param = {}
        if mint:
            # If mint is provided, use it for filtering
            filter_param = {"mint": mint}
        elif program_id:
            # Use programId if provided and mint is not
            filter_param = {"programId": program_id}
        else:
            # Default to the SPL Token program ID if neither is specified
            filter_param = {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"}

        # Prepare parameters for the Alchemy API call
        params = [user_address, filter_param, {"encoding": "jsonParsed"}]

        # Call Solana getTokenAccountsByOwner method
        alchemy_response = call_alchemy(network, "getTokenAccountsByOwner", params)

        if "result" not in alchemy_response:
            # If we have at least the native SOL balance, return that
            if formatted_balances:
                return build_response(200, formatted_balances)
            return build_response(
                500, {"error": "Failed to retrieve data from Alchemy API"}
            )

        token_accounts = alchemy_response["result"]["value"]

        # Format the response to match our API structure
        for account in token_accounts:
            try:
                # Extract parsed data
                parsed_data = account["account"]["data"]["parsed"]["info"]
                token_amount = parsed_data["tokenAmount"]

                # Skip accounts with zero balance
                if token_amount["amount"] == "0":
                    continue

                token_info = {
                    "pubkey": account["pubkey"],
                    "mint": parsed_data["mint"],
                    "owner": parsed_data["owner"],
                    "amount": token_amount["amount"],
                    "decimals": token_amount["decimals"],
                    "uiAmount": token_amount["uiAmount"],
                    "uiAmountString": token_amount["uiAmountString"],
                }
                formatted_balances.append(token_info)
            except (KeyError, TypeError) as e:
                # Skip accounts with missing or malformed data
                print(
                    f"Error processing account {account.get('pubkey', 'unknown')}: {str(e)}"
                )
                continue

        return build_response(200, formatted_balances)

    except Exception as e:
        return build_response(500, {"error": f"An error occurred: {str(e)}"})


# Expected event structure for /sui/coin-metadata:
# {
#   "body": {
#     "coinType": "string" // Required: Type name for the coin (e.g., "0x2::sui::SUI")
#   }
# }
# Response structure:
# {
#   "decimals": number, // Number of decimal places the coin uses
#   "name": "string", // Name for the token
#   "symbol": "string", // Symbol for the token
#   "description": "string", // Description of the token
#   "iconUrl": string | null, // URL for the token logo
#   "id": string | null // Object id for the CoinMetadata object
# }
def handle_sui_coin_metadata(event):
    try:
        body = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        return build_response(400, {"error": "Invalid JSON body"})

    coin_type = body.get("coinType")

    if not coin_type:
        return build_response(400, {"error": "Missing required parameter: coinType"})

    try:
        params = [coin_type]
        sui_response = call_sui_api("suix_getCoinMetadata", params)

        if "error" in sui_response:
            return build_response(
                500, {"error": f"Sui API error: {sui_response['error']['message']}"}
            )

        if "result" not in sui_response:
            return build_response(
                500, {"error": "Failed to retrieve coin metadata from Sui API"}
            )

        return build_response(200, sui_response["result"])

    except Exception as e:
        return build_response(500, {"error": f"An error occurred: {str(e)}"})


# Expected event structure for /sui/balance:
# {
#   "body": {
#     "owner": "string", // Required: The owner's Sui address
#     "coinType": "string" // Optional: Type name for the coin (default to "0x2::sui::SUI")
#   }
# }
# Response structure:
# {
#   "coinType": "string", // Type name for the coin
#   "coinObjectCount": number, // Number of coin objects of this type
#   "totalBalance": "string", // Total balance as a string
#   "lockedBalance": object // Information about locked balance
# }
def handle_sui_balance(event):
    try:
        body = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        return build_response(400, {"error": "Invalid JSON body"})

    owner = body.get("owner")
    coin_type = body.get("coinType")  # Optional

    if not owner:
        return build_response(400, {"error": "Missing required parameter: owner"})

    try:
        params = [owner]
        if coin_type:
            params.append(coin_type)

        sui_response = call_sui_api("suix_getBalance", params)

        if "error" in sui_response:
            return build_response(
                500, {"error": f"Sui API error: {sui_response['error']['message']}"}
            )

        if "result" not in sui_response:
            return build_response(
                500, {"error": "Failed to retrieve balance from Sui API"}
            )

        return build_response(200, sui_response["result"])

    except Exception as e:
        return build_response(500, {"error": f"An error occurred: {str(e)}"})


# Expected event structure for /sui/all-coins:
# {
#   "body": {
#     "owner": "string", // Required: The owner's Sui address
#     "cursor": "string", // Optional: Paging cursor
#     "limit": number // Optional: Maximum number of items per page
#   }
# }
# Response structure:
# {
#   "data": [ // Array of coin objects
#     {
#       "coinType": "string", // Type name for the coin
#       "coinObjectId": "string", // Object ID of the coin
#       "version": "string", // Object version
#       "digest": "string", // Object digest
#       "balance": "string", // Coin balance
#       "previousTransaction": "string" // Previous transaction digest
#     }
#   ],
#   "nextCursor": string | null, // Cursor for pagination, or null if no more pages
#   "hasNextPage": boolean // Whether there are more pages to fetch
# }
def handle_sui_all_coins(event):
    try:
        body = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        return build_response(400, {"error": "Invalid JSON body"})

    owner = body.get("owner")
    cursor = body.get("cursor")  # Optional
    limit = body.get("limit")  # Optional

    if not owner:
        return build_response(400, {"error": "Missing required parameter: owner"})

    try:
        params = [owner]
        if cursor:
            params.append(cursor)
            if limit:
                params.append(limit)
        elif limit:
            params.append(None)  # Add empty cursor if only limit is provided
            params.append(limit)

        sui_response = call_sui_api("suix_getAllCoins", params)

        if "error" in sui_response:
            return build_response(
                500, {"error": f"Sui API error: {sui_response['error']['message']}"}
            )

        if "result" not in sui_response:
            return build_response(
                500, {"error": "Failed to retrieve all coins from Sui API"}
            )

        return build_response(200, sui_response["result"])

    except Exception as e:
        return build_response(500, {"error": f"An error occurred: {str(e)}"})


# Expected event structure for /sui/all-balances:
# {
#   "body": {
#     "owner": "string" // Required: The owner's Sui address
#   }
# }
# Response structure:
# [
#   {
#     "coinType": "string", // Type name for the coin
#     "coinObjectCount": number, // Number of coin objects of this type
#     "totalBalance": "string", // Total balance as a string
#     "lockedBalance": object // Information about locked balance
#   }
# ]
def handle_sui_all_balances(event):
    try:
        body = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        return build_response(400, {"error": "Invalid JSON body"})

    owner = body.get("owner")

    if not owner:
        return build_response(400, {"error": "Missing required parameter: owner"})

    try:
        params = [owner]
        sui_response = call_sui_api("suix_getAllBalances", params)

        if "error" in sui_response:
            return build_response(
                500, {"error": f"Sui API error: {sui_response['error']['message']}"}
            )

        if "result" not in sui_response:
            return build_response(
                500, {"error": "Failed to retrieve all balances from Sui API"}
            )

        return build_response(200, sui_response["result"])

    except Exception as e:
        return build_response(500, {"error": f"An error occurred: {str(e)}"})


# Expected event structure for /usage:
# Query parameters:
# {
#   "view": "all" | "daily" | "protocol", // Type of view (default: "all")
#   "protocol": "entrance" | "swap" | "lending" | "earn", // Filter by protocol/section
#   "userAddress": "string", // Filter by user address
#   "action": "string", // Filter by action (e.g., "deposit", "withdraw", "supply", etc.)
#   "startDate": "YYYY-MM-DD", // Start date filter
#   "endDate": "YYYY-MM-DD", // End date filter
#   "summary": "true" | "false", // Return summary or detailed data (default: "false")
#   "limit": number, // Limit number of results (for pagination)
#   "lastKey": "string" // Last evaluated key for pagination
# }
def handle_usage(event):
    """
    Query metrics from the DynamoDB table with various filters and views.
    """
    try:
        # Parse query parameters
        query_params = event.get("queryStringParameters") or {}

        view = query_params.get("view", "all")
        protocol = query_params.get("protocol")
        user_address = query_params.get("userAddress")
        action = query_params.get("action")
        start_date = query_params.get("startDate")
        end_date = query_params.get("endDate")
        summary = query_params.get("summary", "false").lower() == "true"
        limit = int(query_params.get("limit", "100"))
        last_key_str = query_params.get("lastKey")

        # Parse lastKey if provided
        last_key = None
        if last_key_str:
            try:
                last_key = json.loads(last_key_str)
            except:
                pass

        response_data = {"view": view, "filters": {}, "data": [], "summary": {}}

        # Add active filters to response
        if protocol:
            response_data["filters"]["protocol"] = protocol
        if user_address:
            response_data["filters"]["userAddress"] = user_address
        if action:
            response_data["filters"]["action"] = action
        if start_date:
            response_data["filters"]["startDate"] = start_date
        if end_date:
            response_data["filters"]["endDate"] = end_date

        # Build query based on view type
        if user_address:
            # User-specific queries
            response_data = query_user_metrics(
                user_address,
                protocol,
                action,
                start_date,
                end_date,
                summary,
                limit,
                last_key,
            )
        elif view == "daily":
            # Daily aggregated metrics
            response_data = query_daily_metrics(
                protocol, start_date, end_date, summary, limit, last_key
            )
        elif view == "protocol":
            # Protocol-specific metrics
            if not protocol:
                return build_response(
                    400, {"error": "Protocol parameter is required for protocol view"}
                )
            response_data = query_protocol_metrics(
                protocol, action, start_date, end_date, summary, limit, last_key
            )
        else:
            # Default: all metrics view
            response_data = query_all_metrics(
                protocol, start_date, end_date, summary, limit, last_key
            )

        return build_response(200, response_data)

    except Exception as e:
        print(f"Error handling usage request: {str(e)}")
        return build_response(500, {"error": f"Failed to retrieve metrics: {str(e)}"})


def query_user_metrics(
    user_address, protocol, action, start_date, end_date, summary, limit, last_key
):
    """
    Query metrics for a specific user.
    """
    response_data = {
        "view": "user",
        "userAddress": user_address,
        "data": [],
        "summary": {},
    }

    try:
        # Build the query
        query_params = {
            "KeyConditionExpression": "pk = :pk",
            "ExpressionAttributeValues": {":pk": f"USER#{user_address}"},
            "Limit": limit,
        }

        # Add SK range if dates provided
        sk_conditions = []
        if start_date or end_date:
            if start_date and end_date:
                # Convert dates to timestamps for range query
                start_ts = int(datetime.strptime(start_date, "%Y-%m-%d").timestamp())
                end_ts = (
                    int(datetime.strptime(end_date, "%Y-%m-%d").timestamp()) + 86399
                )
                query_params[
                    "KeyConditionExpression"
                ] += " AND sk BETWEEN :start AND :end"
                query_params["ExpressionAttributeValues"][":start"] = f"#{start_ts}"
                query_params["ExpressionAttributeValues"][":end"] = f"#{end_ts}"
            elif start_date:
                start_ts = int(datetime.strptime(start_date, "%Y-%m-%d").timestamp())
                query_params["KeyConditionExpression"] += " AND sk >= :start"
                query_params["ExpressionAttributeValues"][":start"] = f"#{start_ts}"
            elif end_date:
                end_ts = (
                    int(datetime.strptime(end_date, "%Y-%m-%d").timestamp()) + 86399
                )
                query_params["KeyConditionExpression"] += " AND sk <= :end"
                query_params["ExpressionAttributeValues"][":end"] = f"#{end_ts}"

        # Add filters for protocol and action
        filter_expressions = []
        if protocol:
            if protocol in ["entrance", "swap", "lending", "earn"]:
                filter_expressions.append("metric_type = :protocol")
                query_params["ExpressionAttributeValues"][":protocol"] = protocol

        if action:
            filter_expressions.append("#action = :action")
            query_params["ExpressionAttributeValues"][":action"] = action
            query_params["ExpressionAttributeNames"] = {"#action": "action"}

        if filter_expressions:
            query_params["FilterExpression"] = " AND ".join(filter_expressions)

        if last_key:
            query_params["ExclusiveStartKey"] = last_key

        # Execute query
        result = metrics_table.query(**query_params)

        if summary:
            # Generate summary statistics
            summary_data = {
                "totalActions": 0,
                "byProtocol": {},
                "byAction": {},
                "dateRange": {},
            }

            for item in result.get("Items", []):
                summary_data["totalActions"] += 1

                # Count by protocol/metric type
                metric_type = item.get("metric_type", "unknown")
                summary_data["byProtocol"][metric_type] = (
                    summary_data["byProtocol"].get(metric_type, 0) + 1
                )

                # Count by action if present
                if "action" in item:
                    action_type = item["action"]
                    summary_data["byAction"][action_type] = (
                        summary_data["byAction"].get(action_type, 0) + 1
                    )

                # Track date range
                item_date = item.get("date", "")
                if item_date:
                    if (
                        not summary_data["dateRange"].get("start")
                        or item_date < summary_data["dateRange"]["start"]
                    ):
                        summary_data["dateRange"]["start"] = item_date
                    if (
                        not summary_data["dateRange"].get("end")
                        or item_date > summary_data["dateRange"]["end"]
                    ):
                        summary_data["dateRange"]["end"] = item_date

            response_data["summary"] = summary_data
            response_data["data"] = []  # Don't include raw data in summary mode
        else:
            # Return detailed data
            response_data["data"] = result.get("Items", [])

        # Add pagination info
        if "LastEvaluatedKey" in result:
            response_data["nextKey"] = json.dumps(result["LastEvaluatedKey"])
            response_data["hasMore"] = True
        else:
            response_data["hasMore"] = False

    except Exception as e:
        print(f"Error querying user metrics: {str(e)}")
        raise

    return response_data


def query_daily_metrics(protocol, start_date, end_date, summary, limit, last_key):
    """
    Query daily aggregated metrics.
    """
    response_data = {"view": "daily", "data": [], "summary": {}}

    try:
        # Query daily metrics
        query_params = {
            "KeyConditionExpression": "pk = :pk",
            "ExpressionAttributeValues": {":pk": "GLOBAL"},
            "Limit": limit,
        }

        # Build SK condition for daily data
        sk_prefix = "DAILY#"
        if protocol:
            sk_prefix = f"DAILY#"
            # We'll filter by checking if SK contains the protocol

        if start_date and end_date:
            query_params["KeyConditionExpression"] += " AND sk BETWEEN :start AND :end"
            query_params["ExpressionAttributeValues"][":start"] = f"DAILY#{start_date}"
            query_params["ExpressionAttributeValues"][":end"] = f"DAILY#{end_date}#zzz"
        elif start_date:
            query_params["KeyConditionExpression"] += " AND sk >= :start"
            query_params["ExpressionAttributeValues"][":start"] = f"DAILY#{start_date}"
        elif end_date:
            query_params["KeyConditionExpression"] += " AND sk <= :end"
            query_params["ExpressionAttributeValues"][":end"] = f"DAILY#{end_date}#zzz"
        else:
            query_params["KeyConditionExpression"] += " AND begins_with(sk, :prefix)"
            query_params["ExpressionAttributeValues"][":prefix"] = sk_prefix

        # Add protocol filter if specified
        if protocol:
            query_params["FilterExpression"] = "contains(sk, :protocol)"
            query_params["ExpressionAttributeValues"][":protocol"] = f"#{protocol}"

        if last_key:
            query_params["ExclusiveStartKey"] = last_key

        # Execute query
        result = metrics_table.query(**query_params)

        if summary:
            # Aggregate daily data
            summary_data = {
                "totalDays": set(),
                "totalCount": 0,
                "byDate": {},
                "byProtocol": {},
            }

            for item in result.get("Items", []):
                date = item.get("date", "")
                count = item.get("daily_count", 0)

                if date:
                    summary_data["totalDays"].add(date)
                    summary_data["totalCount"] += count

                    if date not in summary_data["byDate"]:
                        summary_data["byDate"][date] = 0
                    summary_data["byDate"][date] += count

                    # Extract protocol from SK if present
                    sk = item.get("sk", "")
                    for p in ["entrance", "swap", "lending", "earn"]:
                        if f"#{p}" in sk:
                            if p not in summary_data["byProtocol"]:
                                summary_data["byProtocol"][p] = 0
                            summary_data["byProtocol"][p] += count
                            break

            summary_data["totalDays"] = len(summary_data["totalDays"])
            response_data["summary"] = summary_data
            response_data["data"] = []
        else:
            # Return detailed daily data
            response_data["data"] = result.get("Items", [])

        # Add pagination info
        if "LastEvaluatedKey" in result:
            response_data["nextKey"] = json.dumps(result["LastEvaluatedKey"])
            response_data["hasMore"] = True
        else:
            response_data["hasMore"] = False

    except Exception as e:
        print(f"Error querying daily metrics: {str(e)}")
        raise

    return response_data


def query_protocol_metrics(
    protocol, action, start_date, end_date, summary, limit, last_key
):
    """
    Query metrics for a specific protocol/section.
    """
    response_data = {
        "view": "protocol",
        "protocol": protocol,
        "data": [],
        "summary": {},
    }

    try:
        # Query protocol-specific metrics
        pk_prefix = f"TYPE#{protocol}"
        if action:
            pk_prefix = f"TYPE#{protocol}#{action}"

        query_params = {
            "KeyConditionExpression": "begins_with(pk, :pk)",
            "ExpressionAttributeValues": {":pk": pk_prefix},
            "Limit": limit,
        }

        # Add date range filters on SK
        if start_date and end_date:
            query_params["FilterExpression"] = "#date BETWEEN :start AND :end"
            query_params["ExpressionAttributeValues"][":start"] = start_date
            query_params["ExpressionAttributeValues"][":end"] = end_date
            query_params["ExpressionAttributeNames"] = {"#date": "date"}
        elif start_date:
            query_params["FilterExpression"] = "#date >= :start"
            query_params["ExpressionAttributeValues"][":start"] = start_date
            query_params["ExpressionAttributeNames"] = {"#date": "date"}
        elif end_date:
            query_params["FilterExpression"] = "#date <= :end"
            query_params["ExpressionAttributeValues"][":end"] = end_date
            query_params["ExpressionAttributeNames"] = {"#date": "date"}

        if last_key:
            query_params["ExclusiveStartKey"] = last_key

        # Use scan since we're using begins_with on pk
        result = metrics_table.scan(**query_params)

        if summary:
            # Generate protocol-specific summary
            summary_data = {
                "protocol": protocol,
                "totalCount": 0,
                "byAction": {},
                "byDate": {},
                "dateRange": {},
            }

            for item in result.get("Items", []):
                count = item.get("type_count", 0)
                action_type = item.get("action", "")
                date = item.get("date", "")

                summary_data["totalCount"] += count

                if action_type:
                    if action_type not in summary_data["byAction"]:
                        summary_data["byAction"][action_type] = 0
                    summary_data["byAction"][action_type] += count

                if date:
                    if date not in summary_data["byDate"]:
                        summary_data["byDate"][date] = 0
                    summary_data["byDate"][date] += count

                    # Track date range
                    if (
                        not summary_data["dateRange"].get("start")
                        or date < summary_data["dateRange"]["start"]
                    ):
                        summary_data["dateRange"]["start"] = date
                    if (
                        not summary_data["dateRange"].get("end")
                        or date > summary_data["dateRange"]["end"]
                    ):
                        summary_data["dateRange"]["end"] = date

            response_data["summary"] = summary_data
            response_data["data"] = []
        else:
            # Return detailed data
            response_data["data"] = result.get("Items", [])

        # Add pagination info
        if "LastEvaluatedKey" in result:
            response_data["nextKey"] = json.dumps(result["LastEvaluatedKey"])
            response_data["hasMore"] = True
        else:
            response_data["hasMore"] = False

    except Exception as e:
        print(f"Error querying protocol metrics: {str(e)}")
        raise

    return response_data


def query_all_metrics(protocol, start_date, end_date, summary, limit, last_key):
    """
    Query all metrics with optional filters.
    """
    response_data = {"view": "all", "data": [], "summary": {}}

    try:
        # Query global counts
        global_counts = {}

        # Get global entrance count
        entrance_result = metrics_table.get_item(
            Key={"pk": "GLOBAL", "sk": "COUNT#entrance"}
        )
        if "Item" in entrance_result:
            global_counts["entrance"] = entrance_result["Item"].get("entrance_count", 0)

        # Get global swap count
        swap_result = metrics_table.get_item(Key={"pk": "GLOBAL", "sk": "COUNT#swap"})
        if "Item" in swap_result:
            global_counts["swap"] = swap_result["Item"].get("swap_count", 0)

        # Get global earn count
        earn_result = metrics_table.get_item(Key={"pk": "GLOBAL", "sk": "COUNT#earn"})
        if "Item" in earn_result:
            global_counts["earn"] = earn_result["Item"].get("earn_count", 0)

        # Get global lending count
        lending_result = metrics_table.get_item(
            Key={"pk": "GLOBAL", "sk": "COUNT#lending"}
        )
        if "Item" in lending_result:
            global_counts["lending"] = lending_result["Item"].get("lending_count", 0)

        if summary:
            # Return summary only
            summary_data = {
                "totalCounts": global_counts,
                "grandTotal": sum(global_counts.values()),
            }

            # If date range specified, get daily totals within range
            if start_date or end_date:
                daily_data = query_daily_metrics(
                    protocol, start_date, end_date, True, 1000, None
                )
                summary_data["dateRangeCounts"] = daily_data.get("summary", {})

            response_data["summary"] = summary_data
            response_data["data"] = []
        else:
            # Return detailed view - query all daily metrics
            scan_params = {"Limit": limit}

            # Add filters
            filter_expressions = []
            expr_values = {}
            expr_names = {}

            if start_date or end_date:
                if start_date and end_date:
                    filter_expressions.append("#date BETWEEN :start AND :end")
                    expr_values[":start"] = start_date
                    expr_values[":end"] = end_date
                elif start_date:
                    filter_expressions.append("#date >= :start")
                    expr_values[":start"] = start_date
                elif end_date:
                    filter_expressions.append("#date <= :end")
                    expr_values[":end"] = end_date
                expr_names["#date"] = "date"

            if protocol:
                filter_expressions.append(
                    "metric_type = :protocol OR contains(sk, :protocol_str)"
                )
                expr_values[":protocol"] = protocol
                expr_values[":protocol_str"] = f"#{protocol}"

            if filter_expressions:
                scan_params["FilterExpression"] = " AND ".join(filter_expressions)
                if expr_values:
                    scan_params["ExpressionAttributeValues"] = expr_values
                if expr_names:
                    scan_params["ExpressionAttributeNames"] = expr_names

            if last_key:
                scan_params["ExclusiveStartKey"] = last_key

            # Execute scan
            result = metrics_table.scan(**scan_params)

            # Combine global counts with detailed data
            response_data["globalCounts"] = global_counts
            response_data["data"] = result.get("Items", [])

            # Add pagination info
            if "LastEvaluatedKey" in result:
                response_data["nextKey"] = json.dumps(result["LastEvaluatedKey"])
                response_data["hasMore"] = True
            else:
                response_data["hasMore"] = False

    except Exception as e:
        print(f"Error querying all metrics: {str(e)}")
        raise

    return response_data


# Expected event structure for /sui/coins:
# {
#   "body": {
#     "owner": "string", // Required: The owner's Sui address
#     "coinType": "string", // Optional: Type name for the coin
#     "cursor": "string", // Optional: Paging cursor
#     "limit": number // Optional: Maximum number of items per page
#   }
# }
# Response structure:
# {
#   "data": [ // Array of coin objects
#     {
#       "coinType": "string", // Type name for the coin
#       "coinObjectId": "string", // Object ID of the coin
#       "version": "string", // Object version
#       "digest": "string", // Object digest
#       "balance": "string", // Coin balance
#       "previousTransaction": "string" // Previous transaction digest
#     }
#   ],
#   "nextCursor": string | null, // Cursor for pagination, or null if no more pages
#   "hasNextPage": boolean // Whether there are more pages to fetch
# }
def handle_sui_coins(event):
    try:
        body = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        return build_response(400, {"error": "Invalid JSON body"})

    owner = body.get("owner")
    coin_type = body.get("coinType")  # Optional
    cursor = body.get("cursor")  # Optional
    limit = body.get("limit")  # Optional

    if not owner:
        return build_response(400, {"error": "Missing required parameter: owner"})

    try:
        params = [owner]

        # Add optional parameters in order
        if coin_type:
            params.append(coin_type)
            if cursor:
                params.append(cursor)
                if limit:
                    params.append(limit)
            elif limit:
                params.append(None)  # Add empty cursor if only limit is provided
                params.append(limit)
        elif cursor:
            params.append(None)  # Add default coinType if not provided
            params.append(cursor)
            if limit:
                params.append(limit)
        elif limit:
            params.append(None)  # Add default coinType if not provided
            params.append(None)  # Add empty cursor if only limit is provided
            params.append(limit)

        sui_response = call_sui_api("suix_getCoins", params)

        if "error" in sui_response:
            return build_response(
                500, {"error": f"Sui API error: {sui_response['error']['message']}"}
            )

        if "result" not in sui_response:
            return build_response(
                500, {"error": "Failed to retrieve coins from Sui API"}
            )

        return build_response(200, sui_response["result"])

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


# Configuration for Sui API
def get_sui_api_url():
    api_key = os.environ.get("BLOCKPI_SUI_RPC_KEY", "")
    return f"https://sui.blockpi.network/v1/rpc/{api_key}"


# Call Sui API with the provided method and parameters
def call_sui_api(method, params):
    url = get_sui_api_url()
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}

    response = requests.post(
        url, headers={"Content-Type": "application/json"}, json=payload, timeout=10
    )

    return response.json()


# Expected event structure for /metrics (entrance):
# {
#   "body": {
#     "metricType": "entrance", // Required: Type of metric
#     "userAddress": "string", // Optional: User address if available
#   }
# }
def handle_entrance_metrics(event):
    try:
        body = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        return build_response(400, {"error": "Invalid JSON body"})

    user_address = body.get("userAddress")

    try:
        current_time = int(time.time())
        current_date = datetime.fromtimestamp(current_time, tz=timezone.utc).strftime(
            "%Y-%m-%d"
        )

        # 1. Update global entrance count
        try:
            metrics_table.update_item(
                Key={"pk": "GLOBAL", "sk": "COUNT#entrance"},
                UpdateExpression="ADD entrance_count :inc",
                ExpressionAttributeValues={":inc": 1},
            )
        except ClientError:
            metrics_table.put_item(
                Item={
                    "pk": "GLOBAL",
                    "sk": "COUNT#entrance",
                    "entrance_count": 1,
                    "created_at": current_time,
                }
            )

        # 2. Update daily entrance count
        try:
            metrics_table.update_item(
                Key={"pk": "GLOBAL", "sk": f"DAILY#{current_date}#entrance"},
                UpdateExpression="ADD daily_count :inc",
                ExpressionAttributeValues={":inc": 1},
            )
        except ClientError:
            metrics_table.put_item(
                Item={
                    "pk": "GLOBAL",
                    "sk": f"DAILY#{current_date}#entrance",
                    "daily_count": 1,
                    "date": current_date,
                    "created_at": current_time,
                }
            )

        # 3. Record user entrance if address provided
        if user_address:
            metrics_table.put_item(
                Item={
                    "pk": f"USER#{user_address}",
                    "sk": f"entrance#{current_time}",
                    "metric_type": "entrance",
                    "user_address": user_address,
                    "timestamp": current_time,
                    "date": current_date,
                }
            )

        return build_response(
            200, {"success": True, "message": "Entrance metrics recorded successfully"}
        )

    except Exception as e:
        print(f"Error recording entrance metrics: {str(e)}")
        return build_response(
            500, {"error": f"Failed to record entrance metrics: {str(e)}"}
        )


# Expected event structure for /metrics (earn):
# {
#   "body": {
#     "metricType": "earn", // Required: Type of metric
#     "protocol": "string", // Required: Protocol name (e.g., "etherFi", "aave", "pendle")
#     "action": "string", // Required: Action type ("deposit", "withdraw")
#     "userAddress": "string", // Required: User address
#     "vaultId": "string", // Optional: Vault ID
#     "asset": "string", // Required: Asset symbol
#     "amount": "string", // Optional: Amount
#     "chain": "string", // Required: Chain name
#     "txHash": "string", // Optional: Transaction hash
#   }
# }
def handle_earn_metrics(event):
    try:
        body = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        return build_response(400, {"error": "Invalid JSON body"})

    protocol = body.get("protocol")
    action = body.get("action")
    user_address = body.get("userAddress")
    vault_id = body.get("vaultId")
    asset = body.get("asset")
    amount = body.get("amount")
    chain = body.get("chain")
    tx_hash = body.get("txHash")

    if not protocol or not action or not user_address or not asset or not chain:
        return build_response(
            400,
            {
                "error": "Missing required parameters: protocol, action, userAddress, asset, chain"
            },
        )

    try:
        current_time = int(time.time())
        current_date = datetime.fromtimestamp(current_time, tz=timezone.utc).strftime(
            "%Y-%m-%d"
        )

        # 1. Update global earn count
        try:
            metrics_table.update_item(
                Key={"pk": "GLOBAL", "sk": "COUNT#earn"},
                UpdateExpression="ADD earn_count :inc",
                ExpressionAttributeValues={":inc": 1},
            )
        except ClientError:
            metrics_table.put_item(
                Item={
                    "pk": "GLOBAL",
                    "sk": "COUNT#earn",
                    "earn_count": 1,
                    "created_at": current_time,
                }
            )

        # 2. Update daily earn count
        try:
            metrics_table.update_item(
                Key={"pk": "GLOBAL", "sk": f"DAILY#{current_date}#earn"},
                UpdateExpression="ADD daily_count :inc",
                ExpressionAttributeValues={":inc": 1},
            )
        except ClientError:
            metrics_table.put_item(
                Item={
                    "pk": "GLOBAL",
                    "sk": f"DAILY#{current_date}#earn",
                    "daily_count": 1,
                    "date": current_date,
                    "created_at": current_time,
                }
            )

        # 3. Update protocol/action counts
        try:
            metrics_table.update_item(
                Key={
                    "pk": f"TYPE#earn#{protocol}#{action}",
                    "sk": f"DAILY#{current_date}",
                },
                UpdateExpression="ADD type_count :inc",
                ExpressionAttributeValues={":inc": 1},
            )
        except ClientError:
            metrics_table.put_item(
                Item={
                    "pk": f"TYPE#earn#{protocol}#{action}",
                    "sk": f"DAILY#{current_date}",
                    "type_count": 1,
                    "protocol": protocol,
                    "action": action,
                    "date": current_date,
                    "created_at": current_time,
                }
            )

        # 4. Record user earn activity
        user_earn_data = {
            "pk": f"USER#{user_address}",
            "sk": f"earn#{current_time}#{tx_hash or 'unknown'}",
            "metric_type": "earn",
            "protocol": protocol,
            "action": action,
            "user_address": user_address,
            "asset": asset,
            "chain": chain,
            "timestamp": current_time,
            "date": current_date,
        }

        if vault_id:
            user_earn_data["vault_id"] = vault_id
        if amount:
            user_earn_data["amount"] = amount
        if tx_hash:
            user_earn_data["tx_hash"] = tx_hash

        metrics_table.put_item(Item=user_earn_data)

        return build_response(
            200, {"success": True, "message": "Earn metrics recorded successfully"}
        )

    except Exception as e:
        print(f"Error recording earn metrics: {str(e)}")
        return build_response(
            500, {"error": f"Failed to record earn metrics: {str(e)}"}
        )


# Expected event structure for /metrics (lending):
# {
#   "body": {
#     "metricType": "lending", // Required: Type of metric
#     "protocol": "string", // Required: Protocol name (e.g., "aave")
#     "action": "string", // Required: Action type ("supply", "borrow", "withdraw", "repay")
#     "userAddress": "string", // Required: User address
#     "marketId": "string", // Optional: Market ID
#     "asset": "string", // Required: Asset symbol
#     "amount": "string", // Required: Amount
#     "chain": "string", // Required: Chain name
#     "txHash": "string", // Optional: Transaction hash
#   }
# }
def handle_lending_metrics(event):
    try:
        body = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        return build_response(400, {"error": "Invalid JSON body"})

    protocol = body.get("protocol")
    action = body.get("action")
    user_address = body.get("userAddress")
    market_id = body.get("marketId")
    asset = body.get("asset")
    amount = body.get("amount")
    chain = body.get("chain")
    tx_hash = body.get("txHash")

    if (
        not protocol
        or not action
        or not user_address
        or not asset
        or not amount
        or not chain
    ):
        return build_response(
            400,
            {
                "error": "Missing required parameters: protocol, action, userAddress, asset, amount, chain"
            },
        )

    try:
        current_time = int(time.time())
        current_date = datetime.fromtimestamp(current_time, tz=timezone.utc).strftime(
            "%Y-%m-%d"
        )

        # 1. Update global lending count
        try:
            metrics_table.update_item(
                Key={"pk": "GLOBAL", "sk": "COUNT#lending"},
                UpdateExpression="ADD lending_count :inc",
                ExpressionAttributeValues={":inc": 1},
            )
        except ClientError:
            metrics_table.put_item(
                Item={
                    "pk": "GLOBAL",
                    "sk": "COUNT#lending",
                    "lending_count": 1,
                    "created_at": current_time,
                }
            )

        # 2. Update daily lending count
        try:
            metrics_table.update_item(
                Key={"pk": "GLOBAL", "sk": f"DAILY#{current_date}#lending"},
                UpdateExpression="ADD daily_count :inc",
                ExpressionAttributeValues={":inc": 1},
            )
        except ClientError:
            metrics_table.put_item(
                Item={
                    "pk": "GLOBAL",
                    "sk": f"DAILY#{current_date}#lending",
                    "daily_count": 1,
                    "date": current_date,
                    "created_at": current_time,
                }
            )

        # 3. Update protocol/action counts
        try:
            metrics_table.update_item(
                Key={
                    "pk": f"TYPE#lending#{protocol}#{action}",
                    "sk": f"DAILY#{current_date}",
                },
                UpdateExpression="ADD type_count :inc",
                ExpressionAttributeValues={":inc": 1},
            )
        except ClientError:
            metrics_table.put_item(
                Item={
                    "pk": f"TYPE#lending#{protocol}#{action}",
                    "sk": f"DAILY#{current_date}",
                    "type_count": 1,
                    "protocol": protocol,
                    "action": action,
                    "date": current_date,
                    "created_at": current_time,
                }
            )

        # 4. Record user lending activity
        user_lending_data = {
            "pk": f"USER#{user_address}",
            "sk": f"lending#{current_time}#{tx_hash or 'unknown'}",
            "metric_type": "lending",
            "protocol": protocol,
            "action": action,
            "user_address": user_address,
            "asset": asset,
            "amount": amount,
            "chain": chain,
            "timestamp": current_time,
            "date": current_date,
        }

        if market_id:
            user_lending_data["market_id"] = market_id
        if tx_hash:
            user_lending_data["tx_hash"] = tx_hash

        metrics_table.put_item(Item=user_lending_data)

        return build_response(
            200, {"success": True, "message": "Lending metrics recorded successfully"}
        )

    except Exception as e:
        print(f"Error recording lending metrics: {str(e)}")
        return build_response(
            500, {"error": f"Failed to record lending metrics: {str(e)}"}
        )


# Expected event structure for /swap-metrics:
# {
#   "body": {
#     "swapperAddress": "string", // Required: Address performing the swap
#     "txHash": "string", // Optional: Transaction hash
#     "swapType": "string", // Optional: Type of swap ("vanilla", "earn/etherFi", "earn/aave", "earn/pendle", "lend/aave")
#     "path": "string", // Optional: Specific swap path
#     "amount": "string", // Optional: Swap amount
#     "tokenIn": "string", // Optional: Input token address
#     "tokenOut": "string", // Optional: Output token address
#     "network": "string" // Optional: Network name
#   }
# }
# Response structure:
# {
#   "success": boolean,
#   "message": "string"
# }
def handle_swap_metrics(event):
    try:
        body = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        return build_response(400, {"error": "Invalid JSON body"})

    swapper_address = body.get("swapperAddress")
    tx_hash = body.get("txHash")
    swap_type = body.get("swapType", "vanilla")
    path = body.get("path")
    amount = body.get("amount")
    token_in = body.get("tokenIn")
    token_out = body.get("tokenOut")
    network = body.get("network")

    if not swapper_address:
        return build_response(
            400, {"error": "Missing required parameter: swapperAddress"}
        )

    try:
        current_time = int(time.time())
        current_date = datetime.fromtimestamp(current_time, tz=timezone.utc).strftime(
            "%Y-%m-%d"
        )

        # 1. Update global swap count
        try:
            metrics_table.update_item(
                Key={"pk": "GLOBAL", "sk": "COUNT#swap"},
                UpdateExpression="ADD swap_count :inc",
                ExpressionAttributeValues={":inc": 1},
            )
        except ClientError:
            # If item doesn't exist, create it
            metrics_table.put_item(
                Item={
                    "pk": "GLOBAL",
                    "sk": "COUNT#swap",
                    "swap_count": 1,
                    "created_at": current_time,
                }
            )

        # 2. Update daily swap count
        try:
            metrics_table.update_item(
                Key={"pk": "GLOBAL", "sk": f"DAILY#{current_date}#swap"},
                UpdateExpression="ADD daily_count :inc",
                ExpressionAttributeValues={":inc": 1},
            )
        except ClientError:
            metrics_table.put_item(
                Item={
                    "pk": "GLOBAL",
                    "sk": f"DAILY#{current_date}#swap",
                    "daily_count": 1,
                    "date": current_date,
                    "created_at": current_time,
                }
            )

        # 3. Update swap type metrics
        if swap_type:
            try:
                metrics_table.update_item(
                    Key={"pk": f"TYPE#swap#{swap_type}", "sk": f"DAILY#{current_date}"},
                    UpdateExpression="ADD type_count :inc",
                    ExpressionAttributeValues={":inc": 1},
                )
            except ClientError:
                metrics_table.put_item(
                    Item={
                        "pk": f"TYPE#swap#{swap_type}",
                        "sk": f"DAILY#{current_date}",
                        "type_count": 1,
                        "swap_type": swap_type,
                        "date": current_date,
                        "created_at": current_time,
                    }
                )

        # 4. Record individual swap if tx_hash provided
        if tx_hash:
            swap_data = {
                "pk": f"SWAP#{tx_hash}",
                "sk": "METADATA",
                "swapper_address": swapper_address,
                "tx_hash": tx_hash,
                "swap_type": swap_type,
                "timestamp": current_time,
                "date": current_date,
            }

            # Add optional fields if provided
            if path:
                swap_data["path"] = path
            if amount:
                swap_data["amount"] = amount
            if token_in:
                swap_data["token_in"] = token_in
            if token_out:
                swap_data["token_out"] = token_out
            if network:
                swap_data["network"] = network

            metrics_table.put_item(Item=swap_data)

        # 5. Record user swap activity
        user_swap_data = {
            "pk": f"USER#{swapper_address}",
            "sk": f"swap#{current_time}#{tx_hash or 'unknown'}",
            "metric_type": "swap",
            "swapper_address": swapper_address,
            "swap_type": swap_type,
            "timestamp": current_time,
            "date": current_date,
        }

        if tx_hash:
            user_swap_data["tx_hash"] = tx_hash
        if path:
            user_swap_data["path"] = path
        if amount:
            user_swap_data["amount"] = amount
        if token_in:
            user_swap_data["token_in"] = token_in
        if token_out:
            user_swap_data["token_out"] = token_out
        if network:
            user_swap_data["network"] = network

        metrics_table.put_item(Item=user_swap_data)

        return build_response(
            200, {"success": True, "message": "Swap metrics recorded successfully"}
        )

    except Exception as e:
        print(f"Error recording swap metrics: {str(e)}")
        return build_response(
            500, {"error": f"Failed to record swap metrics: {str(e)}"}
        )


def decimal_default(obj):
    if isinstance(obj, Decimal):
        # Convert to int if no fractional part, else float
        if obj % 1 == 0:
            return int(obj)
        else:
            return float(obj)
    raise TypeError


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
        "body": json.dumps(body, default=decimal_default).encode("utf-8"),
        "isBase64Encoded": True,
    }


# Expected event structure:
# {
#   "path": "/test" | "/balances" | "/allowance" | "/metadata" | "/prices", ...
#   "httpMethod": "GET" | "POST" | "ANY" | "PUT",
#   "body": "JSON string"
# }
def lambda_handler(event, context):
    print("Event:", json.dumps(event))

    res = rate_limit(event, context)
    if res:
        return res

    path = event.get("path", "")

    if (
        not path
        and "requestContext" in event
        and "resourcePath" in event["requestContext"]
    ):
        path = event["requestContext"]["resourcePath"]

    if path == "/test" or path.endswith("/test"):
        if event["httpMethod"] == "GET":
            response_data = {"message": "Hello from altverse /test"}
            return build_response(200, response_data)

    elif path == "/balances" or path.endswith("/balances"):
        if event["httpMethod"] == "POST":
            return handle_balances(event)

    elif path == "/spl-balances" or path.endswith("/spl-balances"):
        if event["httpMethod"] == "POST":
            return handle_spl_balances(event)

    elif path == "/allowance" or path.endswith("/allowance"):
        if event["httpMethod"] == "POST":
            return handle_allowance(event)

    elif path == "/metadata" or path.endswith("/metadata"):
        if event["httpMethod"] == "POST":
            return handle_metadata(event)

    elif path == "/prices" or path.endswith("/prices"):
        if event["httpMethod"] == "POST":
            return handle_prices(event)

    elif path == "/sui/coin-metadata" or path.endswith("/sui/coin-metadata"):
        if event["httpMethod"] == "POST":
            return handle_sui_coin_metadata(event)

    elif path == "/sui/balance" or path.endswith("/sui/balance"):
        if event["httpMethod"] == "POST":
            return handle_sui_balance(event)

    elif path == "/sui/all-coins" or path.endswith("/sui/all-coins"):
        if event["httpMethod"] == "POST":
            return handle_sui_all_coins(event)

    elif path == "/sui/all-balances" or path.endswith("/sui/all-balances"):
        if event["httpMethod"] == "POST":
            return handle_sui_all_balances(event)

    elif path == "/sui/coins" or path.endswith("/sui/coins"):
        if event["httpMethod"] == "POST":
            return handle_sui_coins(event)

    elif path == "/metrics" or path.endswith("/metrics"):
        if event["httpMethod"] == "POST":
            # Parse the body to get metricType
            try:
                body = json.loads(event.get("body", "{}"))
                metric_type = body.get("metricType")

                if metric_type == "swap":
                    return handle_swap_metrics(event)
                elif metric_type == "entrance":
                    return handle_entrance_metrics(event)
                elif metric_type == "earn":
                    return handle_earn_metrics(event)
                elif metric_type == "lending":
                    return handle_lending_metrics(event)
                else:
                    return build_response(
                        400,
                        {
                            "error": f"Invalid metricType: {metric_type}. Must be one of: swap, entrance, earn, lending"
                        },
                    )
            except json.JSONDecodeError:
                return build_response(400, {"error": "Invalid JSON body"})

    elif path == "/usage" or path.endswith("/usage"):
        if event["httpMethod"] == "POST":
            return handle_usage(event)

    return build_response(404, {"error": "Not found"})
