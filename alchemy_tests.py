import os
import json
import requests

ALCHEMY_API_KEY = os.environ.get("ALCHEMY_API_KEY")
NETWORK = "eth-mainnet"

# Well-known addresses and contracts
VITALIK_ADDRESS = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"
USDC_ADDRESS = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
DAI_ADDRESS = "0x6B175474E89094C44Da98b954EedeAC495271d0F"
UNISWAP_ROUTER = "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"


def call_alchemy(method, params):
    url = f"https://{NETWORK}.g.alchemy.com/v2/{ALCHEMY_API_KEY}"
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    response = requests.post(
        url, headers={"Content-Type": "application/json"}, json=payload, timeout=10
    )
    return response.json()


def test_get_token_balances():
    print("\n=== Testing Token Balances ===")
    params = [VITALIK_ADDRESS, [USDC_ADDRESS, DAI_ADDRESS]]
    response = call_alchemy("alchemy_getTokenBalances", params)

    print(f"Address: {VITALIK_ADDRESS}")
    if "result" in response:
        balances = response["result"]["tokenBalances"]
        for balance in balances:
            print(f"Token: {balance['contractAddress']}")
            print(f"Balance: {balance['tokenBalance']}")
    else:
        print("Error:", response.get("error", "Unknown error"))


def test_get_allowance():
    print("\n=== Testing Token Allowance ===")
    params = [
        {"owner": VITALIK_ADDRESS, "contract": DAI_ADDRESS, "spender": UNISWAP_ROUTER}
    ]
    response = call_alchemy("alchemy_getTokenAllowance", params)

    print(f"Owner: {VITALIK_ADDRESS}")
    print(f"Token: {DAI_ADDRESS}")
    print(f"Spender: {UNISWAP_ROUTER}")
    if "result" in response:
        print(f"Allowance: {response['result']}")
    else:
        print("Error:", response.get("error", "Unknown error"))


def test_get_token_metadata():
    print("\n=== Testing Token Metadata ===")

    tokens = [USDC_ADDRESS, DAI_ADDRESS]
    for token in tokens:
        print(f"\nChecking metadata for: {token}")
        params = [token]
        response = call_alchemy("alchemy_getTokenMetadata", params)

        if "result" in response:
            metadata = response["result"]
            print(f"Name: {metadata.get('name')}")
            print(f"Symbol: {metadata.get('symbol')}")
            print(f"Decimals: {metadata.get('decimals')}")
        else:
            print("Error:", response.get("error", "Unknown error"))


if __name__ == "__main__":
    if not ALCHEMY_API_KEY:
        print("Error: ALCHEMY_API_KEY environment variable not set")
        exit(1)

    test_get_token_balances()
    test_get_allowance()
    test_get_token_metadata()
