import json
import os
import requests
from ..utils.utils import build_response


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
