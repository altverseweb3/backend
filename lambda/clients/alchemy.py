import requests
from typing import Dict, List, Union


class AlchemyClient:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def call_alchemy(self, network: str, method: str, params: List[Union[str, Dict, List]]) -> Dict:
        url = f"https://{network}.g.alchemy.com/v2/{self.api_key}"
        payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}

        response = requests.post(
            url, headers={"Content-Type": "application/json"}, json=payload, timeout=10
        )
        return response.json()

    async def get_balances(self, request) -> List[Dict[str, str]]:
        try:
            formatted_balances = []

            # Get native token balance
            native_params = [request.user_address, "latest"]
            native_response = self.call_alchemy(request.network, "eth_getBalance", native_params)

            if "result" in native_response:
                native_balance = native_response["result"]

                # Pad the native balance to match ERC20 token format (32 bytes)
                if native_balance.startswith("0x"):
                    padded_balance = "0x" + native_balance[2:].zfill(64)
                else:
                    padded_balance = "0x" + native_balance.zfill(64)

                native_token_info = {
                    "contractAddress": (
                        "0x0000000000000000000000000000000000000000"
                        if request.network != "polygon-mainnet"
                        else "0x0000000000000000000000000000000000001010"
                    ),
                    "tokenBalance": padded_balance,
                }
                formatted_balances.append(native_token_info)
            else:
                print(f"Failed to retrieve native token balance: {native_response}")

            # Get ERC20 token balances
            params = [request.user_address]
            if request.contract_addresses:
                if "," in request.contract_addresses:
                    params.append(request.contract_addresses.split(","))
                else:
                    params.append([request.contract_addresses])

            alchemy_response = self.call_alchemy(request.network, "alchemy_getTokenBalances", params)

            if "result" not in alchemy_response:
                # If we have at least the native token balance, return that
                if formatted_balances:
                    return formatted_balances
                raise Exception("Failed to retrieve data from Alchemy API")

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

            return formatted_balances

        except Exception as e:
            raise Exception(f"An error occurred: {str(e)}")