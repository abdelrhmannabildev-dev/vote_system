import csv
import datetime
import os

import discord
from discord.ext import commands, tasks

from utils import load_json, save_json

# ================= CONFIGURATION =================
SUGGESTION_FILE = "data/suggestions.json"
DAILY_FILE = "data/daily_messages.json"
LIMIT_FILE = "data/suggestion_limits.json"
LEADERBOARD_STATE_FILE = "data/leaderboard_state.json"
SUGGESTION_CHANNEL_ID = 1474644262049284107
                        

PANEL_STATE_FILE = "data/panel_state.json"

PRIORITY_ROLE = 1476309157136306360
min_mssg = 0
items_data = []

# ================= DATA HELPERS =================
def load_items():
    global items_data
    items_data.clear()
    if os.path.exists("items.csv"):
        with open("items.csv", newline="", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if row.get("duped_value") == "N/A":
                    row["duped_value"] = row.get("value", "0")
                items_data.append(row)


def find_similar_items(query):
    query = query.lower()
    return [item for item in items_data if query in item["name"].lower()]


def get_leaderboard_message_id():
    state = load_json(LEADERBOARD_STATE_FILE)
    return state.get("message_id")


def set_leaderboard_message_id(message_id: int):
    save_json(LEADERBOARD_STATE_FILE, {"message_id": message_id})


def get_panel_message_id():
    state = load_json(PANEL_STATE_FILE)
    return state.get("message_id")


def set_panel_message_id(message_id: int):
    save_json(PANEL_STATE_FILE, {"message_id": message_id})

# ================= LEADERBOARD EMBED =================
def build_leaderboard_embed():
    suggestions = load_json(SUGGESTION_FILE)
    if not suggestions:
        description = "No suggestions yet."
    else:
        sorted_suggestions = sorted(
            suggestions.items(),
            key=lambda x: x[1],
            reverse=True
        )
        lines = []
        for i, (key, votes) in enumerate(sorted_suggestions[:10], start=1):
            item, vote_type = key.split("|")
            lines.append(f"#{i} **{item}** ({vote_type}) - `{votes}` votes")
        description = "\n".join(lines)

    return discord.Embed(
        title="Suggestion Leaderboard",
        description=description,
        color=discord.Color.blue(),
    )

# ================= VIEWS =================
class ItemButton(discord.ui.Button):
    def __init__(self, item, cog):
        super().__init__(
            label=f"{item['name']} - {item['category']}",
            style=discord.ButtonStyle.blurple
        )
        self.item = item
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        view = VoteTypeView(self.item["name"], self.cog)
        await interaction.response.edit_message(
            content=f"Select suggestion type for **{self.item['name']}**",
            view=view,
        )


class ItemSelectView(discord.ui.View):
    def __init__(self, matches, cog):
        super().__init__(timeout=60)
        self.matches = matches
        self.page = 0
        self.items_per_page = 5
        self.cog = cog
        self.update_buttons()

    def update_buttons(self):
        self.clear_items()
        start = self.page * self.items_per_page
        end = start + self.items_per_page
        current_items = self.matches[start:end]

        for item in current_items:
            self.add_item(ItemButton(item, self.cog))

        if self.page > 0:
            self.add_item(PrevPageButton())

        if end < len(self.matches):
            self.add_item(NextPageButton())


class PrevPageButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Prev", style=discord.ButtonStyle.gray)

    async def callback(self, interaction: discord.Interaction):
        self.view.page -= 1
        self.view.update_buttons()
        await interaction.response.edit_message(view=self.view)


class NextPageButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Next", style=discord.ButtonStyle.gray)

    async def callback(self, interaction: discord.Interaction):
        self.view.page += 1
        self.view.update_buttons()
        await interaction.response.edit_message(view=self.view)


class VoteTypeView(discord.ui.View):
    def __init__(self, item_name, cog):
        super().__init__(timeout=60)
        self.item_name = item_name
        self.cog = cog

    @discord.ui.button(label="C Value", style=discord.ButtonStyle.green)
    async def c_value(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_vote(interaction, "CLEAN Value")

    @discord.ui.button(label="D Value", style=discord.ButtonStyle.blurple)
    async def d_value(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_vote(interaction, "DUPED Value")

    @discord.ui.button(label="Demand", style=discord.ButtonStyle.gray)
    async def demand(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_vote(interaction, "Demand")

    async def process_vote(self, interaction: discord.Interaction, vote_type: str):
        today = str(datetime.date.today())
        user_id = str(interaction.user.id)
        limits = load_json(LIMIT_FILE)

        if today not in limits:
            limits[today] = {}

        if user_id not in limits[today]:
            limits[today][user_id] = {"count": 0, "entries": []}

        max_limit = 4 if any(r.id == PRIORITY_ROLE for r in interaction.user.roles) else 2
        entry_key = f"{self.item_name}|{vote_type}"

        if entry_key in limits[today][user_id]["entries"]:
            await interaction.response.send_message(
                "Already suggested this today.",
                ephemeral=True
            )
            return

        if limits[today][user_id]["count"] >= max_limit:
            await interaction.response.send_message(
                f"Limit reached ({max_limit}).",
                ephemeral=True
            )
            return

        limits[today][user_id]["count"] += 1
        limits[today][user_id]["entries"].append(entry_key)
        save_json(LIMIT_FILE, limits)

        suggestions = load_json(SUGGESTION_FILE)
        weight = 3 if any(r.id == PRIORITY_ROLE for r in interaction.user.roles) else 1
        suggestions[entry_key] = suggestions.get(entry_key, 0) + weight
        save_json(SUGGESTION_FILE, suggestions)

        await interaction.response.send_message("Suggestion submitted!", ephemeral=True)
        await self.cog.refresh_leaderboard()


class SuggestModal(discord.ui.Modal, title="Suggest A Change"):
    item_name_input = discord.ui.TextInput(
        label="Item Name",
        placeholder="Enter item name..."
    )

    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        today = str(datetime.date.today())
        daily_data = load_json(DAILY_FILE)
        user_msgs = daily_data.get(today, {}).get(str(interaction.user.id), 0)

        if user_msgs < min_mssg:
            await interaction.response.send_message(
                f"You need {min_mssg} messages today (Current: {user_msgs}).",
                ephemeral=True,
            )
            return

        matches = find_similar_items(self.item_name_input.value)

        if not matches:
            await interaction.response.send_message(
                "Item not found.",
                ephemeral=True
            )
            return

        if len(matches) > 1:
            view = ItemSelectView(matches, self.cog)
            await interaction.response.send_message(
                "Multiple items found. Select one:",
                view=view,
                ephemeral=True
            )
        else:
            item = matches[0]
            view = VoteTypeView(item["name"], self.cog)
            await interaction.response.send_message(
                f"Select suggestion type for **{item['name']}**",
                view=view,
                ephemeral=True,
            )


class SuggestionPanelView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="Open Suggestion",
        style=discord.ButtonStyle.green,
        custom_id="suggestion:open_modal",
    )
    async def open_suggestion(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SuggestModal(self.cog))

    # @discord.ui.button(
    #     label="Show Leaderboard",
    #     style=discord.ButtonStyle.blurple,
    #     custom_id="suggestion:show_leaderboard",
    # )
    # async def show_leaderboard(self, interaction: discord.Interaction, button: discord.ui.Button):
    #     await interaction.response.send_message(
    #         embed=build_leaderboard_embed(),
    #         ephemeral=True
    #     )


# ================= COG =================
class SuggestionCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        load_items()
        self.bot.add_view(SuggestionPanelView(self))

    @tasks.loop(seconds=60)
    async def leaderboard_show(self):
        await self.bot.wait_until_ready()
        if not self.leaderboard_loop.is_running():
            self.leaderboard_loop.start()
        await self.refresh_leaderboard()
        await self.refresh_panel()

    async def get_suggestion_channel(self):
        channel = self.bot.get_channel(SUGGESTION_CHANNEL_ID)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(SUGGESTION_CHANNEL_ID)
            except Exception:
                channel = None
        return channel

    async def refresh_leaderboard(self):
        await self.bot.wait_until_ready()
        channel = await self.get_suggestion_channel()
        if channel is None:
            return

        embed = build_leaderboard_embed()
        message_id = get_leaderboard_message_id()

        if message_id:
            try:
                msg = await channel.fetch_message(message_id)
                await msg.edit(embed=embed)
                return
            except Exception:
                pass

        msg = await channel.send(embed=embed)
        set_leaderboard_message_id(msg.id)

    async def refresh_panel(self):
        channel = await self.get_panel_channel()
        if channel is None:
            return

        embed = discord.Embed(
            title="Suggestion Panel",
            description="Use the buttons below to submit suggestions or view leaderboard.",
            color=discord.Color.blue(),
        )

        message_id = get_panel_message_id()
        if message_id:
            try:
                msg = await channel.fetch_message(message_id)
                await msg.edit(embed=embed, view=SuggestionPanelView(self))
                return
            except Exception:
                pass

        msg = await channel.send(embed=embed, view=SuggestionPanelView(self))
        set_panel_message_id(msg.id)

    @tasks.loop(seconds=60)
    async def leaderboard_loop(self):
        await self.bot.wait_until_ready()
        await self.refresh_leaderboard()

    @commands.command(name="panel")
    @commands.has_permissions(manage_guild=True)
    async def panel_command(self, ctx: commands.Context):
        await self.refresh_panel()
        await ctx.send("Panel refreshed.", delete_after=5)

    @panel_command.error
    async def panel_command_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("You need Manage Server permission to create the panel.")
        else:
            raise error


async def setup(bot):
    await bot.add_cog(SuggestionCog(bot))