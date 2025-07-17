import discord
from discord import app_commands
from discord.ext import commands
import os
import logging
from cogs.welcome import get_or_create_welcome_message
from cogs.verification import VerificationView

OWNER_USER_IDS = {890323443252351046, 879714530769391686}
GUILD_ID = int(os.getenv('GUILD_ID', 0))

def is_authorized_guild_or_owner(interaction):
    if interaction.guild and interaction.guild.id == GUILD_ID:
        return True
    if interaction.user.id in OWNER_USER_IDS:
        return True
    return False

@app_commands.command(name="refresh_welcome", description="Manually refresh the welcome message")
@app_commands.default_permissions(administrator=True)
async def refresh_welcome(interaction: discord.Interaction):
    """Manually refresh the welcome message"""
    if not is_authorized_guild_or_owner(interaction):
        return await interaction.response.send_message(
            "❌ You are not authorized to use this command.", ephemeral=True
        )
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
    try:
        welcome_channel_id = os.getenv('WELCOME_CHANNEL_ID')
        bot = interaction.client
        welcome_channel = bot.get_channel(int(welcome_channel_id)) if welcome_channel_id else None
        if welcome_channel:
            channel_mention = welcome_channel.mention if isinstance(welcome_channel, discord.TextChannel) else str(welcome_channel)
            embed = discord.Embed(
                title="👋 Welcome to the Server!",
                description=(
                    "To access the server, you'll need to complete our verification process.\n\n"
                    "**What to expect:**\n"
                    "• Create a verification ticket\n"
                    "• Schedule a quick onboarding call\n"
                    "• Confirm your booking\n"
                    "• Get verified and gain access!\n\n"
                    "Click the button below to begin."
                ),
                color=0x5865F2
            )
            embed.set_footer(text="Join our community today!")
            embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1370122090631532655/1386775344631119963/65fe71ca-e301-40a0-b69b-de77def4f57e.jpeg")
            msg = await get_or_create_welcome_message(welcome_channel, embed, VerificationView())
            result_embed = discord.Embed(
                title="✅ Welcome Message Refreshed",
                description=f"Welcome message updated successfully.",
                color=discord.Color.green()
            )
            result_embed.add_field(name="Channel", value=channel_mention, inline=True)
            result_embed.add_field(name="Message", value=f"[Jump to message]({msg.jump_url})", inline=True)
            await interaction.followup.send(embed=result_embed, ephemeral=True)
        else:
            await interaction.followup.send("❌ Welcome channel not found! Check your .env file.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Error refreshing welcome message: {e}", ephemeral=True)

async def setup(bot: commands.Bot):
    bot.tree.add_command(refresh_welcome) 