import discord
from discord import app_commands
from discord.ext import commands
import typing

@app_commands.command(name="verification_stats", description="Show verification statistics")
@app_commands.default_permissions(administrator=True)
async def verification_stats(interaction: discord.Interaction):
    """Show verification statistics"""
    # SECURITY: Block DMs and check admin permissions
    if not interaction.guild:
        return await interaction.response.send_message(
            "❌ This command can only be used in a server, not in DMs!",
            ephemeral=True
        )
    if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message(
            "❌ You need Administrator permissions to use this command!",
            ephemeral=True
        )
    bot = typing.cast(commands.Bot, interaction.client)
    member_cog = bot.get_cog('MemberManagement')
    if not member_cog:
        return await interaction.response.send_message("❌ MemberManagement cog not loaded.", ephemeral=True)
    total_pending = len(getattr(member_cog, 'member_original_roles', {}))
    total_failed = sum(1 for v in getattr(member_cog, 'failed_verification_logged', {}).values() if v)
    total_verified = getattr(member_cog, 'total_verified', 0)
    embed = discord.Embed(
        title="📊 Verification Stats",
        color=discord.Color.blue(),
        timestamp=discord.utils.utcnow()
    )
    embed.add_field(name="Pending Verifications", value=str(total_pending), inline=True)
    embed.add_field(name="Failed Verifications", value=str(total_failed), inline=True)
    embed.add_field(name="Completed Verifications", value=str(total_verified), inline=True)
    embed.set_footer(text=f"Requested by {interaction.user.name}")
    await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot):
    bot.tree.add_command(verification_stats) 