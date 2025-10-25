import os
import requests


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
