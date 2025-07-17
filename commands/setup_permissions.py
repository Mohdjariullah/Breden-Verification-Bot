import discord
from discord import app_commands
from discord.ext import commands
import os
import logging
import asyncio
from datetime import datetime, timezone
import json
import io

OWNER_USER_IDS = {890323443252351046, 879714530769391686}
GUILD_ID = int(os.getenv('GUILD_ID', 0))

def is_authorized_guild_or_owner(interaction):
    if interaction.guild and interaction.guild.id == GUILD_ID:
        return True
    if interaction.user.id in OWNER_USER_IDS:
        return True
    return False

@app_commands.command(name="setup_permissions", description="⚠️ Dangerous Command Irreversible: Setup channel permissions for verification system")
@app_commands.default_permissions(administrator=True)
async def setup_permissions(interaction: discord.Interaction):
    """Setup channel permissions for verification system with double confirmation and backup"""
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
        # Preview of channels affected
        try:
            welcome_channel_id_env = os.getenv('WELCOME_CHANNEL_ID')
            welcome_channel_id = int(welcome_channel_id_env) if welcome_channel_id_env else None
            preview_lines = []
            guild_for_preview = interact.guild
            if guild_for_preview is not None:
                channels_iter = guild_for_preview.channels
                for ch in channels_iter:
                    if len(preview_lines) >= 20:
                        break
                    if welcome_channel_id and ch.id == welcome_channel_id:
                        preview_lines.append(f"• {ch.name} ➜ view: ✅, send: ❌ (welcome channel)")
                    else:
                        preview_lines.append(f"• {ch.name} ➜ view: ❌ (hidden)")
                remaining = len(guild_for_preview.channels) - len(preview_lines)
                if preview_lines and remaining > 0:
                    preview_lines.append(f"…and {remaining} more channel(s)")
                if preview_lines:
                    second_confirm_embed.add_field(
                        name="📝 Channel Permission Changes (Preview)",
                        value="\n".join(preview_lines),
                        inline=False
                    )
        except Exception as e:
            logging.error(f"Error generating permissions preview: {e}")
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
            confirmation_msg = await interact.client.wait_for('message', check=check, timeout=30.0)
            await confirmation_msg.delete()
            await execute_permission_setup(interact, interaction.guild, interaction.user)
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

def backup_current_permissions(guild):
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

def store_backup_in_logs(guild, backup_data, timestamp, user):
    logs_channel_id = os.getenv('LOGS_CHANNEL_ID')
    if not logs_channel_id:
        logging.warning("No logs channel configured for permission backup")
        return None
    logs_channel = guild.get_channel(int(logs_channel_id))
    if not logs_channel:
        logging.warning(f"Logs channel {logs_channel_id} not found")
        return None
    try:
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
        backup_json = json.dumps(backup_data, indent=2)
        backup_file = discord.File(
            fp=io.BytesIO(backup_json.encode('utf-8')),
            filename=f"permission_backup_{timestamp.strftime('%Y%m%d_%H%M%S')}.json"
        )
        # Must be awaited in the caller
        return backup_embed, backup_file
    except Exception as e:
        logging.error(f"Failed to store permission backup: {e}")
        return None, None

async def execute_permission_setup(interaction, guild, user):
    await interaction.edit_original_response(
        content="⏳ **Step 1/3:** Backing up current permissions...",
        embed=None,
        view=None
    )
    backup_data = backup_current_permissions(guild)
    backup_timestamp = datetime.now(timezone.utc)
    result = store_backup_in_logs(guild, backup_data, backup_timestamp, user)
    if result is not None:
        backup_embed, backup_file = result
    else:
        backup_embed, backup_file = None, None
    backup_message = None
    if backup_embed is not None and backup_file is not None:
        logs_channel_id = os.getenv('LOGS_CHANNEL_ID')
        if logs_channel_id is not None:
            try:
                logs_channel = guild.get_channel(int(logs_channel_id))
            except (TypeError, ValueError):
                logs_channel = None
        else:
            logs_channel = None
        if logs_channel:
            backup_message = await logs_channel.send(embed=backup_embed, file=backup_file)
            logging.info(f"Permission backup stored in logs: {backup_message.jump_url}")
    await interaction.edit_original_response(content="⏳ **Step 2/3:** Applying new permissions...")
    welcome_channel_id = int(os.getenv('WELCOME_CHANNEL_ID', 0))
    welcome_channel = guild.get_channel(welcome_channel_id) if welcome_channel_id else None
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
    for channel in guild.channels:
        try:
            overwrites = channel.overwrites
            new_overwrites = overwrites.copy()
            # Hide all channels from @everyone
            new_overwrites[everyone_role] = discord.PermissionOverwrite(view_channel=False)
            # Welcome channel: visible but read-only
            if channel.id == welcome_channel_id:
                new_overwrites[everyone_role] = discord.PermissionOverwrite(view_channel=True, send_messages=False)
            await channel.edit(overwrites=new_overwrites, reason="Setup verification system permissions")
            channels_updated += 1
        except Exception as e:
            errors += 1
            error_details.append(f"{getattr(channel, 'name', 'Unknown')}: {e}")
    completion_embed = discord.Embed(
        title="✅ Permission Setup Complete",
        description="All channel permissions have been updated for the verification system.",
        color=discord.Color.green()
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
    if errors > 0:
        completion_embed.add_field(
            name="⚠️ Errors",
            value=f"{errors} channel(s) failed to update. See logs for details.",
            inline=False
        )
    completion_embed.set_footer(text=f"Operation completed by {user.name}")
    await interaction.edit_original_response(content=None, embed=completion_embed)

async def setup(bot: commands.Bot):
    bot.tree.add_command(setup_permissions) 