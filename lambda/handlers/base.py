from abc import ABC, abstractmethod
from typing import Dict, List, Union, Any


class RequestHandler(ABC):
    @abstractmethod
    async def handle(self, data: Dict[str, Any]) -> Any:
        pass


class APIRouter:
    def __init__(self):
        self._routes: Dict[str, RequestHandler] = {}

    def register_handler(self, path: str, handler: RequestHandler):
        self._routes[path] = handler

    async def route_request(self, path: str, data: Dict[str, Any]) -> Any:
        if path not in self._routes:
            raise ValueError(f"No handler registered for path: {path}")

        handler = self._routes[path]
        return await handler.handle(data)

    def get_registered_routes(self) -> List[str]:
        return list(self._routes.keys())