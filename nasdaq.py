from events import TickEvent, EventHandler
from stock import Stock
from datetime import datetime
import MetaTrader5 as mt5
import pandas as pd


class Nasdaq(Stock):

    def __init__(
        self,
        tp: float,
        sl: float,
        volume: float,
        discord_queue: None = None,
    ):
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

        if not self.running:
            return

        match self.phase:
            case 1:
                self.phase_1(server_time)
            case 2:
                self.phase_2(server_time)
            case 3:
                pass
            case _:
                pass

    def phase_1(self, server_time: datetime):
        window_start = server_time.replace(hour=13, minute=0, second=0, microsecond=0)
        window_end = server_time.replace(hour=16, minute=30, second=0, microsecond=0)

        if server_time >= window_end:
            self.phase = 0
            self.append_log("London high/low break window expired")
            return

        if window_start <= server_time < window_end:
            if self.london_hl is None:
                self.london_hl = self.get_london_hl(server_time)

                if self.london_hl is None:
                    self.append_log("Waiting for London candles...")
                    return
                
                self.append_log(
                    f"self.london: {self.london_hl}"
                )

            tick = mt5.symbol_info_tick(self.symbol)

            if tick is None:
                self.append_log("Failed to fetch tick data")
                return

            high, low = self.london_hl

            if tick.bid < low:
                self.direction_bias = "UP"
                self.phase = 2

                self.append_log("London LOW broken. Direction bias set to UP (Expecting reversal)")

            elif tick.ask > high:
                self.direction_bias = "DOWN"
                self.phase = 2

                self.append_log("London HIGH broken. Direction bias set to DOWN (Expecting reversal)")

    def phase_2(self, server_time: datetime):
        nyc_open = server_time.replace(hour=13, minute=0, second=0, microsecond=0)
        nyc_close = server_time.replace(hour=18, minute=0, second=0, microsecond=0)

        if server_time >= nyc_close:
            self.phase = 0
            self.append_log("NYC FVG window expired")
            return

        if nyc_open <= server_time < nyc_close:
            rates = mt5.copy_rates_from_pos(
                self.symbol, mt5.TIMEFRAME_M15, 0, 4
            )

            if rates is None or len(rates) < 4:
                return

            rates_df = pd.DataFrame(rates)
            c1_high, c1_low = rates_df.iloc[0]["high"], rates_df.iloc[0]["low"]
            c3_high, c3_low = rates_df.iloc[2]["high"], rates_df.iloc[2]["low"]

            if self.direction_bias == "DOWN":
                if self.fvg_time is None:

                    if c1_high < c3_low:
                        self.fvg_time = rates_df.iloc[2]["time"]

                        self.append_log("Bullish FVG detected in move up. Waiting for live price to cross previous open...")

                if self.fvg_time is not None:
                    previous_open = rates_df.iloc[2]["open"]
                    current_price = rates_df.iloc[3]["close"]

                    if current_price < previous_open:
                        position = self.open_position("SHORT")
                        if position is None:
                            self.append_log(
                                "Failed to open SHORT position."
                            )
                            self.phase = 0
                            return

                        self.append_log(
                            "Live price surpassed previous open downwards."
                            " Opened SHORT."
                        )
                        self.phase = 3

            elif self.direction_bias == "UP":
                if self.fvg_time is None:
                    if c1_low > c3_high:
                        self.fvg_time = rates_df.iloc[2]["time"]
                        self.append_log(
                            "Bearish FVG detected in move down. Waiting for"
                            " live price to cross previous open..."
                        )

                if self.fvg_time is not None:
                    previous_open = rates_df.iloc[2]["open"]
                    current_price = rates_df.iloc[3]["close"]

                    if current_price > previous_open:
                        position = self.open_position("LONG")
                        if position is None:
                            self.append_log(
                                "Failed to open LONG position. Turning phase"
                                " off."
                            )
                            self.phase = 0
                            return

                        self.append_log(
                            "Live price surpassed previous open upwards. Opened"
                            " LONG."
                        )
                        self.phase = 3

    def monitor_positions(self):
        positions = mt5.positions_get(symbol=self.symbol)

        if positions is None or len(positions) == 0:
            if self.phase == 3:
                self.append_log("Position closed. Resetting trade state.")
                self.reset_trade_state()
            return

        tick = mt5.symbol_info_tick(self.symbol)
        if tick is None:
            return

        for pos in positions:
            if pos.magic != 234000:
                continue

            ticket = pos.ticket
            entry_price = pos.price_open
            pos_type = pos.type

            if pos_type == mt5.POSITION_TYPE_BUY:
                current_price = tick.bid
                points_gained = current_price - entry_price
            else:
                current_price = tick.ask
                points_gained = entry_price - current_price

            if not self.is_break_even:
                if points_gained >= 50.0:
                    self.modify_position_sl(ticket=ticket, new_sl=entry_price)
                    self.is_break_even = True
                    self.points_after_break_even = 0.0
                    self.append_log("Shifted SL to Break-Even at +50 points.")
            else:
                if points_gained - 50.0 > self.points_after_break_even + 10.0:
                    self.points_after_break_even = points_gained - 50.0

                    new_sl = (
                        entry_price + self.points_after_break_even
                        if pos_type == mt5.POSITION_TYPE_BUY
                        else entry_price - self.points_after_break_even
                    )

                    self.modify_position_sl(ticket=ticket, new_sl=new_sl)
                    self.append_log(f"Trailed SL to {new_sl:.2f}")

    def get_london_hl(self, server_time: datetime) -> tuple | None:
        london_open = server_time.replace(
            hour=9, minute=0, second=0, microsecond=0
        )
        london_close = server_time.replace(
            hour=12, minute=45, second=0, microsecond=0
        )

        rates = mt5.copy_rates_range(
            self.symbol, mt5.TIMEFRAME_M15, london_open, london_close
        )
        if rates is None or len(rates) == 0:
            return None

        rates_df = pd.DataFrame(rates)
        return max(rates_df["high"]), min(rates_df["low"])

    def reset_trade_state(self):
        self.phase = 1
        self.london_hl = None
        self.direction_bias = "NONE"
        self.fvg_time = None
        self.is_break_even = False
        self.points_after_break_even = 0.0

    def reset(self):
        self.reset_trade_state()
        super().reset()