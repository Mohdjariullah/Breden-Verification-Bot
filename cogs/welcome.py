import discord
from discord.ext import commands
from discord import app_commands
import logging
import os
from .verification import VerificationView

class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        """Setup welcome channel when bot is ready"""
        try:
            guild = self.bot.get_guild(int(os.getenv('GUILD_ID')))
            if not guild:
                logging.error(f"Guild with ID {os.getenv('GUILD_ID')} not found")
                return
                
            welcome_channel = self.bot.get_channel(int(os.getenv('WELCOME_CHANNEL_ID')))
            if not welcome_channel:
                logging.error(f"Welcome channel with ID {os.getenv('WELCOME_CHANNEL_ID')} not found")
                return
                
            # Clean up only bot's previous messages
            try:
                deleted_count = 0
                async for message in welcome_channel.history(limit=100):
                    if message.author == self.bot.user:
                        await message.delete()
                        deleted_count += 1
                logging.info(f"Cleaned up {deleted_count} bot messages from welcome channel")
            except Exception as e:
                logging.error(f"Error cleaning welcome channel: {e}")
            
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
            embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1335112843476860968/1366511856994222201/funded.jpg")
            
            message = await welcome_channel.send(embed=embed, view=VerificationView())
            logging.info(f"Created new welcome message: {message.jump_url}")
            
        except Exception as e:
            logging.error(f"Error in on_ready welcome setup: {e}")

    @app_commands.command(name="setup_permissions", description="Setup channel permissions for verification system")
    @app_commands.default_permissions(administrator=True)
    async def setup_permissions(self, interaction: discord.Interaction):
        """Setup channel permissions for verification system"""
        # Defer immediately to prevent timeout
        await interaction.response.defer(ephemeral=True)
        
        guild = interaction.guild
        everyone_role = guild.default_role
        welcome_channel_id = int(os.getenv('WELCOME_CHANNEL_ID'))
        
        channels_updated = 0
        errors = 0
        
        try:
            for channel in guild.channels:
                try:
                    if channel.id == welcome_channel_id:
                        # Allow everyone to see welcome channel but not send messages
                        await channel.set_permissions(everyone_role, view_channel=True, send_messages=False)
                        logging.info(f"Set permissions for welcome channel: {channel.name}")
                        channels_updated += 1
                    else:
                        # Hide other channels from unverified users (those with only @everyone role)
                        await channel.set_permissions(everyone_role, view_channel=False)
                        logging.info(f"Hidden channel from @everyone: {channel.name}")
                        channels_updated += 1
                except Exception as e:
                    logging.error(f"Error setting permissions for channel {channel.name}: {e}")
                    errors += 1
            
            # Send followup message
            embed = discord.Embed(
                title="✅ Permissions Setup Complete",
                description=f"Updated permissions for **{channels_updated}** channels.",
                color=discord.Color.green()
            )
            
            if errors > 0:
                embed.add_field(name="⚠️ Errors", value=f"{errors} channels had permission errors", inline=False)
            
            embed.add_field(name="Welcome Channel", value=f"<#{welcome_channel_id}> - Visible, no sending", inline=False)
            embed.add_field(name="Other Channels", value="Hidden from @everyone", inline=False)
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(f"❌ Error setting up permissions: {e}", ephemeral=True)

    @app_commands.command(name="refresh_welcome", description="Manually refresh the welcome message")
    @app_commands.default_permissions(administrator=True)
    async def refresh_welcome(self, interaction: discord.Interaction):
        """Manually refresh the welcome message"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            welcome_channel = self.bot.get_channel(int(os.getenv('WELCOME_CHANNEL_ID')))
            if welcome_channel:
                # Clean up bot's messages
                deleted_count = 0
                try:
                    async for message in welcome_channel.history(limit=100):
                        if message.author == self.bot.user:
                            await message.delete()
                            deleted_count += 1
                except Exception as e:
                    logging.error(f"Error cleaning welcome channel: {e}")
                
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
                embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1335112843476860968/1366511856994222201/funded.jpg")
                
                message = await welcome_channel.send(embed=embed, view=VerificationView())
                
                result_embed = discord.Embed(
                    title="✅ Welcome Message Refreshed",
                    description=f"Cleaned up {deleted_count} old messages and posted new welcome message.",
                    color=discord.Color.green()
                )
                result_embed.add_field(name="Channel", value=welcome_channel.mention, inline=True)
                result_embed.add_field(name="Message", value=f"[Jump to message]({message.jump_url})", inline=True)
                
                await interaction.followup.send(embed=result_embed, ephemeral=True)
            else:
                await interaction.followup.send("❌ Welcome channel not found! Check your .env file.", ephemeral=True)
                
        except Exception as e:
            await interaction.followup.send(f"❌ Error refreshing welcome message: {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Welcome(bot))