import discord
from discord import app_commands
from discord.ext import commands
import typing
from typing import Optional
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

def get_pending_verification_users(mm_cog, guild):
    # Return a list of discord.Member objects for users who have not completed verification
    pending = []
    for user_id in mm_cog.member_original_roles:
        if user_id in mm_cog.users_awaiting_verification or user_id in mm_cog.users_being_verified:
            member = guild.get_member(user_id)
            if member:
                pending.append(member)
    return pending

@app_commands.command(name="force_verify", description="Manually verify a user and restore their subscription roles")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(user="The user to verify (optional, autocomplete)")
async def force_verify(interaction: discord.Interaction, user: Optional[str] = None):
    """Manually verify a user and restore their subscription roles. If no user is provided, suggest pending users."""
    # SECURITY: Block DMs and check admin permissions
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server!", ephemeral=True)
    if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ You need Administrator permissions!", ephemeral=True)
    if not is_authorized_guild_or_owner(interaction):
        return await interaction.response.send_message(
            "❌ You are not authorized to use this command.", ephemeral=True
        )
    await interaction.response.defer(ephemeral=True)
    bot = typing.cast(commands.Bot, interaction.client)
    member_cog = bot.get_cog("MemberManagement")
    if not member_cog:
        return await interaction.followup.send("❌ MemberManagement cog not loaded!", ephemeral=True)
    mm_cog = typing.cast(MemberManagement, member_cog)
    guild = interaction.guild
    member = None
    if user:
        try:
            member = guild.get_member(int(user))
        except Exception:
            member = None
        if not member:
            return await interaction.followup.send(f"❌ Could not find user with ID `{user}` in this server.", ephemeral=True)
    else:
        # No user provided, show a list of pending users
        pending = get_pending_verification_users(mm_cog, guild)
        if not pending:
            return await interaction.followup.send("✅ No users are currently pending verification!", ephemeral=True)
        embed = discord.Embed(
            title="Pending Users for Verification",
            description="Select a user to force verify (use autocomplete or provide user ID):",
            color=discord.Color.blue()
        )
        for m in pending[:10]:
            embed.add_field(name=m.display_name, value=m.mention, inline=True)
        await interaction.followup.send(embed=embed, ephemeral=True)
        return
    # Only call restore_member_roles if member is not None
    try:
        member_mention = member.mention if member is not None else 'Unknown User'
        restored_roles = await mm_cog.restore_member_roles(member)
        if restored_roles:
            role_names = [role.name for role in restored_roles]
            embed = discord.Embed(
                title="✅ Manual Verification Complete",
                description=f"Successfully verified {member_mention} and restored their subscription roles.",
                color=discord.Color.green()
            )
            embed.add_field(name="Restored Roles", value=", ".join(role_names), inline=False)
            await mm_cog.log_member_event(
                guild,
                "🔧 Manual Verification",
                f"{member_mention} was manually verified by {interaction.user.mention}",
                member,
                discord.Color.purple(),
                restored_roles
            )
        else:
            embed = discord.Embed(
                title="🚫 No Roles to Restore",
                description=f"{member_mention} has no stored subscription roles to restore.",
                color=discord.Color.yellow()
            )
        await interaction.followup.send(embed=embed, ephemeral=True)
        log_embed = discord.Embed(title="Admin Command Used", description=f"/force_verify used by {interaction.user.mention}", color=discord.Color.purple())
        log_embed.add_field(name="Target", value=member_mention, inline=True)
        if hasattr(mm_cog, "send_to_logs"):
            await mm_cog.send_to_logs(guild, log_embed)
    except Exception as e:
        await interaction.followup.send(f"❌ Error during manual verification: {e}", ephemeral=True)

@force_verify.autocomplete('user')
async def force_verify_autocomplete(interaction: discord.Interaction, current: str):
    bot = typing.cast(commands.Bot, interaction.client)
    member_cog = bot.get_cog("MemberManagement")
    if not member_cog:
        return []
    mm_cog = typing.cast(MemberManagement, member_cog)
    guild = interaction.guild
    if not guild:
        return []
    suggestions = []
    for user_id in list(mm_cog.member_original_roles.keys()):
        member = guild.get_member(user_id)
        if member and (user_id in mm_cog.users_awaiting_verification or user_id in mm_cog.users_being_verified):
            if current.lower() in member.display_name.lower():
                suggestions.append(app_commands.Choice(name=member.display_name, value=str(member.id)))
            if len(suggestions) >= 20:
                break
    return suggestions

async def setup(bot: commands.Bot):
    bot.tree.add_command(force_verify) 