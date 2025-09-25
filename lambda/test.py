import json
import asyncio
import os
from api import Web3APIWrapper


async def main():
    # Test addresses
    USDC_ADDRESS = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
    DAI_ADDRESS = "0x6B175474E89094C44Da98b954EedeAC495271d0F"
    USDC_ARB_ADDRESS = "0xaf88d065e77c8cC2239327C5EDb3A432268e5831"

    # Initialize API wrapper
    api_wrapper = Web3APIWrapper(
        coingecko_api_key=os.environ.get("COINGECKO_API_KEY", ""),
        alchemy_api_key=os.environ.get("ALCHEMY_API_KEY", "")
    )

    # Test prices endpoint
    print("=== Testing /prices endpoint ===")
    prices_test_event = {
        "path": "/prices",
        "httpMethod": "POST",
        "body": json.dumps({
            "networks": [
                {
                    "network": "ethereum",
                    "addresses": [USDC_ADDRESS, DAI_ADDRESS]
                },
                {
                    "network": "arbitrum-one",
                    "addresses": [USDC_ARB_ADDRESS]
                }
            ]
        }),
    }

    try:
        response = await api_wrapper.handle_request(prices_test_event)
        print("Prices response:", response)
    except Exception as e:
        print(f"Prices test failed: {e}")

    print("\n" + "="*50 + "\n")

    # Test balances endpoint
    print("=== Testing /balances endpoint ===")
    balances_test_event = {
        "path": "/balances",
        "httpMethod": "POST",
        "body": json.dumps({
            "network": "eth-mainnet",
            "userAddress": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",  # Vitalik's address
            "contractAddresses": f"{USDC_ADDRESS},{DAI_ADDRESS}"
        }),
    }

    try:
        response = await api_wrapper.handle_request(balances_test_event)
        print("Balances response:", response)
    except Exception as e:
        print(f"Balances test failed: {e}")

    # Test error handling
    print("\n" + "="*50 + "\n")
    print("=== Testing error handling ===")

    error_test_event = {
        "path": "/nonexistent",
        "httpMethod": "POST",
        "body": json.dumps({}),
    }

    try:
        response = await api_wrapper.handle_request(error_test_event)
        print("Error handling response:", response)
    except Exception as e:
        print(f"Error test failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())