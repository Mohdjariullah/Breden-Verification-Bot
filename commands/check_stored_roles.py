import discord
from discord import app_commands
from discord.ext import commands
import typing
import os
from cogs.member_management import MemberManagement

OWNER_USER_IDS = {890323443252351046, 879714530769391686}
GUILD_ID = int(os.getenv('GUILD_ID', 0))

def is_authorized_guild_or_owner(interaction):
    if interaction.guild and interaction.guild.id == GUILD_ID:
        return True
    if interaction.user.id in OWNER_USER_IDS:
        return True
    return False

def get_env_role_id(var_name):
    env_value = os.getenv(var_name)
    try:
        return int(env_value) if env_value is not None else None
    except Exception:
        return None

@app_commands.command(name="check_stored_roles", description="Check how many members have stored subscription roles")
@app_commands.default_permissions(administrator=True)
async def check_stored_roles(interaction: discord.Interaction):
    """Check how many members have stored subscription roles"""
    if not is_authorized_guild_or_owner(interaction):
        return await interaction.response.send_message(
            "❌ You are not authorized to use this command.", ephemeral=True
        )
    # SECURITY: Block DMs and check admin permissions
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server!", ephemeral=True)
    if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ You need Administrator permissions!", ephemeral=True)
    bot = typing.cast(commands.Bot, interaction.client)
    member_cog = bot.get_cog("MemberManagement")
    if not member_cog:
        return await interaction.response.send_message("❌ MemberManagement cog not loaded!", ephemeral=True)
    mm_cog = typing.cast(MemberManagement, member_cog)
    count = len(mm_cog.member_original_roles)
    monitoring_count = len(mm_cog.users_awaiting_verification)
    verifying_count = len(mm_cog.users_being_verified)
    embed = discord.Embed(
        title="📊 Pending Verifications",
        description=f"Currently tracking subscription roles for **{count}** members awaiting verification.",
        color=discord.Color.blue()
    )
    embed.add_field(name="👥 Users Awaiting Verification", value=str(count), inline=True)
    embed.add_field(name="🔍 Users Being Monitored", value=str(monitoring_count), inline=True)
    embed.add_field(name="⚙️ Users Being Verified", value=str(verifying_count), inline=True)
    embed.add_field(name="🛡️ Protection Status", value="Active" if monitoring_count > 0 else "Inactive", inline=True)
    if count > 0:
        pending_users = []
        subscription_roles = {
            get_env_role_id('LAUNCHPAD_ROLE_ID'): "🚀 VIP ($98/mo),($750/yr), or $1,000 for lifetime access)",
            get_env_role_id('MEMBER_ROLE_ID'): "👤 Member (Free)"
        }
        guild = interaction.guild
        for user_id in list(mm_cog.member_original_roles.keys())[:5]:  # Show first 5
            user = guild.get_member(user_id)
            user_roles = []
            for role_id in mm_cog.member_original_roles[user_id]:
                role_name = subscription_roles.get(role_id)
                if not role_name and guild:
                    role = guild.get_role(role_id)
                    if role:
                        role_name = role.name
                    else:
                        role_name = f"Role ID: {role_id}"
                user_roles.append(role_name)
            roles_text = ", ".join(user_roles) if user_roles else "Unknown"
            status_parts = []
            if user_id in mm_cog.users_awaiting_verification:
                status_parts.append("🔍 Monitored")
            if user_id in mm_cog.users_being_verified:
                status_parts.append("⚙️ Verifying")
            status = " | ".join(status_parts) if status_parts else "⚠️ Not tracked"
            if user is not None:
                pending_users.append(f"• {user.mention} - {roles_text} ({status})")
            else:
                pending_users.append(f"• [User Left] (ID: {user_id}) - {roles_text} ({status})")
        if pending_users:
            embed.add_field(
                name="Recent Pending Verifications",
                value="\n".join(pending_users) + (f"\n... and {count - len(pending_users)} more" if count > 5 else ""),
                inline=False
            )
    await interaction.response.send_message(embed=embed, ephemeral=True)
    # Log the action
    if hasattr(mm_cog, "send_to_logs"):
        await mm_cog.send_to_logs(
            interaction.guild,
            discord.Embed(title="Admin Command Used", description=f"/check_stored_roles used by {interaction.user.mention}", color=discord.Color.purple())
        )

async def setup(bot: commands.Bot):
    bot.tree.add_command(check_stored_roles) 