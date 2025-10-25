import json
from .utils.rate_limitter import rate_limit
from .utils.utils import build_response
from .endpoints import evm, solana, sui, prices, metrics, analytics


def lambda_handler(event, context):
    """
    Main Lambda entry point.
    1. Applies rate limiting.
    2. Routes the request to the correct endpoint handler based on the path.
    """
    print("Event:", json.dumps(event))

    # Apply rate limiting first
    # rate_limit() will return a 429 response if triggered
    rate_limit_response = rate_limit(event, context)
    if rate_limit_response:
        return rate_limit_response

    # Route the request
    path = event.get("path", "")

    # Handle cases where path is in requestContext (e.g., API Gateway proxy)
    if (
        not path
        and "requestContext" in event
        and "resourcePath" in event["requestContext"]
    ):
        path = event["requestContext"]["resourcePath"]

    # Test endpoint
    if path == "/test" or path.endswith("/test"):
        if event["httpMethod"] == "GET":
            response_data = {"message": "Hello from altverse /test"}
            return build_response(200, response_data)

    # EVM endpoints
    elif path == "/balances" or path.endswith("/balances"):
        if event["httpMethod"] == "POST":
            return evm.handle_balances(event)

    elif path == "/allowance" or path.endswith("/allowance"):
        if event["httpMethod"] == "POST":
            return evm.handle_allowance(event)

    elif path == "/metadata" or path.endswith("/metadata"):
        if event["httpMethod"] == "POST":
            return evm.handle_metadata(event)

    # Solana endpoint
    elif path == "/spl-balances" or path.endswith("/spl-balances"):
        if event["httpMethod"] == "POST":
            return solana.handle_spl_balances(event)

    # Sui endpoints
    elif path == "/sui/coin-metadata" or path.endswith("/sui/coin-metadata"):
        if event["httpMethod"] == "POST":
            return sui.handle_coin_metadata(event)

    elif path == "/sui/balance" or path.endswith("/sui/balance"):
        if event["httpMethod"] == "POST":
            return sui.handle_balance(event)

    elif path == "/sui/all-coins" or path.endswith("/sui/all-coins"):
        if event["httpMethod"] == "POST":
            return sui.handle_all_coins(event)

    elif path == "/sui/all-balances" or path.endswith("/sui/all-balances"):
        if event["httpMethod"] == "POST":
            return sui.handle_all_balances(event)

    elif path == "/sui/coins" or path.endswith("/sui/coins"):
        if event["httpMethod"] == "POST":
            return sui.handle_coins(event)

    # Prices endpoint
    elif path == "/prices" or path.endswith("/prices"):
        if event["httpMethod"] == "POST":
            return prices.handle_prices(event)

    # Metrics & Analytics
    elif path == "/metrics" or path.endswith("/metrics"):
        if event["httpMethod"] == "POST":
            return metrics.handle(event)

    elif path == "/analytics" or path.endswith("/analytics"):
        if event["httpMethod"] == "POST":
            return analytics.handle(event)

    # 404 Not Found
    return build_response(404, {"error": "Not found"})
