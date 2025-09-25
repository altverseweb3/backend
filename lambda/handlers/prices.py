from typing import Dict, List, Union, Any
from .base import RequestHandler
from clients.coingecko import AsyncCoingeckoClient


class CGPricesRequest:
    def __init__(self, network: str, addresses: List[str]):
        self.network = network
        self.addresses = addresses

    @classmethod
    def from_dict(cls, data: dict):
        if "network" not in data or "addresses" not in data:
            raise ValueError("Missing required fields: network and addresses")
        if not isinstance(data["addresses"], list) or not all(isinstance(addr, str) for addr in data["addresses"]):
            raise ValueError("Addresses must be a list of strings")
        return cls(network=data["network"], addresses=data["addresses"])


class PricesRequestHandler(RequestHandler):
    def __init__(self, coingecko_client: AsyncCoingeckoClient):
        self.coingecko_client = coingecko_client

    async def handle(self, data: Dict[str, Any]) -> Any:
        requests = [CGPricesRequest.from_dict(entry) for entry in data.get("networks", [])]
        return await self.coingecko_client.get_prices(requests)