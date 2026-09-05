from events import TickEvent, EVENT_BUS
import MetaTrader5 as mt5
import time as timer
from datetime import datetime, time, timezone
from nasdaq import Nasdaq

if __name__ == "__main__":
    # Initialize stocks
    NASDAQ = Nasdaq(tp=100, sl=80, volume=1.0, discord_queue=None)

    while True:
        timer.sleep(0.5)

        # Tick Event
        tick_event = TickEvent(server_time=datetime.fromtimestamp(mt5.symbol_info_tick("NAS100_SB").time, tz=timezone.utc))
        EVENT_BUS.publish(tick_event)
