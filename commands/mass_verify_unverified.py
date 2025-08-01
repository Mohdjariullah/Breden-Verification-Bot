import discord
from discord import app_commands
from discord.ext import commands
import os
import io
import json
import json as pyjson
from typing import Any, Optional

UNVERIFIED_FILE = 'unverified_users.json'

OWNER_USER_IDS = {890323443252351046, 879714530769391686}
GUILD_ID = int(os.getenv('GUILD_ID', 0))

REMINDER_MESSAGE = (
    "👋 Hi! You still have the Unverified role in the server. "
    "Please complete the verification process to gain access. If you need help, contact an admin."
)

# --- Security check ---
def is_authorized_guild_or_owner(interaction):
    if interaction.guild and interaction.guild.id == GUILD_ID:
        return True
    if interaction.user.id in OWNER_USER_IDS:
        return True
    return False

def get_env_role_id(var_name):
    env_value = os.getenv(var_name)
    if env_value is None:
        raise ValueError(f"Environment variable '{var_name}' is not set")
    return int(env_value)

def load_unverified():
    try:
        with open(UNVERIFIED_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return {}

def save_unverified(data):
    with open(UNVERIFIED_FILE, 'w') as f:
        json.dump(data, f, indent=2)

class MassVerifyView(discord.ui.View):
    def __init__(self, unverified_members, member_role, unverified_role, unverified_users_json, author_id):
        super().__init__(timeout=120)
        self.unverified_members = unverified_members
        self.member_role = member_role
        self.unverified_role = unverified_role
        self.unverified_users_json = unverified_users_json
        self.author_id = author_id
        self.mass_verify_in_progress = False
        self.message: Optional[Any] = None  # Will hold the sent message

    async def on_timeout(self):
        # Disable all items and update the message
        for item in self.children:
            if isinstance(item, (discord.ui.Button, discord.ui.Select)):
                item.disabled = True
        if self.message and hasattr(self.message, 'edit') and callable(getattr(self.message, 'edit', None)):
            try:
                await self.message.edit(view=self, embed=self._expired_embed(self.message.embeds[0] if self.message.embeds else None))
            except Exception:
                pass

    def _expired_embed(self, original_embed):
        if original_embed:
            embed = original_embed.copy()
            embed.color = discord.Color.dark_grey()
            embed.set_footer(text="Session expired. Please re-run the command if needed.")
            return embed
        else:
            return discord.Embed(title="Session expired.", color=discord.Color.dark_grey())

    @discord.ui.button(label="Remind All", style=discord.ButtonStyle.primary, custom_id="remind_all")
    async def remind_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message("❌ Only the command invoker can use this.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        success = 0
        failed = 0
        for member in self.unverified_members:
            try:
                await member.send(REMINDER_MESSAGE)
                success += 1
            except Exception:
                failed += 1
        await interaction.followup.send(
            f"✅ Reminded {success} user(s). " + (f"❌ Failed to DM {failed} user(s)." if failed else ""),
            ephemeral=True
        )

    @discord.ui.button(label="Mass Verify", style=discord.ButtonStyle.success, custom_id="mass_verify")
    async def mass_verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message("❌ Only the command invoker can use this.", ephemeral=True)
        if self.mass_verify_in_progress:
            return await interaction.response.send_message("⏳ Mass verification already in progress.", ephemeral=True)
        # Show select menu for number of users
        select = MassVerifySelect(self.unverified_members, self.member_role, self.unverified_role, self.unverified_users_json, self.author_id)
        view = discord.ui.View()
        view.add_item(select)
        await interaction.response.send_message(
            "Select how many users to mass verify:",
            view=view,
            ephemeral=True
        )

class MassVerifySelect(discord.ui.Select):
    def __init__(self, unverified_members, member_role, unverified_role, unverified_users_json, author_id):
        options = [
            discord.SelectOption(label="10 users", value="10"),
            discord.SelectOption(label="50 users", value="50"),
            discord.SelectOption(label="100 users", value="100"),
            discord.SelectOption(label="300 users", value="300"),
            discord.SelectOption(label="All users", value="all"),
        ]
        super().__init__(placeholder="Choose how many to verify...", min_values=1, max_values=1, options=options)
        self.unverified_members = unverified_members
        self.member_role = member_role
        self.unverified_role = unverified_role
        self.unverified_users_json = unverified_users_json
        self.author_id = author_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message("❌ Only the command invoker can use this.", ephemeral=True)
        count = self.values[0]
        if count == "all":
            to_verify = self.unverified_members
        else:
            to_verify = self.unverified_members[:int(count)]
        affected = []
        to_remove_from_json = []
        for member in to_verify:
            try:
                await member.add_roles(self.member_role, reason="Mass verification by admin command")
            except Exception:
                pass
            try:
                await member.remove_roles(self.unverified_role, reason="Mass verification by admin command")
            except Exception:
                pass
            if str(member.id) in self.unverified_users_json:
                to_remove_from_json.append(str(member.id))
            affected.append({
                "user_id": member.id,
                "username": str(member),
                "original_roles": self.unverified_users_json.get(str(member.id), {}).get("original_roles", [])
            })
        for uid in to_remove_from_json:
            del self.unverified_users_json[uid]
        save_unverified(self.unverified_users_json)
        # Prepare JSON file for logs
        json_bytes = pyjson.dumps(affected, indent=2).encode('utf-8')
        json_file = discord.File(io.BytesIO(json_bytes), filename="mass_verified_unverified_users.json")
        # Send to logs channel
        logs_channel_id = os.getenv('LOGS_CHANNEL_ID')
        logs_channel = None
        if interaction.guild and logs_channel_id:
            logs_channel = interaction.guild.get_channel(int(logs_channel_id))
        embed = discord.Embed(
            title="✅ Mass Verified Unverified Users",
            description=f"{len(affected)} users were given the Member role and removed from Unverified." if affected else "No users with the Unverified role were found.",
            color=discord.Color.green()
        )
        if affected:
            embed.add_field(
                name="Users Updated",
                value="\n".join([f"<@{u['user_id']}>" for u in affected][:10]) +
                      (f"\n...and {len(affected)-10} more" if len(affected) > 10 else ""),
                inline=False
            )
        if logs_channel and isinstance(logs_channel, discord.TextChannel):
            await logs_channel.send(embed=embed, file=json_file)
        await interaction.response.send_message(embed=embed, ephemeral=True)

@app_commands.command(name="mass_verify_unverified", description="Show and manage all users with the Unverified role.")
@app_commands.default_permissions(administrator=True)
async def mass_verify_unverified(interaction: discord.Interaction):
    if not is_authorized_guild_or_owner(interaction):
        return await interaction.response.send_message(
            "❌ You are not authorized to use this command.", ephemeral=True
        )
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server!", ephemeral=True)
    if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ You need Administrator permissions!", ephemeral=True)
    await interaction.response.defer(ephemeral=True)

    guild = interaction.guild
    UNVERIFIED_ROLE_ID = int(os.getenv('UNVERIFIED_ROLE_ID', 0))
    unverified_role = guild.get_role(UNVERIFIED_ROLE_ID)
    member_role_id = get_env_role_id('MEMBER_ROLE_ID')
    if member_role_id is None:
        return await interaction.followup.send("❌ MEMBER_ROLE_ID is not set!", ephemeral=True)
    member_role = guild.get_role(member_role_id)
    if not unverified_role or not member_role:
        return await interaction.followup.send("❌ Unverified or Member role not found! Check your environment variables.", ephemeral=True)

    unverified_users_json = load_unverified()
    unverified_members = [m for m in guild.members if unverified_role in m.roles]
    embed = discord.Embed(
        title="🛡️ Unverified Users Management",
        description=f"There are **{len(unverified_members)}** users with the Unverified role.",
        color=discord.Color.orange()
    )
    if unverified_members:
        embed.add_field(
            name="Sample Users",
            value="\n".join([f"<@{m.id}>" for m in unverified_members[:10]]) +
                  (f"\n...and {len(unverified_members)-10} more" if len(unverified_members) > 10 else ""),
            inline=False
        )
    else:
        embed.add_field(name="No Unverified Users", value="All users are verified!", inline=False)
    view = MassVerifyView(unverified_members, member_role, unverified_role, unverified_users_json, interaction.user.id)
    sent = await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    try:
        view.message = await interaction.original_response()
    except Exception:
        view.message = None

async def setup(bot: commands.Bot):
    bot.tree.add_command(mass_verify_unverified) 