import discord
from discord import app_commands
from discord.ext import commands
import os

# List of allowed owner user IDs
OWNER_USER_IDS = {890323443252351046, 879714530769391686}

@app_commands.command(name="debug_logs", description="DM yourself the bot.log file. Optionally clear it after.")
@app_commands.describe(clear_after="Clear the log file after sending?")
async def debug_logs(interaction: discord.Interaction, clear_after: bool = False):
    if interaction.user.id not in OWNER_USER_IDS:
        return await interaction.response.send_message(
            "❌ You are not authorized to use this command.", ephemeral=True
        )
    log_path = "bot.log"
    if not os.path.exists(log_path):
        return await interaction.response.send_message(
            "❌ Log file not found.", ephemeral=True
        )
    try:
        file = discord.File(log_path, filename="bot.log")
        await interaction.user.send(
            content="Here is the current bot.log file." + (" (Log will be cleared after this)" if clear_after else ""),
            file=file
        )
        await interaction.response.send_message(
            "✅ Log file sent to your DMs!" + (" Log will be cleared." if clear_after else ""), ephemeral=True
        )
        if clear_after:
            with open(log_path, "w", encoding="utf-8") as f:
                f.truncate(0)
    except Exception as e:
        await interaction.response.send_message(f"❌ Failed to send log file: {e}", ephemeral=True)

async def setup(bot: commands.Bot):
    bot.tree.add_command(debug_logs) 