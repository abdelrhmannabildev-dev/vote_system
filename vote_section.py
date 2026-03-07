# vote_section.py
import discord
from discord.ext import commands, tasks
import csv
import json
import datetime
import os

# ================= CONFIG =================
VOTE_CHANNEL_ID = 1474644587128819783  # القناة اللي هيظهر فيها التصويت
TEAM_CHANNEL_ID = 1474644262049284107  # قناة الفريق للموافقة (temporary, should be VT channel)
VOTE_DURATION_SECONDS = 3600          # مدة التصويت (ساعة مثلاً)

# خيارات التصويت للقيم
VOTE_OPTIONS_VALUES = ["+250k", "+500k", "+1M", "+1.25M", "+1.5M","2m","1.75m"]

# خيارات التصويت للديماند (قابلة للتعديل)
VOTE_OPTIONS_DEMAND = ["Low", "Medium", "High", "Very High"]

# ملفات تخزين الأصوات
VOTES_FILE = "data/votes.json"
CURRENT_VOTE_STATE_FILE = "data/current_vote_state.json"

# قاعدة البيانات CSV
DATABASE_FILE = "items.csv"

# الدور المسموح لبدء التصويت يدوي
ALLOWED_ROLE_ID = 1476309157136306360  # ضع هنا ID الدور

# ================= HELPERS =================
def format_value(value):

    value = int(value)

    if value >= 1_000_000:
        return f"{value/1_000_000:.2f}M"

    if value >= 1_000:
        return f"{value/1_000}k"

    return str(value)
def load_votes():
    if os.path.exists(VOTES_FILE):
        try:
            with open(VOTES_FILE, "r") as f:
                data = json.load(f)
                # Ensure it has the correct structure
                if isinstance(data, dict) and "votes" in data:
                    return data
        except (json.JSONDecodeError, IOError):
            pass
    return {"votes": []}

def save_votes(votes_list):
    """Save vote with detailed information (user_id, timestamp, vote, proposal_id)"""
    if not isinstance(votes_list, list):
        votes_list = []
    data = {"votes": votes_list}
    with open(VOTES_FILE, "w") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def add_vote(user_id, user_name, vote_value, proposal_id):
    """Add a single vote with timestamp.

    The file `votes.json` acts as a history log. If the same user changes
    their choice for the same proposal we remove the old entry before
    appending the new one.  Debug output is printed so you can see when the
    function runs.
    """
    votes_data = load_votes()

    # remove any previous vote from this user on the same proposal
    votes_data["votes"] = [
        v for v in votes_data.get("votes", [])
        if not (v.get("user_id") == str(user_id) and v.get("proposal_id") == proposal_id)
    ]

    vote_record = {
        "user_id": str(user_id),
        "user_name": user_name,
        "vote": vote_value,
        "proposal_id": proposal_id,
        "timestamp": datetime.datetime.utcnow().isoformat()
    }
    votes_data["votes"].append(vote_record)
    save_votes(votes_data.get("votes", []))
    print(f"[DEBUG] added vote: {vote_record}")

def load_current_vote_state():
    """Load the current active vote state"""
    if os.path.exists(CURRENT_VOTE_STATE_FILE):
        with open(CURRENT_VOTE_STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

def save_current_vote_state(proposal_id, message_id, channel_id, item_data, votes_data):
    """Save the current active vote state"""
    state = {
        "proposal_id": proposal_id,
        "message_id": message_id,
        "channel_id": channel_id,
        "item_data": item_data,
        "votes_data": votes_data,
        "timestamp": datetime.datetime.utcnow().isoformat()
    }
    with open(CURRENT_VOTE_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=4, ensure_ascii=False)

def clear_current_vote_state():
    """Clear the current vote state"""
    if os.path.exists(CURRENT_VOTE_STATE_FILE):
        os.remove(CURRENT_VOTE_STATE_FILE)

LEADERBOARD_FILE = "data/suggestions.json"

def load_database():
    items = []
    with open(DATABASE_FILE, newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            items.append(row)
    return items

def save_database(items):
    if not items:
        return
    keys = items[0].keys()
    with open(DATABASE_FILE, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=keys)
        writer.writeheader()
        writer.writerows(items)

def get_top_item():
    if not os.path.exists(LEADERBOARD_FILE):
        return None

    with open(LEADERBOARD_FILE, "r", encoding="utf-8") as f:
        leaderboard = json.load(f)

    if not leaderboard:
        return None

    # نجيب العنصر الأعلى قيمة حسب leaderboard.json
    top_key = max(leaderboard.items(), key=lambda x: x[1])[0]  # مثال: "Torpedo|D Value"
    item_name, item_type = top_key.split("|")

    # نروح لـ CSV ونجيب الصف المطابق للاسم
    items = load_database()
    top_item = None
    for row in items:
        if row.get("name") == item_name.strip():
            top_item = row
            break

    if not top_item:
        return None

    # تحويل القيمة النهائية للقيمة الرقمية
    try:
        raw_value = str(top_item.get("value", "0")).replace(",", "").replace("N/A","0")
        top_item["value"] = float(raw_value)
    except Exception as e:
        print(f"[ERROR] Failed to parse value for {item_name}: {e}")
        top_item["value"] = 0

    # حفظ النوع اللي جاي من leaderboard
    top_item["type"] = item_type.strip()

    return top_item
# ================= VOTE VIEW =================
class VoteView(discord.ui.View):

    def __init__(self, proposal_id, item):
        super().__init__(timeout=VOTE_DURATION_SECONDS)

        self.proposal_id = proposal_id
        self.item = get_top_item()

        self.votes = {}
        self.results = {}

        # أزرار الاتجاه
        self.add_item(DirectionButton("increase", self))
        self.add_item(DirectionButton("decrease", self))


    def calculate_results(self):

        tally = {}

        for vote in self.votes.values():
            tally[vote] = tally.get(vote, 0) + 1

        self.results = tally


    def build_embed(self):

        description=f"Current Value: **{format_value(self.item['value'])}**\n\n"
        if not self.results:
            description += "No votes yet."

        else:
            for option, count in self.results.items():
                description += f"**{option}** → {count} votes\n"

        embed = discord.Embed(
            title=f"Vote for {self.item['name']}",
            description=description,
            color=discord.Color.blue()
        )

        return embed

    def _get_winner_option(self):
        """Return the option string that has the highest vote count.

        The internal `results` mapping may be stale if no votes have been
        tallied since the last change, so recalc as needed.  Returns `None`
        when there are no votes.
        """
        if not self.results:
            self.calculate_results()
        if not self.results:
            return None
        return max(self.results.items(), key=lambda x: x[1])[0]

    def _save_winner_to_file(self, winner_option):
        """Dump the winner metadata to a file and return the path."""
        winner_data = {
            "proposal_id": self.proposal_id,
            "item_name": self.item['name'],
            "current_value": self.item['value'],
            "winning_option": winner_option,
            "type": self.item.get("type", "")
        }
        os.makedirs("pending_winners", exist_ok=True)
        file_path = os.path.join("pending_winners", f"{self.proposal_id}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(winner_data, f, indent=4, ensure_ascii=False)
        return file_path

    async def on_timeout(self):
        """Called when vote times out"""
        winner_option = self._get_winner_option()
        if not winner_option:
            clear_current_vote_state()
            return

        file_path = self._save_winner_to_file(winner_option)
        print(f"[VOTE] Vote completed for {self.item['name']} - Winner: {winner_option}")
        print(f"[VOTE] Pending approval saved to: {file_path}")
        clear_current_vote_state()

class VoteButton(discord.ui.Button):
    def __init__(self, label, proposal_id, view):
        super().__init__(label=label, style=discord.ButtonStyle.green)
        self.proposal_id = proposal_id
        self.vote_view = view

    async def callback(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        user_name = interaction.user.name

        # منع التصويت المكرر
        self.vote_view.votes[user_id] = self.label

        # حفظ التصويت مع تفاصيل المستخدم والوقت
        add_vote(user_id, user_name, self.label, self.proposal_id)

        # إعادة حساب النتائج
        self.vote_view.calculate_results()

        # تحديث الـ embed
        embed = self.vote_view.build_embed()

        await interaction.response.edit_message(embed=embed, view=self.vote_view)
        
        # Update only votes_data in the current vote state (keep channel/message intact)
        state = load_current_vote_state()
        if not state:
            print("[DEBUG] no state file found when trying to update votes")
        elif state.get("proposal_id") != self.proposal_id:
            print(f"[DEBUG] proposal id mismatch: state has {state.get('proposal_id')} vs view {self.proposal_id}")
        else:
            # keep the original channel/message ids in case they changed elsewhere
            save_current_vote_state(
                self.proposal_id,
                state.get("message_id"),
                state.get("channel_id"),
                state.get("item_data"),
                self.vote_view.votes,
            )
            print(f"[DEBUG] state updated with votes {self.vote_view.votes}")

class DirectionButton(discord.ui.Button):

    def __init__(self, direction, view):
        super().__init__(label=direction, style=discord.ButtonStyle.blurple)
        self.direction = direction
        self.vote_view = view

    async def callback(self, interaction: discord.Interaction):

        self.vote_view.clear_items()

        if self.direction == "increase":
            options = VOTE_OPTIONS_VALUES
        else:
            options = ["-" + v.replace("+", "") for v in VOTE_OPTIONS_VALUES]

        for option in options:
            self.vote_view.add_item(VoteButton(option, self.vote_view.proposal_id, self.vote_view))

        embed = self.vote_view.build_embed()
        await interaction.response.edit_message(embed=embed, view=self.vote_view)
# ================= COG =================
class VoteSectionCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.vote_message = None
        self.vote_proposal_id = None
        self.vote_view = None
        self.loop_started = False

    @commands.Cog.listener()
    async def on_ready(self):
        """Restore vote on bot startup"""
        if not self.loop_started:
            self.loop_started = True
            self.post_vote_loop.start()
            
        # Try to restore the current vote if it exists
        current_state = load_current_vote_state()
        if current_state:
            try:
                channel_id = current_state.get("channel_id")
                if not channel_id:
                    print("[INFO] No channel_id in vote state, clearing state")
                    clear_current_vote_state()
                    return
                    
                channel = self.bot.get_channel(channel_id)
                if not channel:
                    try:
                        channel = await self.bot.fetch_channel(channel_id)
                    except discord.NotFound:
                        print(f"[ERROR] Vote state channel {channel_id} not found, clearing state")
                        clear_current_vote_state()
                        return
                    except Exception as e:
                        print(f"[ERROR] Failed to fetch channel {channel_id}: {e}")
                        clear_current_vote_state()
                        return
                
                if channel:
                    message_id = current_state.get("message_id")
                    if not message_id:
                        print("[INFO] No message_id in vote state, clearing state")
                        clear_current_vote_state()
                        return
                        
                    try:
                        self.vote_message = await channel.fetch_message(message_id)
                        
                        # Restore vote view with previous votes
                        proposal_id = current_state["proposal_id"]
                        item_data = current_state["item_data"]
                        votes_data = current_state["votes_data"]
                        
                        self.vote_proposal_id = proposal_id
                        
                        # Restore VoteView
                        self.vote_view = VoteView(proposal_id, item_data.get("type", "").lower() == "demand")
                        
                        # Restore previous votes
                        for user_id, vote_value in votes_data.items():
                            self.vote_view.votes[user_id] = vote_value
                        
                        self.vote_view.calculate_results()
                        embed = self.vote_view.build_embed()
                        
                        # Update the message with restored view
                        await self.vote_message.edit(embed=embed, view=self.vote_view)
                        print(f"[RESTORED] Vote for {item_data['name']} restored successfully")
                    except discord.NotFound:
                        # Message was deleted, clear state
                        print("[INFO] Vote message not found, clearing state")
                        clear_current_vote_state()
                    except Exception as e:
                        print(f"[ERROR] Failed to restore vote message: {e}")
                        clear_current_vote_state()
                else:
                    print("[INFO] Channel not accessible, clearing vote state")
                    clear_current_vote_state()
            except Exception as e:
                print(f"[ERROR] Failed to restore vote: {e}")
                clear_current_vote_state()

    # ===== دالة مشتركة بين loop و command =====
    async def post_vote_loop_iteration(self, top_item, ctx_channel=None):
        self.vote_proposal_id = f"{top_item['name']}|{datetime.datetime.utcnow().isoformat()}"
        is_demand = top_item.get("type", "").lower() == "demand"

        channel = ctx_channel if ctx_channel else self.bot.get_channel(VOTE_CHANNEL_ID)
        if not channel:
            return

        embed = discord.Embed(
            title=f"Vote for Top Item: {top_item['name']}",
            description=f"Current Value: **{format_value(top_item['value'])}**\n\n",
            color=discord.Color.green() if ctx_channel else discord.Color.blue()
        )
        self.vote_view = VoteView(self.vote_proposal_id, is_demand)
        self.vote_view.bot = self.bot
        self.vote_message = await channel.send(embed=embed, view=self.vote_view)
        
        # Save the current vote state
        save_current_vote_state(
            self.vote_proposal_id,
            self.vote_message.id,
            channel.id,
            {
                "name": top_item["name"],
                "value": str(top_item.get("value", "0")),
                "type": top_item.get("type", "")
            },
            {}
        )

    # ===== LOOP تلقائي كل ساعة =====
    @tasks.loop(seconds=3600)
    async def post_vote_loop(self):
        await self.bot.wait_until_ready()
        top_item = get_top_item()
        if top_item:
            await self.post_vote_loop_iteration(top_item)

    # ===== COMMAND لبدء التصويت يدوي =====
    @commands.command(name="startvote")
    @commands.has_role(ALLOWED_ROLE_ID)
    async def start_vote_command(self, ctx: commands.Context):
        """Manually start voting on the top suggestion"""
        top_item = get_top_item()
        if not top_item:
            return await ctx.send("No top item found to vote on.")

        await self.post_vote_loop_iteration(top_item, ctx_channel=ctx.channel)
        await ctx.send(f"Vote started manually by {ctx.author.mention} for **{top_item['name']}**!")

    @commands.command(name="endvote")
    @commands.has_role(ALLOWED_ROLE_ID)
    async def end_vote_command(self, ctx: commands.Context):
        """Manually end the current vote and send to VT approval"""
        if not self.vote_view:
            await ctx.send("No active vote to end.")
            return

        # Force timeout logic (but we need to capture the winner file path)
        try:
            # use the view helpers so we always compute and save the winner
            winner_option = self.vote_view._get_winner_option()
            if winner_option:
                file_path = self.vote_view._save_winner_to_file(winner_option)
                await ctx.send(f"✅ Vote manually ended. Winner **{winner_option}** saved to {file_path}")
            else:
                await ctx.send("✅ Vote ended but no votes were cast, nothing was sent to VT.")

            # call on_timeout anyway to handle state clearing
            await self.vote_view.on_timeout()
        except Exception as e:
            print(f"[ERROR] Failed to end vote: {e}")
            await ctx.send("Error ending vote.")
            return

        # Clear the vote message
        if self.vote_message:
            try:
                embed = self.vote_message.embeds[0]
                embed.color = discord.Color.orange()
                embed.set_footer(text="Vote manually ended")
                await self.vote_message.edit(embed=embed, view=None)
            except Exception as e:
                print(f"[ERROR] Failed to update vote message: {e}")
        
        # Reset vote state
        self.vote_message = None
        self.vote_proposal_id = None
        self.vote_view = None

    @commands.command(name="end")
    @commands.has_role(ALLOWED_ROLE_ID)
    async def end_command(self, ctx: commands.Context):
        """Alias for endvote - manually end the current vote"""
        await self.end_vote_command(ctx)

    @commands.command(name="votestatus")
    async def vote_status_command(self, ctx: commands.Context):
        """Check the current vote status and remaining time"""
        if not self.vote_view or not self.vote_message:
            await ctx.send("No active vote currently running.")
            return

        # Calculate remaining time
        remaining = self.vote_view.timeout
        if remaining:
            hours = int(remaining // 3600)
            minutes = int((remaining % 3600) // 60)
            seconds = int(remaining % 60)
            time_str = f"{hours}h {minutes}m {seconds}s"
        else:
            time_str = "Expired"

        embed = discord.Embed(
            title="Current Vote Status",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Item",
            value=self.vote_view.item['name'] if self.vote_view.item else "Unknown",
            inline=True
        )
        
        embed.add_field(
            name="Time Remaining",
            value=time_str,
            inline=True
        )
        
        embed.add_field(
            name="Total Votes",
            value=str(len(self.vote_view.votes)),
            inline=True
        )
        
        if self.vote_view.results:
            results_text = "\n".join([f"**{option}** → {count} votes" for option, count in self.vote_view.results.items()])
            embed.add_field(
                name="Current Results",
                value=results_text,
                inline=False
            )
        
        await ctx.send(embed=embed)

# ================= SETUP =================
async def setup(bot):
    await bot.add_cog(VoteSectionCog(bot))