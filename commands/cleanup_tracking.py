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

@app_commands.command(name="cleanup_tracking", description="Clean up orphaned tracking data")
@app_commands.default_permissions(administrator=True)
async def cleanup_tracking(interaction: discord.Interaction):
    """Clean up tracking data for users who are no longer in the server"""
    if not is_authorized_guild_or_owner(interaction):
        return await interaction.response.send_message(
            "❌ You are not authorized to use this command.", ephemeral=True
        )
    # SECURITY: Block DMs and check admin permissions
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server!", ephemeral=True)
    if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ You need Administrator permissions!", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    bot = typing.cast(commands.Bot, interaction.client)
    member_cog = bot.get_cog("MemberManagement")
    if not member_cog:
        return await interaction.followup.send("❌ MemberManagement cog not loaded!", ephemeral=True)
    mm_cog = typing.cast(MemberManagement, member_cog)
    # Get the guild object robustly
    guild = interaction.guild
    if guild is None and hasattr(bot, 'get_guild'):
        guild_id = os.getenv('GUILD_ID')
        if guild_id:
            guild = bot.get_guild(int(guild_id))
    cleaned_stored = 0
    cleaned_monitoring = 0
    cleaned_verifying = 0
    cleaned_tickets = 0
    # Clean stored roles for users not in server
    for user_id in list(mm_cog.member_original_roles.keys()):
        member = guild.get_member(user_id) if guild and hasattr(guild, 'get_member') else None
        if not member:
            del mm_cog.member_original_roles[user_id]
            cleaned_stored += 1
    # Clean monitoring list
    for user_id in list(mm_cog.users_awaiting_verification):
        member = guild.get_member(user_id) if guild and hasattr(guild, 'get_member') else None
        if not member:
            mm_cog.users_awaiting_verification.discard(user_id)
            cleaned_monitoring += 1
    # Clean verifying list
    for user_id in list(mm_cog.users_being_verified):
        member = guild.get_member(user_id) if guild and hasattr(guild, 'get_member') else None
        if not member:
            mm_cog.users_being_verified.discard(user_id)
            cleaned_verifying += 1
    # Clean ticket channels mapping
    for user_id in list(mm_cog.user_ticket_channels.keys()):
        member = guild.get_member(user_id) if guild and hasattr(guild, 'get_member') else None
        if not member:
            del mm_cog.user_ticket_channels[user_id]
            cleaned_tickets += 1
    embed = discord.Embed(
        title="🧹 Cleanup Complete",
        description="Removed tracking data for users who left the server.",
        color=discord.Color.green()
    )
    embed.add_field(name="Stored Roles Cleaned", value=str(cleaned_stored), inline=True)
    embed.add_field(name="Monitoring Cleaned", value=str(cleaned_monitoring), inline=True)
    embed.add_field(name="Verifying Cleaned", value=str(cleaned_verifying), inline=True)
    embed.add_field(name="Ticket Channels Cleaned", value=str(cleaned_tickets), inline=True)
    await interaction.followup.send(embed=embed, ephemeral=True)
    # Log the action
    if hasattr(mm_cog, "send_to_logs"):
        await mm_cog.send_to_logs(
            guild,
            discord.Embed(title="Admin Command Used", description=f"/cleanup_tracking used by {interaction.user.mention}", color=discord.Color.purple())
        )

async def setup(bot: commands.Bot):
    bot.tree.add_command(cleanup_tracking) 