import asyncio
import io
import discord
from discord.ext import commands
from discord import app_commands
import logging
import os
import json
from datetime import datetime, timezone
from .verification import VerificationView

WELCOME_MESSAGE_FILE = 'welcome_message.json'

async def get_or_create_welcome_message(welcome_channel, embed, view):
    """Fetch or create the persistent welcome message, updating if needed."""
    # Try to load the message ID
    try:
        with open(WELCOME_MESSAGE_FILE, 'r') as f:
            data = json.load(f)
            msg_id = data.get('message_id')
            channel_id = data.get('channel_id')
    except Exception:
        msg_id = None
        channel_id = None
    # If channel ID doesn't match, ignore old message
    if channel_id != getattr(welcome_channel, 'id', None):
        msg_id = None
    # Try to fetch and edit the message
    if msg_id:
        try:
            msg = await welcome_channel.fetch_message(msg_id)
            await msg.edit(embed=embed, view=view)
            return msg
        except Exception:
            pass  # Message missing or deleted
    # Post a new message and save its ID
    msg = await welcome_channel.send(embed=embed, view=view)
    with open(WELCOME_MESSAGE_FILE, 'w') as f:
        json.dump({'message_id': msg.id, 'channel_id': welcome_channel.id}, f)
    return msg

class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        """Setup welcome channel when bot is ready (persistent message)"""
        try:
            guild_id = os.getenv('GUILD_ID')
            guild = self.bot.get_guild(int(guild_id)) if guild_id and hasattr(self.bot, 'get_guild') else None
            if not guild:
                logging.error(f"Guild with ID {guild_id} not found")
                return
            welcome_channel_id = os.getenv('WELCOME_CHANNEL_ID')
            if not welcome_channel_id:
                logging.error("WELCOME_CHANNEL_ID is not set in environment variables")
                return
            welcome_channel = self.bot.get_channel(int(welcome_channel_id))
            if not welcome_channel:
                logging.error(f"Welcome channel with ID {welcome_channel_id} not found")
                return
            # Create new welcome embed
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
            # Use persistent message logic
            msg = await get_or_create_welcome_message(welcome_channel, embed, VerificationView())
            logging.info(f"Welcome message is now persistent: {msg.jump_url}")
        except Exception as e:
            logging.error(f"Error in on_ready welcome setup: {e}")

async def setup(bot):
    await bot.add_cog(Welcome(bot))