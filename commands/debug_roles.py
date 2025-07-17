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

@app_commands.command(name="debug_roles", description="Debug role information for a user")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(user="The user to check")
async def debug_roles(interaction: discord.Interaction, user: discord.Member):
    """Debug role information for a user"""
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
    embed = discord.Embed(
        title=f"🔍 User Debug for {user} ({user.id})",
        color=discord.Color.blue()
    )
    # Show all roles
    all_roles = [f"{role.name} (ID: {role.id})" for role in user.roles]
    embed.add_field(name="All Roles", value="\n".join(all_roles) if all_roles else "None", inline=False)
    # Show environment variables
    launchpad_id = get_env_role_id('LAUNCHPAD_ROLE_ID')
    member_id = get_env_role_id('MEMBER_ROLE_ID')
    embed.add_field(name="Expected Role IDs", value=f"Launchpad: {launchpad_id}\nMember: {member_id}", inline=False)
    # Check if user has subscription roles
    user_role_ids = {role.id for role in user.roles}
    subscription_roles = set(filter(None, [launchpad_id, member_id]))
    has_subscription = bool(user_role_ids & subscription_roles)
    embed.add_field(name="Has Subscription Roles", value=str(has_subscription), inline=False)
    # Check stored roles (show names if possible)
    stored_roles = mm_cog.member_original_roles.get(user.id, [])
    stored_role_names = []
    if stored_roles and interaction.guild:
        for role_id in stored_roles:
            role = interaction.guild.get_role(role_id)
            if role:
                stored_role_names.append(f"{role.name} (ID: {role.id})")
            else:
                stored_role_names.append(f"Unknown Role (ID: {role_id})")
    embed.add_field(name="Stored Roles", value="\n".join(stored_role_names) if stored_role_names else "None", inline=False)
    # Check monitoring status
    is_monitored = user.id in mm_cog.users_awaiting_verification
    is_verifying = user.id in mm_cog.users_being_verified
    embed.add_field(name="Being Monitored", value=str(is_monitored), inline=True)
    embed.add_field(name="Currently Verifying", value=str(is_verifying), inline=True)
    # Show ticket channel if exists
    ticket_channel_id = mm_cog.user_ticket_channels.get(user.id)
    if ticket_channel_id and interaction.guild:
        channel = interaction.guild.get_channel(ticket_channel_id)
        if channel:
            embed.add_field(name="Ticket Channel", value=channel.mention, inline=False)
        else:
            embed.add_field(name="Ticket Channel", value=f"Unknown Channel (ID: {ticket_channel_id})", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)
    # Log the action
    if hasattr(mm_cog, "send_to_logs"):
        await mm_cog.send_to_logs(
            interaction.guild,
            discord.Embed(title="Admin Command Used", description=f"/debug_roles used by {interaction.user.mention} (target: {user.mention})", color=discord.Color.purple())
        )

async def setup(bot: commands.Bot):
    bot.tree.add_command(debug_roles) 