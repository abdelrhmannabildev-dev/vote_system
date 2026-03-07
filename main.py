import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
TOKEN = os.getenv("TOKEN")
GUILD_ID = os.getenv("GUILD_ID")


class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.messages = True
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):

        # تحميل suggestion cog
        try:
            await self.load_extension("suggestion")
            print("[OK] Suggestion Cog loaded successfully!")
        except Exception as e:
            print(f"[ERROR] Failed to load suggestion extension: {e}")

        # تحميل vote_section cog
        try:
            await self.load_extension("vote_section")
            print("[OK] Vote Section Cog loaded successfully!")
        except Exception as e:
            print(f"[ERROR] Failed to load vote_section extension: {e}")

        # تحميل vt_section cog
        try:
            await self.load_extension("vt_section")
            print("[OK] VT Section Cog loaded successfully!")
        except Exception as e:
            print(f"[ERROR] Failed to load vt_section extension: {e}")

        # # تحميل leaderboard cog
        # try:
        #     await self.load_extension("leaderboard")
        #     print("[OK] Leaderboard Cog loaded successfully!")
        # except Exception as e:
        #     print(f"[ERROR] Failed to load leaderboard extension: {e}")

        # Sync commands
        try:
            if GUILD_ID:
                guild_id_int = int(GUILD_ID)
                guild = discord.Object(id=guild_id_int)
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)
                print(f"[OK] Synced {len(synced)} command(s) to guild {guild_id_int}.")
            else:
                synced = await self.tree.sync()
                print(f"[OK] Synced {len(synced)} global command(s).")
                print("[INFO] Global slash commands may take up to 1 hour to appear.")
        except Exception as e:
            print(f"[ERROR] Command sync failed: {e}")


bot = MyBot()


@bot.event
async def on_ready():
    print(f"[READY] {bot.user} is online and ready for action!")


if __name__ == "__main__":
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("[ERROR] No TOKEN found in .env file.")