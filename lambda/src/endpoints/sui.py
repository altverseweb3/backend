import json
from ..utils.utils import build_response
from ..utils.api_callers import call_sui_api


# Expected event structure for /sui/coin-metadata:
# {
#   "body": {
#     "coinType": "string" // Required: Type name for the coin (e.g., "0x2::sui::SUI")
#   }
# }
def handle_coin_metadata(event):
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
def handle_balance(event):
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
def handle_all_coins(event):
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
def handle_all_balances(event):
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


# Expected event structure for /sui/coins:
# {
#   "body": {
#     "owner": "string", // Required: The owner's Sui address
#     "coinType": "string", // Optional: Type name for the coin
#     "cursor": "string", // Optional: Paging cursor
#     "limit": number // Optional: Maximum number of items per page
#   }
# }
def handle_coins(event):
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
