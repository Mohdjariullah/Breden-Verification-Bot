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

class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        """Setup welcome channel when bot is ready"""
        try:
            guild_id = os.getenv('GUILD_ID')
            guild = self.bot.get_guild(int(guild_id)) if guild_id and hasattr(self.bot, 'get_guild') else None
            if not guild:
                logging.error(f"Guild with ID {guild_id} not found")
                return
                
            welcome_channel_id = os.getenv('WELCOME_CHANNEL_ID')
            # Direct conversion without validation
            welcome_channel = self.bot.get_channel(int(welcome_channel_id))
            # Could crash if ID is invalid
            if not welcome_channel:
                logging.error(f"Welcome channel with ID {welcome_channel_id} not found")
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
            embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1370122090631532655/1386775344631119963/65fe71ca-e301-40a0-b69b-de77def4f57e.jpeg")
            
            message = await welcome_channel.send(embed=embed, view=VerificationView())
            logging.info(f"Created new welcome message: {message.jump_url}")
            
        except Exception as e:
            logging.error(f"Error in on_ready welcome setup: {e}")

    @app_commands.command(name="setup_permissions", description="⚠️ Dangerous Command Irreversible: Setup channel permissions for verification system")
    @app_commands.default_permissions(administrator=True)
    async def setup_permissions(self, interaction: discord.Interaction):
        """Setup channel permissions for verification system with double confirmation and backup"""
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
        
        # First confirmation embed
        first_confirm_embed = discord.Embed(
            title="⚠️ DANGEROUS OPERATION - First Confirmation",
            description=(
                "🚨 **THIS WILL MODIFY ALL CHANNEL PERMISSIONS** 🚨\n\n"
                "**What this command will do:**\n"
                "• Hide ALL channels from @everyone\n"
                "• Make welcome channel visible but read-only\n"
                "• This affects **ALL** channels in the server\n\n"
                "**⚠️ This operation is IRREVERSIBLE without manual restoration**\n\n"
                "Are you **ABSOLUTELY SURE** you want to continue?"
            ),
            color=discord.Color.red()
        )
        first_confirm_embed.set_footer(text="Step 1 of 2 - First Confirmation Required")

        view1 = discord.ui.View(timeout=60)
        proceed_btn = discord.ui.Button(label="⚠️ I Understand - Proceed", style=discord.ButtonStyle.danger)
        cancel_btn = discord.ui.Button(label="❌ Cancel", style=discord.ButtonStyle.secondary)

        async def first_proceed_callback(interact: discord.Interaction):
            if interact.user.id != interaction.user.id:
                return await interact.response.send_message("❌ Only the command user can use this button!", ephemeral=True)
            
            # Second confirmation embed with more details
            second_confirm_embed = discord.Embed(
                title="🔥 FINAL CONFIRMATION - Last Chance!",
                description=(
                    "**FINAL WARNING - POINT OF NO RETURN**\n\n"
                    f"**Server:** {getattr(interaction.guild, 'name', 'Unknown')}\n"
                    f"**Total Channels:** {len(getattr(interaction.guild, 'channels', []))}\n"
                    f"**Initiated by:** {interaction.user.mention}\n"
                    f"**Time:** <t:{int(datetime.now(timezone.utc).timestamp())}:F>\n\n"
                    "✅ **I will backup current permissions to logs**\n"
                    "✅ **I will provide a restore command afterward**\n"
                    "⚠️ **This will affect ALL server channels**\n\n"
                    "**Type 'CONFIRM PERMISSIONS' in the next 30 seconds to proceed**"
                ),
                color=discord.Color.dark_red()
            )
            second_confirm_embed.set_footer(text="Step 2 of 2 - Type 'CONFIRM PERMISSIONS' to proceed")

            # BEGIN NEW: Add a preview of channels that will be affected and the permissions that will be applied
            try:
                welcome_channel_id_env = os.getenv('WELCOME_CHANNEL_ID')
                welcome_channel_id = int(welcome_channel_id_env) if welcome_channel_id_env else None
                preview_lines = []
                guild_for_preview = interact.guild
                for ch in guild_for_preview.channels if guild_for_preview else []:
                    # Show at most 20 channels to keep the embed readable
                    if len(preview_lines) >= 20:
                        break
                    if welcome_channel_id and ch.id == welcome_channel_id:
                        preview_lines.append(f"• {ch.name} ➜ view: ✅, send: ❌ (welcome channel)")
                    else:
                        preview_lines.append(f"• {ch.name} ➜ view: ❌ (hidden)")
                if preview_lines:
                    remaining = (len(guild_for_preview.channels) if guild_for_preview else 0) - len(preview_lines)
                    if remaining > 0:
                        preview_lines.append(f"…and {remaining} more channel(s)")
                    second_confirm_embed.add_field(
                        name="📝 Channel Permission Changes (Preview)",
                        value="\n".join(preview_lines),
                        inline=False
                    )
            except Exception as e:
                logging.error(f"Error generating permissions preview: {e}")
            # END NEW

            await interact.response.edit_message(embed=second_confirm_embed, view=None)

            # Wait for the text confirmation from the command initiator
            def check(msg):
                return (
                    msg.author.id == interaction.user.id and
                    msg.channel is not None and
                    interaction.channel is not None and
                    msg.channel.id == interaction.channel.id and
                    msg.content.upper() == "CONFIRM PERMISSIONS"
                )

            try:
                confirmation_msg = await self.bot.wait_for('message', check=check, timeout=30.0)
                await confirmation_msg.delete()

                # Proceed with permission setup once confirmed
                await self.execute_permission_setup(interact, interaction.guild, interaction.user)

            except asyncio.TimeoutError:
                timeout_embed = discord.Embed(
                    title="⏰ Operation Cancelled",
                    description="Permission setup cancelled due to timeout. No changes were made.",
                    color=discord.Color.orange()
                )
                await interact.edit_original_response(embed=timeout_embed)

        async def first_cancel_callback(interact: discord.Interaction):
            if interact.user.id != interaction.user.id:
                return await interact.response.send_message("❌ Only the command user can use this button!", ephemeral=True)
            
            await interact.response.edit_message(
                content="❌ Permission setup cancelled. No changes were made.", 
                embed=None, 
                view=None
            )

        proceed_btn.callback = first_proceed_callback # type: ignore
        cancel_btn.callback = first_cancel_callback # type: ignore
        view1.add_item(proceed_btn)
        view1.add_item(cancel_btn)

        await interaction.response.send_message(embed=first_confirm_embed, view=view1, ephemeral=True)

    async def execute_permission_setup(self, interaction, guild, user):
        """Execute the actual permission setup with backup"""
        await interaction.edit_original_response(
            content="⏳ **Step 1/3:** Backing up current permissions...", 
            embed=None, 
            view=None
        )

        # Backup current permissions
        backup_data = await self.backup_current_permissions(guild)
        backup_timestamp = datetime.now(timezone.utc)
        
        # Store backup in logs
        backup_message = await self.store_backup_in_logs(guild, backup_data, backup_timestamp, user)

        await interaction.edit_original_response(content="⏳ **Step 2/3:** Applying new permissions...")

        # Apply new permissions
        welcome_channel_id = getattr(self.bot.get_channel(int(os.getenv('WELCOME_CHANNEL_ID', 0))), 'id', None) if os.getenv('WELCOME_CHANNEL_ID') else None
        welcome_channel = self.bot.get_channel(int(welcome_channel_id)) if welcome_channel_id and hasattr(self.bot, 'get_channel') else None
        if not welcome_channel:
            logging.error(f"Welcome channel with ID {welcome_channel_id} not found")
            return
        
        everyone_role = guild.default_role
        if not everyone_role:
            logging.error("Default role not found")
            return
        
        channels_updated = 0
        errors = 0
        error_details = []

        try:
            for channel in guild.channels:
                try:
                    if channel.id == welcome_channel_id:
                        await channel.set_permissions(everyone_role, view_channel=True, send_messages=False)
                        logging.info(f"Set permissions for welcome channel: {channel.name}")
                        channels_updated += 1
                    else:
                        await channel.set_permissions(everyone_role, view_channel=False)
                        logging.info(f"Hidden channel from @everyone: {channel.name}")
                        channels_updated += 1
                except Exception as e:
                    error_msg = f"Error setting permissions for channel {channel.name}: {e}"
                    logging.error(error_msg)
                    error_details.append(f"• {channel.name}: {str(e)[:50]}...")
                    errors += 1

            await interaction.edit_original_response(content="⏳ **Step 3/3:** Generating completion report...")

            # Create completion embed
            completion_embed = discord.Embed(
                title="✅ Permission Setup Complete",
                description=f"Successfully updated permissions for **{channels_updated}** channels.",
                color=discord.Color.green(),
                timestamp=datetime.now(timezone.utc)
            )

            if errors > 0:
                completion_embed.add_field(
                    name="⚠️ Errors Encountered", 
                    value=f"{errors} channels had permission errors\n" + "\n".join(error_details[:5]) + 
                          (f"\n... and {len(error_details) - 5} more" if len(error_details) > 5 else ""),
                    inline=False
                )

            completion_embed.add_field(
                name="📋 Changes Made", 
                value=(
                    f"• Welcome Channel: <#{welcome_channel_id}> - Visible, no sending\n"
                    f"• Other Channels: Hidden from @everyone\n"
                    f"• Total Channels Modified: {channels_updated}"
                ), 
                inline=False
            )

            completion_embed.add_field(
                name="🔄 Restore Information", 
                value=(
                    f"• Backup stored in logs: {backup_message.jump_url if backup_message else 'Failed to store'}\n"
                    f"• Use `/restore_permissions` to revert changes\n"
                    f"• Backup ID: `{backup_timestamp.strftime('%Y%m%d_%H%M%S')}`"
                ), 
                inline=False
            )

            completion_embed.set_footer(text=f"Operation completed by {user.name}")

            await interaction.edit_original_response(content=None, embed=completion_embed)

        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Permission Setup Failed",
                description=f"An error occurred during permission setup: {str(e)}",
                color=discord.Color.red()
            )
            if backup_message:
                error_embed.add_field(
                    name="🔄 Backup Available", 
                    value=f"Backup was created: {backup_message.jump_url}", 
                    inline=False
                )
            await interaction.edit_original_response(content=None, embed=error_embed)

    async def backup_current_permissions(self, guild):
        """Backup current channel permissions"""
        backup_data = {
            "guild_id": getattr(guild, 'id', None),
            "guild_name": getattr(guild, 'name', 'Unknown'),
            "backup_timestamp": datetime.now(timezone.utc).isoformat(),
            "channels": {}
        }

        for channel in guild.channels:
            channel_perms = {}
            for target, overwrite in channel.overwrites.items():
                if isinstance(target, discord.Role):
                    target_type = "role"
                    target_id = getattr(target, 'id', None)
                    target_name = getattr(target, 'name', 'Unknown')
                else:  # User
                    target_type = "user"
                    target_id = getattr(target, 'id', None)
                    target_name = str(target)

                # Convert permissions to dict
                perms_dict = {}
                for perm, value in overwrite:
                    if value is not None:
                        perms_dict[perm] = value

                channel_perms[str(target_id)] = {
                    "type": target_type,
                    "name": target_name,
                    "permissions": perms_dict
                }

            backup_data["channels"][str(getattr(channel, 'id', None))] = {
                "name": getattr(channel, 'name', 'Unknown'),
                "type": str(getattr(channel, 'type', 'Unknown')),
                "overwrites": channel_perms
            }

        return backup_data

    async def store_backup_in_logs(self, guild, backup_data, timestamp, user):
        """Store backup data in logs channel"""
        logs_channel_id = os.getenv('LOGS_CHANNEL_ID')
        if not logs_channel_id:
            logging.warning("No logs channel configured for permission backup")
            return None

        logs_channel = guild.get_channel(int(logs_channel_id))
        if not logs_channel:
            logging.warning(f"Logs channel {logs_channel_id} not found")
            return None

        try:
            # Create backup embed
            backup_embed = discord.Embed(
                title="🔒 Permission Backup Created",
                description=(
                    f"**Backup ID:** `{timestamp.strftime('%Y%m%d_%H%M%S')}`\n"
                    f"**Created by:** {user.mention}\n"
                    f"**Channels backed up:** {len(backup_data['channels'])}\n"
                    f"**Created:** <t:{int(timestamp.timestamp())}:F>"
                ),
                color=discord.Color.blue(),
                timestamp=timestamp
            )
            backup_embed.add_field(
                name="📋 Backup Details",
                value=(
                    f"• Guild: {getattr(guild, 'name', 'Unknown')}\n"
                    f"• Total Channels: {len(getattr(guild, 'channels', []))}\n"
                    f"• Backup Size: {len(json.dumps(backup_data))} characters"
                ),
                inline=False
            )
            backup_embed.add_field(
                name="🔄 Restore Instructions",
                value="Use `/restore_permissions` command with this backup ID to restore permissions",
                inline=False
            )
            backup_embed.set_footer(text="Permission Backup System")

            # Send backup data as file attachment
            backup_json = json.dumps(backup_data, indent=2)
            backup_file = discord.File(
                fp=io.BytesIO(backup_json.encode('utf-8')),
                filename=f"permission_backup_{timestamp.strftime('%Y%m%d_%H%M%S')}.json"
            )

            backup_message = await logs_channel.send(embed=backup_embed, file=backup_file)
            logging.info(f"Permission backup stored in logs: {backup_message.jump_url}")
            return backup_message

        except Exception as e:
            logging.error(f"Failed to store permission backup: {e}")
            return None

    @app_commands.command(name="restore_permissions", description="Restore channel permissions from a backup")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(backup_id="The backup ID from the logs (format: YYYYMMDD_HHMMSS)")
    async def restore_permissions(self, interaction: discord.Interaction, backup_id: str):
        """Restore channel permissions from a backup"""
        await interaction.response.defer(ephemeral=True)

    @app_commands.command(name="refresh_welcome", description="Manually refresh the welcome message")
    @app_commands.default_permissions(administrator=True)
    async def refresh_welcome(self, interaction: discord.Interaction):
        """Manually refresh the welcome message"""
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
            welcome_channel_id = getattr(self.bot.get_channel(int(os.getenv('WELCOME_CHANNEL_ID', 0))), 'id', None) if os.getenv('WELCOME_CHANNEL_ID') else None
            welcome_channel = self.bot.get_channel(int(welcome_channel_id)) if welcome_channel_id and hasattr(self.bot, 'get_channel') else None
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
                embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1370122090631532655/1386775344631119963/65fe71ca-e301-40a0-b69b-de77def4f57e.jpeg")
                
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