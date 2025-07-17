import discord
from discord import app_commands
from discord.ext import commands
import typing
from cogs.member_management import MemberManagement
import os

OWNER_USER_IDS = {890323443252351046, 879714530769391686}
GUILD_ID = int(os.getenv('GUILD_ID', 0))

def is_authorized_guild_or_owner(interaction):
    if interaction.guild and interaction.guild.id == GUILD_ID:
        return True
    if interaction.user.id in OWNER_USER_IDS:
        return True
    return False

@app_commands.command(name="help_admin", description="List all admin commands and their descriptions")
@app_commands.default_permissions(administrator=True)
async def help_admin(interaction: discord.Interaction):
    """List all admin commands and their descriptions"""
    if not is_authorized_guild_or_owner(interaction):
        return await interaction.response.send_message(
            "❌ You are not authorized to use this command.", ephemeral=True
        )
    # SECURITY: Block DMs and check admin permissions
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server!", ephemeral=True)
    if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ You need Administrator permissions!", ephemeral=True)
    commands_info = [
        ("/force_verify <user>", "Manually verify a user and restore their subscription roles."),
        ("/remove_verification <user>", "Remove all subscription roles and tracking for a user."),
        ("/pending_verifications", "List all users currently awaiting verification or with failed verifications."),
        ("/retry_verification <user>", "Retry the verification/role restoration process for a user."),
        ("/bot_status", "Show bot uptime, latency, loaded cogs, and environment variable status."),
        ("/show_logs <count>", "Show the last N log entries (from file or memory)."),
        ("/debug_roles <user>", "Show all roles, expected roles, and tracking status for a user."),
        ("/cleanup_tracking", "Remove tracking for users who have left the server."),
        ("/reset_tracking", "Clear all tracking data (dangerous, admin only)."),
        ("/refresh_welcome", "Re-post the welcome/verification message."),
        ("/setup_permissions", "Set up channel permissions for onboarding."),
        ("/set_logs_channel <channel>", "Set the channel for logs."),
        ("/set_welcome_channel <channel>", "Set the channel for welcome/verification."),
        ("/help_admin", "List all admin commands and what they do."),
    ]
    embed = discord.Embed(
        title="🛠️ Admin Commands Help",
        description="List of available admin commands:",
        color=discord.Color.blue()
    )
    for cmd, desc in commands_info:
        embed.add_field(name=cmd, value=desc, inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)
    # Log the action
    bot = typing.cast(commands.Bot, interaction.client)
    member_cog = bot.get_cog("MemberManagement")
    if member_cog and hasattr(member_cog, "log_member_event"):
        mm_cog = typing.cast(MemberManagement, member_cog)
        await mm_cog.send_to_logs(
            interaction.guild,
            discord.Embed(title="Admin Command Used", description=f"/help_admin used by {interaction.user.mention}", color=discord.Color.purple())
        )

async def setup(bot: commands.Bot):
    bot.tree.add_command(help_admin) 