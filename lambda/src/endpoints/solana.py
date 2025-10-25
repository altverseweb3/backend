import json
from ..utils.utils import build_response
from ..utils.api_callers import call_alchemy


# Expected event structure for /spl-balances:
# {
#   "body": {
#     "network": "string", // Required: Solana network name (e.g., "solana-mainnet")
#     "userAddress": "string", // Required: Solana wallet address
#     "programId": "string", // Optional: The SPL token program ID to filter by
#     "mint": "string" // Optional: The SPL token mint address to filter by
#   }
# }
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
