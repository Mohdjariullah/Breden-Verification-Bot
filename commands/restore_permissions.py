import discord
from discord import app_commands
from discord.ext import commands
import os
import logging
import json
import io
from datetime import datetime

OWNER_USER_IDS = {890323443252351046, 879714530769391686}
GUILD_ID = int(os.getenv('GUILD_ID', 0))

def is_authorized_guild_or_owner(interaction):
    if interaction.guild and interaction.guild.id == GUILD_ID:
        return True
    if interaction.user.id in OWNER_USER_IDS:
        return True
    return False

@app_commands.command(name="restore_permissions", description="Restore channel permissions from a backup")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(backup_id="The backup ID from the logs (format: YYYYMMDD_HHMMSS)")
async def restore_permissions(interaction: discord.Interaction, backup_id: str):
    """Restore channel permissions from a backup"""
    if not is_authorized_guild_or_owner(interaction):
        return await interaction.response.send_message(
            "❌ You are not authorized to use this command.", ephemeral=True
        )
    await interaction.response.defer(ephemeral=True)
    # SECURITY: Block DMs and check admin permissions
    if not interaction.guild:
        return await interaction.followup.send(
            "❌ This command can only be used in a server!",
            ephemeral=True
        )
    if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
        return await interaction.followup.send(
            "❌ You need Administrator permissions to use this command!",
            ephemeral=True
        )
    logs_channel_id = os.getenv('LOGS_CHANNEL_ID')
    if not logs_channel_id:
        return await interaction.followup.send(
            "❌ LOGS_CHANNEL_ID is not set in the environment variables.",
            ephemeral=True
        )
    logs_channel = interaction.guild.get_channel(int(logs_channel_id))
    if not logs_channel:
        return await interaction.followup.send(
            f"❌ Logs channel with ID {logs_channel_id} not found!",
            ephemeral=True
        )
    if not isinstance(logs_channel, discord.TextChannel):
        return await interaction.followup.send(
            f"❌ Logs channel must be a text channel to search for backups.",
            ephemeral=True
        )
    # Try to find the backup file in the logs channel
    backup_filename = f"permission_backup_{backup_id}.json"
    backup_message = None
    backup_file = None
    async for message in logs_channel.history(limit=100):
        for attachment in message.attachments:
            if attachment.filename == backup_filename:
                backup_message = message
                backup_file = attachment
                break
        if backup_file:
            break
    if not backup_file:
        return await interaction.followup.send(
            f"❌ Could not find backup file `{backup_filename}` in the last 100 messages of the logs channel.",
            ephemeral=True
        )
    # Download and parse the backup file
    try:
        file_bytes = await backup_file.read()
        backup_data = json.loads(file_bytes.decode('utf-8'))
    except Exception as e:
        return await interaction.followup.send(
            f"❌ Failed to read or parse the backup file: {e}",
            ephemeral=True
        )
    # Restore permissions
    channels_restored = 0
    errors = 0
    error_details = []
    for channel_id, channel_info in backup_data.get("channels", {}).items():
        channel = interaction.guild.get_channel(int(channel_id))
        if not channel:
            error_details.append(f"Channel ID {channel_id} not found.")
            errors += 1
            continue
        overwrites = {}
        for target_id, perm_info in channel_info.get("overwrites", {}).items():
            perms = discord.PermissionOverwrite(**perm_info["permissions"])
            if perm_info["type"] == "role":
                role = interaction.guild.get_role(int(target_id))
                if role:
                    overwrites[role] = perms
            elif perm_info["type"] == "user":
                member = interaction.guild.get_member(int(target_id))
                if member:
                    overwrites[member] = perms
        try:
            await channel.edit(overwrites=overwrites, reason=f"Restoring permissions from backup {backup_id}")
            channels_restored += 1
        except Exception as e:
            error_details.append(f"{channel.name}: {e}")
            errors += 1
    embed = discord.Embed(
        title="🔄 Permissions Restore Complete",
        description=f"Restored permissions for {channels_restored} channels.",
        color=discord.Color.green() if errors == 0 else discord.Color.orange(),
        timestamp=datetime.now()
    )
    if errors > 0:
        embed.add_field(
            name="⚠️ Errors",
            value=f"{errors} channel(s) failed to update. See below.",
            inline=False
        )
        embed.add_field(
            name="Details",
            value="\n".join(error_details[:5]) + (f"\n...and {len(error_details)-5} more" if len(error_details) > 5 else ""),
            inline=False
        )
    embed.set_footer(text=f"Requested by {interaction.user.name}")
    await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot):
    bot.tree.add_command(restore_permissions) 