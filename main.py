from events import TickEvent, EVENT_BUS
import MetaTrader5 as mt5
import time as timer
from datetime import datetime, time, timezone
from nasdaq import Nasdaq
from threading import Thread
import discord
from discord.ext import commands, tasks
import queue
from dotenv import load_dotenv, dotenv_values

def event_loop():
    while True:
        timer.sleep(0.5)

        # Tick Event
        tick = mt5.symbol_info_tick("NAS100_SB")
        if tick is not None:
            tick_event = TickEvent(server_time=datetime.fromtimestamp(tick.time, tz=timezone.utc))
            EVENT_BUS.publish(tick_event)

load_dotenv()
env = dotenv_values(".env")

DISCORD_TOKEN = env.get("BOT_TOKEN")
DISCORD_CHANNEL_ID = env.get("CHANNEL_ID")
DISCORD_QUEUE = queue.Queue()

if DISCORD_TOKEN is None or DISCORD_CHANNEL_ID is None:
    raise ReferenceError("Please check your .env file and add your discord bot token, and discord server channel ID to the parameters.")

STOCKS = [
    Nasdaq(tp=100, sl=80, volume=1.0, discord_queue=DISCORD_QUEUE)
]

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Discord Bot logged in as {bot.user}")
    notification_loop.start()

    DISCORD_QUEUE.put("Discord bot initialized")

    for stock in STOCKS:
        stock.set_running(True)


@bot.command()
async def stop(ctx):
    for stock in STOCKS:
        stock.set_running(False)


@bot.command()
async def start(ctx):
    for stock in STOCKS:
        stock.set_running(True)


@bot.command()
async def status(ctx):
    for stock in STOCKS:
        if stock.running:
            await ctx.send(f"{stock.symbol}: :green_circle: RUNNING")
        else:
            await ctx.send(f"{stock.symbol}: :red_circle: STOPPED")

# TODO: Break even
# TODO: Close order

@bot.command()
async def reset(ctx):
    for stock in STOCKS:
        stock.reset()

# Discord message on main thread
@tasks.loop(seconds=1.0)
async def notification_loop():
    channel = bot.get_channel(DISCORD_CHANNEL_ID)
    if not channel:
        return

    while not DISCORD_QUEUE.empty():
        msg = DISCORD_QUEUE.get()
        try:
            await channel.send(f"```\n{msg}\n```")
        except Exception as e:
            print(f"Failed to send Discord message: {e}")

if __name__ == "__main__":
    # Attach separate thread to event loop
    event_thread = Thread(target=event_loop, daemon=True)
    event_thread.start()

    bot.run(DISCORD_TOKEN)
    

    
