import discord
from discord import app_commands
from discord.ext import commands
import typing
from datetime import datetime, timezone
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

@app_commands.command(name="test_member_join", description="Test the member join functionality")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(user="The user to test with")
async def test_member_join(interaction: discord.Interaction, user: discord.Member):
    """Test the member join functionality manually"""
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
    # Create test log embed
    test_embed = discord.Embed(
        title="🧪 Manual Test Started",
        description=f"Testing member join functionality for {user.mention}",
        color=discord.Color.yellow(),
        timestamp=datetime.now(timezone.utc)
    )
    test_embed.add_field(name="Tested By", value=interaction.user.mention, inline=True)
    test_embed.add_field(name="Test Subject", value=user.mention, inline=True)
    test_embed.add_field(name="Current Roles", value=", ".join([role.name for role in user.roles]) if user.roles else "None", inline=False)
    test_embed.set_footer(text="Manual Test")
    # Send to logs
    if hasattr(mm_cog, "send_to_logs"):
        await mm_cog.send_to_logs(interaction.guild, test_embed)
    print(f"🧪 MANUAL TEST: Testing member join for {user.name}")
    # Run the test
    try:
        await mm_cog.on_member_join(user)
        # Create success log
        success_embed = discord.Embed(
            title="✅ Manual Test Completed",
            description=f"Member join test completed for {user.mention}",
            color=discord.Color.green(),
            timestamp=datetime.now(timezone.utc)
        )
        # Check if user was processed
        if user.id in mm_cog.member_original_roles:
            stored_roles = []
            guild = interaction.guild
            if guild is not None:
                for role_id in mm_cog.member_original_roles[user.id]:
                    role = guild.get_role(role_id)
                    if role:
                        stored_roles.append(role.name)
            success_embed.add_field(name="Roles Stored", value=", ".join(stored_roles) if stored_roles else "None", inline=False)
            success_embed.add_field(name="Monitoring Status", value="✅ Added to monitoring" if user.id in mm_cog.users_awaiting_verification else "❌ Not monitored", inline=True)
        else:
            success_embed.add_field(name="Result", value="No subscription roles found - no action taken", inline=False)
        success_embed.set_footer(text="Manual Test Result")
        # Send to logs
        if hasattr(mm_cog, "send_to_logs"):
            await mm_cog.send_to_logs(interaction.guild, success_embed)
        await interaction.followup.send(f"✅ Test completed for {user.mention}. Check logs channel for detailed results.", ephemeral=True)
    except Exception as e:
        # Create error log
        error_embed = discord.Embed(
            title="❌ Manual Test Failed",
            description=f"Error during member join test for {user.mention}",
            color=discord.Color.red(),
            timestamp=datetime.now(timezone.utc)
        )
        error_embed.add_field(name="Error", value=str(e), inline=False)
        error_embed.set_footer(text="Manual Test Error")
        # Send to logs
        if hasattr(mm_cog, "send_to_logs"):
            await mm_cog.send_to_logs(interaction.guild, error_embed)
        await interaction.followup.send(f"❌ Test failed for {user.mention}. Check logs channel for error details.", ephemeral=True)

async def setup(bot: commands.Bot):
    bot.tree.add_command(test_member_join) 