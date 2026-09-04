from events import TickEvent, EventHandler
from stock import Stock

class Nasdaq(Stock):
    def __init__(self, tp: float, sl: float, volume: float, discord_queue: None):
        super().__init__("NAS100_SB", tp, sl, volume, discord_queue)

    @EventHandler(TickEvent)
    def on_tick(self, event: TickEvent):
        print("test")