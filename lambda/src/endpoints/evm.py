import json
from ..utils.utils import build_response
from ..utils.api_callers import call_alchemy


# Expected event structure for /balances:
# {
#   "body": {
#     "network": "string", // Required: alchemy network name (e.g., "eth-mainnet")
#     "userAddress": "string", // Required: wallet address
#     "contractAddresses": "string" // Optional: Comma-separated list of token contract addresses
#   }
# }
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
