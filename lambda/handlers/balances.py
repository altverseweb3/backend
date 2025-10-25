from typing import Dict, List, Union, Optional, Any
from .base import RequestHandler
from clients.alchemy import AlchemyClient


class BalancesRequest:
    def __init__(self, network: str, user_address: str, contract_addresses: Optional[str] = None):
        self.network = network
        self.user_address = user_address
        self.contract_addresses = contract_addresses

    @classmethod
    def from_dict(cls, data: Dict[str, Union[str, List[str]]]):
        if "network" not in data or "userAddress" not in data:
            raise ValueError("Missing required fields: network and userAddress")
        if not isinstance(data["network"], str) or not isinstance(data["userAddress"], str):
            raise ValueError("network and userAddress must be strings")

        contract_addresses = data.get("contractAddresses")
        if contract_addresses is not None and not isinstance(contract_addresses, str):
            raise ValueError("contractAddresses must be a string")

        return cls(
            network=data["network"],
            user_address=data["userAddress"],
            contract_addresses=contract_addresses
        )


class BalancesRequestHandler(RequestHandler):
    def __init__(self, alchemy_client: AlchemyClient):
        self.alchemy_client = alchemy_client

    async def handle(self, data: Dict[str, Any]) -> List[Dict[str, str]]:
        request = BalancesRequest.from_dict(data)
        return await self.alchemy_client.get_balances(request)