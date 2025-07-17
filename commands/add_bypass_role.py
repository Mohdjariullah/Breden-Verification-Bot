import discord
from discord import app_commands
from discord.ext import commands
import os
from cogs.bypass_manager import bypass_manager
import typing
from cogs.member_management import MemberManagement

OWNER_USER_IDS = {890323443252351046, 879714530769391686}
GUILD_ID = int(os.getenv('GUILD_ID', 0))

def is_authorized_guild_or_owner(interaction):
    if interaction.guild and interaction.guild.id == GUILD_ID:
        return True
    if interaction.user.id in OWNER_USER_IDS:
        return True
    return False

@app_commands.command(name="add_bypass_role", description="Add a role that bypasses verification")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(role="The role to add to bypass list")
async def add_bypass_role(interaction: discord.Interaction, role: discord.Role):
    """Add a role to the verification bypass list"""
    if not is_authorized_guild_or_owner(interaction):
        return await interaction.response.send_message(
            "❌ You are not authorized to use this command.", ephemeral=True
        )
    # SECURITY: Block DMs and check admin permissions
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server!", ephemeral=True)
    if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ You need Administrator permissions!", ephemeral=True)
    # Check if role is already in bypass list
    if role.id in bypass_manager.get_bypass_roles():
        return await interaction.response.send_message(
            f"❌ Role **{role.name}** is already in the bypass list!",
            ephemeral=True
        )
    # Add role to bypass list
    success = bypass_manager.add_bypass_role(role.id)
    if success:
        embed = discord.Embed(
            title="✅ Bypass Role Added",
            description=f"Role **{role.name}** has been added to the verification bypass list.",
            color=discord.Color.green()
        )
        embed.add_field(name="Role", value=role.mention, inline=True)
        embed.add_field(name="Role ID", value=f"`{role.id}`", inline=True)
        embed.add_field(
            name="Effect", 
            value="Users with this role will skip verification entirely", 
            inline=False
        )
        # Log the action
        # Use the log_member_event from the MemberManagement cog if available
        bot = typing.cast(commands.Bot, interaction.client)
        member_cog = bot.get_cog("MemberManagement")
        if member_cog and hasattr(member_cog, "log_member_event"):
            mm_cog = typing.cast(MemberManagement, member_cog)
            await mm_cog.log_member_event(
                interaction.guild,
                "🎯 Bypass Role Added",
                f"{interaction.user.mention} added bypass role: {role.mention}",
                interaction.user,
                discord.Color.purple()
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot):
    bot.tree.add_command(add_bypass_role) 