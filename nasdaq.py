from events import TickEvent, EventHandler
from stock import Stock
from datetime import datetime, timedelta
import MetaTrader5 as mt5
import pandas as pd
import time as timer

class Nasdaq(Stock):
    def __init__(self, tp: float, sl: float, volume: float, discord_queue: None):
        super().__init__("NAS100_SB", tp, sl, volume, discord_queue)

        self.phase = 1
        self.london_hl = None
        self.direction_bias = "NONE"
        self.fvg_time = None
        self.is_break_even = False
        self.points_after_break_even = 0.0

    @EventHandler(TickEvent)
    def on_tick(self, event: TickEvent):
        server_time = event.server_time

        self.monitor_positions()

        match self.phase:
            case 1:
                self.phase_1(server_time)

            case 2:
                self.phase_2(server_time)

            case _:
                self.append_log("Unknown phase detected. Turning bot off.")
                self.set_running(False)


    def phase_1(self, server_time: datetime):
        """
        author: James P
        This function checks for the break of london high and low within the new york session.
        """
        window_start = server_time.replace(hour=13, minute=0, second=0, microsecond=0)
        window_end = server_time.replace(hour=16, minute=30, second=0, microsecond=0)

        if server_time >= window_end:
            self.phase = 0
            self.append_log("London high/low break window expired")
            return

        if window_start <= server_time < window_end:

            if self.london_hl is None:
                self.london_hl = self.get_london_hl(server_time)
                self.append_log(f"London High: {self.london_hl[0]}, London Low: {self.london_hl[1]}")

            tick = mt5.symbol_info_tick(self.symbol)
            if tick is None:
                self.append_log(f"Failed to fetch tick data")
                return

            high, low = self.london_hl
            if tick.bid > low:
                self.direction_bias = "UP"
                self.phase = 2
                self.append_log(f"London LOW broken. Direction bias set to UP")

            elif tick.ask > high:
                self.direction_bias = "DOWN"
                self.phase = 2
                self.append_log(f"London HIGH broken. Direction bias set to DOWN")

    def phase_2(self, server_time: datetime):
        """
        author: James P
        This function will await for a fair value gap to occur in the direction of the bias. If a fair value gap and price cross occurs, phase 3 will proceed.
        """

        nyc_open = server_time.replace(hour=13, minute=0, second=0, microsecond=0)
        nyc_close = server_time.replace(hour=18, minute=0, second=0, microsecond=0)

        if server_time >= nyc_close:
            self.phase = 0
            self.append_log("NYC fvg window expired")
            return

        if nyc_open <= server_time < nyc_close:

            rates = mt5.copy_rates_from_pos(self.symbol, mt5.TIMEFRAME_M15, 0, 4)
            if rates is None or len(rates) < 4:
                self.append_log(f"Failed to fetch rates")
                return

            rates_df = pd.DataFrame(rates)

            c1_high, c1_low = rates_df.iloc[0]['high'], rates_df.iloc[0]['low']
            c3_high, c3_low = rates_df.iloc[2]['high'], rates_df.iloc[2]['low']

            if self.direction_bias == "DOWN":
                if self.fvg_time is None:
                    if c1_high < c3_low:
                        self.fvg_time = rates_df.iloc[2]['time']
                        self.append_log("Bullish fvg detected. Waiting for live price to cross previous open...")

                if self.fvg_time is not None:
                    previous_open = rates_df.iloc[2]['open']
                    current_price = rates_df.iloc[3]['close']

                    if current_price < previous_open:
                        position = self.open_position("SHORT")

                        if position is None:
                            self.phase = 0
                            return

                        self.append_log(f"Live price surpassed previous open downwards. Opened SHORT")
                        self.phase = 3
                        return

            elif self.direction_bias == "UP":
                if self.fvg_time is None:
                    if c1_low > c3_high:
                        self.fvg_time = rates_df.iloc[2]['time']
                        self.append_log("Bearish fvg detected. Waiting for live price to cross previous open...")

                if self.fvg_time is not None:
                    previous_open = rates_df.iloc[2]['open']
                    current_price = rates_df.iloc[3]['close']

                    if current_price > previous_open:
                        position = self.open_position("LONG")

                        if position is None:
                            self.phase = 0
                            return

                        self.append_log(f"Live price surpassed previous open upwards. Opened LONG")
                        self.phase = 3
                        return

    def monitor_positions(self):
        """
        author: James P
        This function will monitor the stock price and modify the stop if necessary.
        """

        positions = mt5.positions_get(self.symbol)

        if positions is None or len(positions) == 0:
            return

        tick = mt5.symbol_info_tick(self.symbol)
        if tick is None:
            return

        symbol_info = mt5.symbol_info(self.symbol)
        if symbol_info is None:
            return

        for pos in positions:
            ticket = pos.ticket
            entry_price = pos.price_open
            order_type = pos.type

            if order_type == mt5.ORDER_TYPE_BUY:
                current_price = tick.bid
                points_gained = current_price - entry_price

            else:
                current_price = tick.ask
                points_gained = entry_price - current_price

            # Break even logic
            if not self.is_break_even:
                if points_gained >= 50:
                    self.modify_position_sl(ticket=ticket, new_sl=entry_price)
                    self.is_break_even = True
                    self.append_log("Shifted SL to break even at +50 points.")
                    self.points_after_break_even = 0

            else:
                # Trailing SL
                if points_gained - 50 > self.points_after_break_even + 10:
                    self.points_after_break_even = points_gained - 50

                    new_sl = entry_price + self.points_after_break_even if order_type == mt5.POSITION_TYPE_BUY else entry_price - self.points_after_break_even
                    self.modify_position_sl(ticket=ticket, new_sl=new_sl)
        
    
    def get_london_hl(self, server_time: datetime) -> tuple | None:
        london_open = server_time.replace(hour=9, minute=0, second=0, microsecond=0)
        london_close = server_time.replace(hour=12, minute=45, second=0, microsecond=0)

        rates = mt5.copy_rates_range(self.symbol, mt5.TIMEFRAME_M15, london_open, london_close)
        if rates is None or len(rates) == 0:
            return None

        rates_df = pd.DataFrame(rates)
        return max(rates_df['high']), min(rates_df['low'])