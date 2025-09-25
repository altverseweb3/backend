import json
from typing import Dict, Union
from handlers.base import APIRouter
from handlers.prices import PricesRequestHandler
from handlers.balances import BalancesRequestHandler
from clients.coingecko import AsyncCoingeckoClient
from clients.alchemy import AlchemyClient

class Web3APIWrapper:
    def __init__(self, coingecko_api_key: str, alchemy_api_key: str):
        self.router = APIRouter()
        self.coingecko_client = AsyncCoingeckoClient(coingecko_api_key)
        self.alchemy_client = AlchemyClient(alchemy_api_key)
        self._setup_routes()

    def _setup_routes(self):
        # by doing this instead of our massive elifs, we get O(1) routing time
        self.router.register_handler("/prices", PricesRequestHandler(self.coingecko_client))
        self.router.register_handler("/balances", BalancesRequestHandler(self.alchemy_client))
    
    @staticmethod
    def build_response(status_code: int, body: Dict) -> Dict:
        return {
            "statusCode": status_code,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "**",
                "Access-Control-Allow-Methods": "ANY,OPTIONS,POST,GET",
                "Content-Type": "application/json",
            },
            "body": json.dumps(body).encode("utf-8"),
            "isBase64Encoded": True,
        }

    async def handle_request(self, event: Dict[str, Union[str, Dict]]) -> Dict[str, Union[int, str, Dict, bool]]:
        try:
            path = event.get("path")
            if not path or not isinstance(path, str):
                return self.build_response(400, {"error": "Missing path in request"})

            body_str = event.get("body", "{}")
            if not isinstance(body_str, str):
                return self.build_response(400, {"error": "Invalid body format"})

            body = json.loads(body_str)
            result = await self.router.route_request(path, body)

            return self.build_response(200, {"data": result})

        except ValueError as e:
            return self.build_response(404, {"error": str(e)})
        except json.JSONDecodeError as e:
            return self.build_response(400, {"error": f"Invalid JSON: {str(e)}"})
        except Exception as e:
            return self.build_response(500, {"error": f"Internal server error: {str(e)}"})