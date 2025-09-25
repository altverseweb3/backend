import asyncio
from coingecko_sdk import AsyncCoingecko
from typing import List


class AsyncCoingeckoClient:
    def __init__(self, api_key):
        self.coingecko_api_key = api_key
        self.async_client = AsyncCoingecko(demo_api_key=api_key, environment='demo')

    async def get_prices(self, requests):
        if not requests:
            return []

        # Execute all requests concurrently
        tasks = [self._get_prices(request) for request in requests]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        return responses

    async def _get_prices(self, request):
        try:
            response = await self.async_client.simple.token_price.get_id(
                contract_addresses=request.addresses,
                id=request.network,
                vs_currencies='usd'
            )
            return response.to_dict()
        except Exception as e:
            print(f"Error fetching prices: {e}")
            return None