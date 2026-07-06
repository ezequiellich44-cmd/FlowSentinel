from abc import ABC, abstractmethod
from typing import AsyncIterator, Union
from flowsentinel.models import TxIntent, PoolState, OrderBookSnapshot

class Feed(ABC):
    @abstractmethod
    async def stream(self) -> AsyncIterator[Union[TxIntent, PoolState, OrderBookSnapshot]]:
        """
        Asynchronously streams financial events from a venue (mempool, exchange, etc.).
        """
        yield  # Just a dummy yield to make it an async generator if subclassed
