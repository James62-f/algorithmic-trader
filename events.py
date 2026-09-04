from dataclasses import dataclass
from typing import Dict, Type, Any, List, Callable, TypeVar
from datetime import datetime, timezone
import MetaTrader5 as mt5

T = TypeVar('T')

class EventBus:

    def __init__(self) -> None:
        self._subscribers: Dict[Type[Any], List[Callable[[Any], Any]]] = {}

        def subscribe(self, event_type: Type[T], handler: Callable[[T], Any]) -> None:
            if event_type not in self._subscribers:
                self._subscribers = []

            self._subscribers[event_type].append(handler)

        def publish(self, event: Any) -> None:
            event_type = type(event)
            handlers = self._subscribers.get(event_type, [])

            for handler in handlers:
                handler(event)

event_bus = EventBus()

def EventHandler(event_type: Type[T]) -> Callable[[Callable[[T], Any]], Callable[[T], Any]]:

    def decorator(func: Callable[[T], Any]) -> Callable[[T], Any]:
        event_bus.subscribe(event_type, func)
        return func

    return decorator


"""Events"""

@dataclass(frozen=True)
class TickEvent:
    server_time: datetime = datetime.fromtimestamp(mt5.time_current())






    