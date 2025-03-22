import json
import os
import requests


# Expected event structure:
# {
#   "path": "/test" | "/balances" | "/allowance" | "/metadata",
#   "httpMethod": "GET" | "POST" | "ANY" | "PUT",
#   "body": "JSON string"
# }
def lambda_handler(event, context):
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

    return build_response(404, {"error": "Not found"})


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
