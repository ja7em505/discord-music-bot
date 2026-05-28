import asyncio
import discord
from discord.ext import commands
import os

TOKEN = os.environ.get("DISCORD_TOKEN") or os.getenv("DISCORD_TOKEN")
PREFIX = os.environ.get("PREFIX") or os.getenv("PREFIX", "!")

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)


@bot.event
async def on_ready():
    print(f"[+] Logged in as {bot.user}")
    print(f"[+] Prefix: {PREFIX}")
    print(f"[+] Servers: {len(bot.guilds)}")
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.listening,
            name=f"{PREFIX}play | {PREFIX}help",
        )
    )


async def main():
    await bot.load_extension("music")
    await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
