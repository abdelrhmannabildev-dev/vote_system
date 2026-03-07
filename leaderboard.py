# import discord
# from discord.ext import commands, tasks
# from utils import load_json

# LEADERBOARD_CHANNEL_ID = 1474644262049284107


# class LeaderboardCog(commands.Cog):
#     def __init__(self, bot):
#         self.bot = bot
#         self.leaderboard_message_id = None

#     @commands.Cog.listener()
#     async def on_ready(self):
#         # منع تشغيل الـ loop أكثر من مرة
#         if not hasattr(self.bot, 'leaderboard_loop_started'):
#             self.update_loop.start()
#             self.bot.leaderboard_loop_started = True
#     @commands.Cog.listener()
#     async def on_ready(self):
#         # منع تشغيل الـ loop أكثر من مرة
#         if not hasattr(self.bot, 'leaderboard_loop_started'):
#             self.update_loop.start()
#             self.bot.leaderboard_loop_started = True

#     async def update_leaderboard(self):
#         suggestions = load_json("suggestions.json") or {}

#         channel = self.bot.get_channel(LEADERBOARD_CHANNEL_ID)
#         if channel is None:
#             try:    
#                 channel = await self.bot.fetch_channel(LEADERBOARD_CHANNEL_ID)
#             except Exception:
#                 return

#         if not suggestions:
#             description = "No suggestions yet."
#         else:
#             sorted_suggestions = sorted(
#                 suggestions.items(),
#                 key=lambda x: x[1],
#                 reverse=True
#             )

#             lines = []
#             for i, (key, votes) in enumerate(sorted_suggestions[:3], start=1):
#                 try:
#                     item, vote_type = key.split("|")
#                 except ValueError:
#                     continue  # حماية من بيانات تالفة

#                 lines.append(f"#{i} {item} {vote_type} — {votes} votes")

#             description = "\n".join(lines) if lines else "No suggestions yet."

#         embed = discord.Embed(
#             title="📊 Suggestion Leaderboard",
#             description=description,
#             color=discord.Color.gold(),
#         )

#         # لو عندنا message_id نحاول نعدلها
#         if self.leaderboard_message_id:
#             try:
#                 msg = await channel.fetch_message(self.leaderboard_message_id)
#                 await msg.edit(embed=embed)
#                 return
#             except discord.NotFound:
#                 # الرسالة اتحذفت
#                 self.leaderboard_message_id = None
#             except Exception:
#                 return

#         # لو مفيش رسالة أو اتحذفت نعمل واحدة جديدة
#         try:
#             msg = await channel.send(embed=embed)
#             self.leaderboard_message_id = msg.id
#         except Exception:
#             pass

#     @tasks.loop(seconds=60)
#     async def update_loop(self):
#         await self.bot.wait_until_ready()
#         await self.update_leaderboard()

#     @update_loop.before_loop
#     async def before_update_loop(self):
#         await self.bot.wait_until_ready()


# async def setup(bot):
#     await bot.add_cog(LeaderboardCog(bot))