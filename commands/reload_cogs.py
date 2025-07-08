import discord
from discord import app_commands
from discord.ext import commands
import logging
import typing

@app_commands.command(name="reload_cogs", description="Reload all bot cogs")
@app_commands.default_permissions(administrator=True)
async def reload_cogs(interaction: discord.Interaction):
    """Reload all bot cogs"""
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
    await interaction.response.defer(ephemeral=True)
    bot = typing.cast(commands.Bot, interaction.client)
    cogs = ["cogs.verification", "cogs.member_management", "cogs.welcome"]
    results = []
    for cog in cogs:
        try:
            await bot.reload_extension(cog)
            results.append(f"✅ {cog} reloaded")
            logging.info(f"Admin {interaction.user.name} reloaded cog: {cog}")
        except Exception as e:
            results.append(f"❌ {cog} failed: {str(e)[:50]}")
            logging.error(f"Failed to reload {cog}: {e}")
    await interaction.followup.send("\n".join(results), ephemeral=True)

async def setup(bot: commands.Bot):
    bot.tree.add_command(reload_cogs) 