# vt_section.py
import discord
from discord.ext import commands, tasks
import json
import os
import datetime
from utils import load_json, save_json

# ================= CONFIG =================
VT_CHANNEL_ID = 1474644661649018960  # قناة الفريق للموافقة على التغييرات (temporary, should be dedicated VT channel)
PENDING_WINNERS_DIR = "pending_winners"
APPROVED_CHANGES_FILE = "data/approved_changes.json"
DATABASE_FILE = "items.csv"

# الدور المسموح للموافقة على التغييرات
VT_ROLE_ID = 1476309157136306360  # ضع هنا ID دور الفريق

def format_value(value):
    value = int(value)
    if value >= 1_000_000:
        return f"{value/1_000_000:.2f}M"
    if value >= 1_000:
        return f"{value/1_000}k"
    return str(value)
def load_pending_winners():
    """Load all pending winner files"""
    if not os.path.exists(PENDING_WINNERS_DIR):
        return []
    
    pending = []
    for filename in os.listdir(PENDING_WINNERS_DIR):
        if filename.endswith('.json'):
            try:
                with open(os.path.join(PENDING_WINNERS_DIR, filename), 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    data['filename'] = filename
                    pending.append(data)
            except Exception as e:
                print(f"[ERROR] Failed to load {filename}: {e}")
    
    return pending

def remove_pending_winner(filename):
    """Remove a processed winner file"""
    filepath = os.path.join(PENDING_WINNERS_DIR, filename)
    if os.path.exists(filepath):
        os.remove(filepath)

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

def apply_value_change(item_name, winning_option, current_value):
    """Apply the value change to the database"""
    items = load_database()
    
    for item in items:
        if item.get("name") == item_name:
            # Calculate new value
            if winning_option.startswith('+'):
                # Increase value
                change_amount = float(winning_option[1:].replace('M', '000000').replace('k', '000'))
                new_value = current_value + change_amount
            elif winning_option.startswith('-'):
                # Decrease value
                change_amount = float(winning_option[1:].replace('M', '000000').replace('k', '000'))
                new_value = max(0, current_value - change_amount)  # Don't go below 0
            else:
                # Direct value (like "2m")
                if 'm' in winning_option.lower():
                    new_value = float(winning_option.lower().replace('m', '')) * 1_000_000
                elif 'k' in winning_option.lower():
                    new_value = float(winning_option.lower().replace('k', '')) * 1_000
                else:
                    new_value = float(winning_option)
            
            item["value"] = str(int(new_value))
            print(f"[APPROVED] Updated {item_name} value from {current_value} to {new_value}")
            break
    
    save_database(items)

def save_approved_change(winner_data, approved_by):
    """Save approved change for tracking"""
    approved_data = load_json(APPROVED_CHANGES_FILE) or []
    
    change_record = {
        "item_name": winner_data["item_name"],
        "old_value": winner_data["current_value"],
        "winning_option": winner_data["winning_option"],
        "approved_by": approved_by,
        "approved_at": datetime.datetime.utcnow().isoformat(),
        "proposal_id": winner_data["proposal_id"]
    }
    
    approved_data.append(change_record)
    save_json(APPROVED_CHANGES_FILE, approved_data)

# ================= VT APPROVAL VIEW =================
class VTApprovalView(discord.ui.View):
    def __init__(self, winner_data, filename):
        super().__init__(timeout=None)
        self.winner_data = winner_data
        self.filename = filename

    @discord.ui.button(label="✅ Approve", style=discord.ButtonStyle.green, custom_id="vt:approve")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check if user has VT role
        if not any(r.id == VT_ROLE_ID for r in interaction.user.roles):
            await interaction.response.send_message("You don't have permission to approve changes.", ephemeral=True)
            return

        # Apply the change
        apply_value_change(
            self.winner_data["item_name"],
            self.winner_data["winning_option"],
            self.winner_data["current_value"]
        )
        
        # Save approval record
        save_approved_change(self.winner_data, str(interaction.user))
        
        # Remove from pending
        remove_pending_winner(self.filename)
        
        # Update the message
        embed = interaction.message.embeds[0]
        embed.color = discord.Color.green()
        embed.set_footer(text=f"✅ Approved by {interaction.user}")
        
        # Disable buttons
        for child in self.children:
            child.disabled = True
        
        await interaction.response.edit_message(embed=embed, view=self)
        
        await interaction.followup.send(f"✅ **{self.winner_data['item_name']}** value change approved!", ephemeral=False)

    @discord.ui.button(label="❌ Reject", style=discord.ButtonStyle.red, custom_id="vt:reject")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check if user has VT role
        if not any(r.id == VT_ROLE_ID for r in interaction.user.roles):
            await interaction.response.send_message("You don't have permission to reject changes.", ephemeral=True)
            return

        # Remove from pending (rejected)
        remove_pending_winner(self.filename)
        
        # Update the message
        embed = interaction.message.embeds[0]
        embed.color = discord.Color.red()
        embed.set_footer(text=f"❌ Rejected by {interaction.user}")
        
        # Disable buttons
        for child in self.children:
            child.disabled = True
        
        await interaction.response.edit_message(embed=embed, view=self)
        
        await interaction.followup.send(f"❌ **{self.winner_data['item_name']}** value change rejected!", ephemeral=False)

# ================= COG =================
class VTSectionCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.vt_channel = None
        self.pending_messages = {}  # Track pending approval messages

    @commands.Cog.listener()
    async def on_ready(self):
        """Initialize VT channel on ready"""
        try:
            self.vt_channel = self.bot.get_channel(VT_CHANNEL_ID)
            if self.vt_channel is None:
                try:
                    self.vt_channel = await self.bot.fetch_channel(VT_CHANNEL_ID)
                except discord.NotFound:
                    print(f"[ERROR] VT channel {VT_CHANNEL_ID} not found!")
                    self.vt_channel = None
                except Exception as e:
                    print(f"[ERROR] Failed to fetch VT channel: {e}")
                    self.vt_channel = None
        except Exception as e:
            print(f"[ERROR] Failed to initialize VT channel: {e}")
            self.vt_channel = None

        # Load existing pending winners and create approval messages
        if self.vt_channel:
            await self.load_pending_approvals()
        else:
            print("[WARNING] VT channel not available, skipping pending approvals load")

    async def load_pending_approvals(self):
        """Load all pending winners and create approval messages"""
        if not self.vt_channel:
            return

        pending_winners = load_pending_winners()
        
        for winner_data in pending_winners:
            # Check if we already have a message for this proposal
            proposal_id = winner_data["proposal_id"]
            if proposal_id in self.pending_messages:
                continue  # Already posted
            
            # Create approval embed
            embed = discord.Embed(
                title=f"🎯 Value Change Approval Required",
                description=f"**Item:** {winner_data['item_name']}\n"
                            f"**Current Value:** {format_value(winner_data['current_value'])}\n"
                            f"**Proposed Change:** {winner_data['winning_option']}\n"
                            f"**Type:** {winner_data.get('type', 'Value')}",
                color=discord.Color.blue(),
                timestamp=datetime.datetime.utcnow()
            )
            
            embed.set_footer(text="Vote Team Decision Required")
            
            # Create approval view
            view = VTApprovalView(winner_data, winner_data['filename'])
            
            # Send the approval message
            try:
                message = await self.vt_channel.send(embed=embed, view=view)
                self.pending_messages[proposal_id] = message.id
                print(f"[VT] Created approval message for {winner_data['item_name']}")
            except Exception as e:
                print(f"[ERROR] Failed to create approval message: {e}")

    @tasks.loop(minutes=5)  # Check every 5 minutes for new pending winners
    async def check_pending_winners(self):
        """Periodically check for new pending winners"""
        await self.load_pending_approvals()

    @commands.command(name="vtcheck")
    @commands.has_role(VT_ROLE_ID)
    async def check_pending_command(self, ctx: commands.Context):
        """Manually check for pending approvals"""
        pending_count = len(load_pending_winners())
        
        if pending_count == 0:
            await ctx.send("✅ No pending value change approvals.")
        else:
            await ctx.send(f"🔄 Found {pending_count} pending approvals. Refreshing...")
            await self.load_pending_approvals()
            await ctx.send("✅ Pending approvals refreshed!")

    @commands.command(name="vtstats")
    @commands.has_role(VT_ROLE_ID)
    async def show_stats(self, ctx: commands.Context):
        """Show VT approval statistics"""
        approved_data = load_json(APPROVED_CHANGES_FILE) or []
        pending_count = len(load_pending_winners())
        
        embed = discord.Embed(
            title="📊 VT Approval Statistics",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Pending Approvals",
            value=str(pending_count),
            inline=True
        )
        
        embed.add_field(
            name="Total Approved Changes",
            value=str(len(approved_data)),
            inline=True
        )
        
        if approved_data:
            recent = approved_data[-5:]  # Last 5 approvals
            recent_text = "\n".join([
                f"{item['item_name']}: {item['winning_option']} (by {item['approved_by']})"
                for item in recent
            ])
            embed.add_field(
                name="Recent Approvals",
                value=recent_text,
                inline=False
            )
        
        await ctx.send(embed=embed)

# ================= SETUP =================
async def setup(bot):
    cog = VTSectionCog(bot)
    await bot.add_cog(cog)
    # Start the periodic check
    cog.check_pending_winners.start()
