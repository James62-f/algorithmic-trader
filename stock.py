import MetaTrader5 as mt5
from typing import Any
from events import EVENT_BUS

class Stock:

    def __init__(self, symbol: str, tp: float, sl: float, volume: float, discord_queue: None):
        EVENT_BUS.register(self)

        self.symbol = symbol
        self.tp = tp
        self.sl = sl
        self.volume = volume
        self.logs = []
        self.discord_queue = discord_queue
        self.running = False

    def append_log(self, text: str):
        msg = f"{[self.symbol]} {text} "
        self.logs.append(msg)
        print(msg)

        if self.discord_queue is not None:
            self.discord_queue.put(msg)

    def set_running(self, value: bool):
        self.running = value

        msg = f"{"🟢" if self.running else "🔴"} Bot run state set to: {"enabled" if self.running else "disabled"}"
        self.append_log(msg)

    def get_filling_mode(self) -> Any:
        info = mt5.symbol_info(self.symbol)

        if not info:
            return mt5.ORDER_FILLING_RETURN
        
        if info.filling_mode & 1:
            return mt5.ORDER_FILLING_FOK
        
        elif info.filling_mode & 2:
            return mt5.ORDER_FILLING_IOC
        
        return mt5.ORDER_FILLING_RETURN

    def open_position(self, order_type: str) -> Any:
        tick = mt5.symbol_info_tick(self.symbol)
        symbol_info = mt5.symbol_info(self.symbol)

        if symbol_info is None or tick is None:
            self.append_log(f"Failed to fetch symbol info for {self.symbol}")
            return None

        if order_type == "LONG":
            trade_type = mt5.ORDER_TYPE_BUY
            price = tick.ask
            sl = price - self.sl
            tp = price + self.tp
        else:
            trade_type = mt5.ORDER_TYPE_SELL
            price = tick.bid
            sl = price + self.sl
            tp = price - self.tp

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": float(self.volume),
            "type": trade_type,
            "price": float(round(price, symbol_info.digits)),
            "sl": float(round(sl, symbol_info.digits)),
            "tp": float(round(tp, symbol_info.digits)),
            "deviation": 20,
            "magic": 234000,
            "comment": order_type,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": self.get_filling_mode(),
        }

        result = mt5.order_send(request)

        if result is None:
            self.append_log("order_send returned None (Check MT5 terminal connection)")
            return None

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            self.append_log(f"Order failed with retcode {result.retcode}: {result.comment}")
            return None
        
        return result

    def close_position(self, ticket, order_type, current_price: float, volume: float) -> Any:
        close_type = mt5.ORDER_TYPE_SELL if order_type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
        
        req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": float(volume),
            "type": close_type,
            "position": ticket,
            "price": current_price,
            "deviation": 20,
            "magic": 234000,
            "comment": "Closed order",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": self.get_filling_mode()
        }

        result = mt5.order_send(req)
        return result

    def modify_position_sl(self, ticket, new_sl):
        symbol_info = mt5.symbol_info(self.symbol)
        
        req = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": self.symbol,
            "position": ticket,
            "sl": float(round(new_sl, symbol_info.digits)),
            "magic": 234000
        }
        
        result = mt5.order_send(req)
        if result is None:
            self.append_log(f"Failed to modify SL for ticket {ticket}: order_send returned None")
            return None

        if result.retcode == mt5.TRADE_RETCODE_DONE:
            self.append_log(f"Successfully modified SL for ticket {ticket} to {new_sl}")
        else:
            self.append_log(f"Failed to modify SL: {result.comment}")
        return result

