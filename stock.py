
class Stock:

    def __init__(self, symbol: str, tp: float, sl: float, volume: float, discord_queue):
        self.symbol = symbol
        self.sl = sl
        self.volume = volume
        self.logs = []
        self.discord_queue = discord_queue

    def append_log(self, text):
        msg = f"{[self.symbol]} {text} "
        self.logs.append(msg)
        print(msg)

    


