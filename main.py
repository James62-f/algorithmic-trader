from events import TickEvent, event_bus
import MetaTrader5 as mt5
import time as timer
from datetime import datetime, time, timezone

if __name__ == "__main__":
    if not mt5.initialize():
        print("initialize() failed, error code =", mt5.last_error())
        quit()

    while True:
        timer.sleep(0.5)

        # Tick Event
        tick_event = TickEvent()
        event_bus.publish(tick_event)






