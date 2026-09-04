from dataclasses import dataclass
from typing import Dict, Type, Any, List, Callable, TypeVar
from datetime import datetime, timezone
import MetaTrader5 as mt5

T = TypeVar('T')

class EventBus:

    def __init__(self) -> None:
        mt5.initialize()

        self._subscribers: Dict[Type[Any], List[Callable[[Any], Any]]] = {}

    def subscribe(self, event_type: Type[T], handler: Callable[[T], Any]) -> None:
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []

        self._subscribers[event_type].append(handler)

    def publish(self, event: Any) -> None:
        event_type = type(event)
        handlers = self._subscribers.get(event_type, [])

        for handler in handlers:
            handler(event)

    def register(self, instance: Any) -> None:
        for attr_name in dir(instance):
            attr = getattr(instance, attr_name)

            if callable(attr) and hasattr(attr, "_event_type"):
                self.subscribe(attr._event_type, attr)

EVENT_BUS = EventBus()

def EventHandler(event_type: Type[T]) -> Callable[[Callable[[T], Any]], Callable[[T], Any]]:

    def decorator(func: Callable[[T], Any]) -> Callable[[T], Any]:
        func._event_type = event_type
        return func

    return decorator


"""Events"""

@dataclass(frozen=True)
class TickEvent:
    # We can hard code the symbol here since the timezone data for US stocks are all equal
    server_time: datetime = datetime.fromtimestamp(mt5.symbol_info_tick("NAS100_SB").time, tz=timezone.utc)






    