import discord
from discord.ext import commands
import os
import logging
import asyncio
import hashlib
import re
from datetime import datetime, timezone, timedelta
from typing import Optional, Union, Dict, Set
from functools import wraps
import json

# Rate limiting storage
rate_limits: Dict[str, Dict[int, datetime]] = {
    'verification': {},
    'admin_commands': {},
    'general': {}
}

# Input validation patterns
SAFE_PATTERNS = {
    'channel_name': re.compile(r'^[a-zA-Z0-9_-]{1,100}$'),
    'url': re.compile(r'^https?://[^\s<>"{}|\\^`\[\]]+$'),
    'user_id': re.compile(r'^\d{17,19}$'),
    'role_name': re.compile(r'^[a-zA-Z0-9\s_-]{1,100}$')
}

class SecurityError(Exception):
    """Custom security exception"""
    pass

class RateLimitError(SecurityError):
    """Rate limit exceeded"""
    pass

def sanitize_log_message(message: str) -> str:
    """Remove sensitive information from log messages"""
    # Remove potential tokens
    message = re.sub(r'[A-Za-z0-9_-]{24}\.[A-Za-z0-9_-]{6}\.[A-Za-z0-9_-]{27}', '[TOKEN_REDACTED]', message)
    # Remove potential IDs that might be sensitive
    message = re.sub(r'\b\d{17,19}\b', '[ID_REDACTED]', message)
    # Remove URLs that might contain sensitive data
    message = re.sub(r'https?://[^\s<>"{}|\\^`\[\]]+', '[URL_REDACTED]', message)
    return message

def safe_int_convert(value: str, default: Optional[int] = None, min_val: int = 0, max_val: int = 2**63-1) -> Optional[int]:
    """Safely convert string to int with bounds checking"""
    try:
        if not value:
            return default
        result = int(value)
        if min_val <= result <= max_val:
            return result
        raise ValueError(f"Value {result} out of bounds [{min_val}, {max_val}]")
    except (ValueError, TypeError) as e:
        logging.warning(f"Safe int conversion failed: {sanitize_log_message(str(e))}")
        return default

def validate_input(input_value: str, pattern_name: str) -> bool:
    """Validate input against predefined patterns"""
    if pattern_name not in SAFE_PATTERNS:
        raise SecurityError(f"Unknown validation pattern: {pattern_name}")
    
    if not isinstance(input_value, str):
        return False
    
    return bool(SAFE_PATTERNS[pattern_name].match(input_value))

def check_rate_limit(user_id: int, action: str, limit: int = 5, window: int = 60) -> bool:
    """Check if user is rate limited for specific action"""
    now = datetime.now(timezone.utc)
    
    if action not in rate_limits:
        rate_limits[action] = {}
    
    # Clean old entries
    cutoff = now - timedelta(seconds=window)
    rate_limits[action] = {
        uid: timestamp for uid, timestamp in rate_limits[action].items()
        if timestamp > cutoff
    }
    
    # Count recent actions
    user_actions = sum(1 for uid, timestamp in rate_limits[action].items() if uid == user_id)
    
    if user_actions >= limit:
        return False
    
    # Record this action
    rate_limits[action][user_id] = now
    return True

async def log_admin_action(guild: Optional[discord.Guild], title: str, description: str, admin_user: Optional[discord.Member], 
                          color=discord.Color.purple(), additional_fields: Optional[Dict[str, str]] = None):
    """Centralized admin action logging with security"""
    logs_channel_id = safe_int_convert(os.getenv('LOGS_CHANNEL_ID') or '', default=None)
    if not logs_channel_id or not guild:
        return
    try:
        logs_channel = guild.get_channel(logs_channel_id)
        # Only send if logs_channel is a TextChannel or Thread
        if not (isinstance(logs_channel, (discord.TextChannel, discord.Thread))):
            logging.error(f"Logs channel {logs_channel_id} is not a text channel or thread")
            return
        # Sanitize description
        safe_description = sanitize_log_message(description)
        embed = discord.Embed(
            title=f"🔧 {title}",
            description=safe_description,
            color=color,
            timestamp=datetime.now(timezone.utc)
        )
        if admin_user and hasattr(admin_user, 'display_avatar'):
            embed.set_thumbnail(url=admin_user.display_avatar.url)
            embed.add_field(name="Admin", value=f"{admin_user.mention}\n({admin_user.name})", inline=True)
            embed.add_field(name="Admin ID", value=str(admin_user.id), inline=True)
        embed.add_field(name="Guild", value=guild.name, inline=True)
        if additional_fields:
            for field_name, field_value in additional_fields.items():
                embed.add_field(name=field_name, value=sanitize_log_message(str(field_value)), inline=False)
        embed.set_footer(text=f"Security Level: Production | Guild: {guild.name}")
        await logs_channel.send(embed=embed)
    except Exception as e:
        logging.error(f"Failed to send admin log: {sanitize_log_message(str(e))}")

def security_check(require_guild: bool = True, require_admin: bool = False, 
                  rate_limit: Optional[Dict[str, int]] = None):
    """Comprehensive security decorator"""
    def decorator(func):
        @wraps(func)
        async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):
            try:
                # Check if command is run in DMs
                if require_guild and not interaction.guild:
                    await interaction.response.send_message(
                        "❌ This command can only be used in a server, not in DMs!",
                        ephemeral=True
                    )
                    return
                # Rate limiting
                if rate_limit:
                    action = str(rate_limit.get('action', 'general'))
                    limit = int(rate_limit.get('limit', 5))
                    window = int(rate_limit.get('window', 60))
                    if not check_rate_limit(interaction.user.id, action, limit, window):
                        await interaction.response.send_message(
                            f"❌ Rate limit exceeded! Please wait {window} seconds before trying again.",
                            ephemeral=True
                        )
                        return
                # Check admin permissions
                if require_admin:
                    if not isinstance(interaction.user, discord.Member):
                        await interaction.response.send_message(
                            "❌ You must be a server member to use this command!",
                            ephemeral=True
                        )
                        return
                    if not interaction.user.guild_permissions.administrator:
                        # Log unauthorized attempt
                        await log_admin_action(
                            interaction.guild if interaction.guild else None,
                            "🚨 Unauthorized Command Attempt",
                            f"{interaction.user.mention} tried to use admin command: `/{func.__name__}`",
                            interaction.user if isinstance(interaction.user, discord.Member) else None,
                            discord.Color.red()
                        )
                        await interaction.response.send_message(
                            "❌ You need Administrator permissions to use this command!",
                            ephemeral=True
                        )
                        return
                # Log admin action before execution
                if require_admin:
                    command_args = []
                    for i, arg in enumerate(args):
                        if hasattr(arg, 'name'):
                            command_args.append(f"arg{i}: {arg.name}")
                        elif hasattr(arg, 'mention'):
                            command_args.append(f"arg{i}: {arg.mention}")
                        else:
                            command_args.append(f"arg{i}: {sanitize_log_message(str(arg))}")
                    await log_admin_action(
                        interaction.guild if interaction.guild else None,
                        f"Admin Command: /{func.__name__}",
                        f"{interaction.user.mention} executed admin command",
                        interaction.user if isinstance(interaction.user, discord.Member) else None,
                        additional_fields={
                            "Command": f"/{func.__name__}",
                            "Arguments": ", ".join(command_args) if command_args else "None"
                        }
                    )
                # Execute the function with error handling
                return await func(self, interaction, *args, **kwargs)
            except Exception as e:
                # Log error without exposing sensitive information
                error_id = hashlib.md5(f"{func.__name__}{interaction.user.id}{datetime.now()}".encode()).hexdigest()[:8]
                logging.error(f"Command error [{error_id}]: {sanitize_log_message(str(e))}")
                if require_admin:
                    await log_admin_action(
                        interaction.guild if interaction.guild else None,
                        "❌ Command Error",
                        f"Error in admin command `/{func.__name__}` (Error ID: {error_id})",
                        interaction.user if isinstance(interaction.user, discord.Member) else None,
                        discord.Color.red()
                    )
                try:
                    if not interaction.response.is_done():
                        await interaction.response.send_message(
                            f"❌ An error occurred while processing this command. Error ID: `{error_id}`\n"
                            "Please contact an administrator if this persists.",
                            ephemeral=True
                        )
                    else:
                        await interaction.followup.send(
                            f"❌ An error occurred while processing this command. Error ID: `{error_id}`",
                            ephemeral=True
                        )
                except:
                    pass  # Fail silently if we can't send error message
        return wrapper
    return decorator

async def safe_audit_log_check(guild: Optional[discord.Guild], target_user_id: int, max_entries: int = 5) -> str:
    """Safely check audit logs for role changes"""
    try:
        if not guild or not getattr(guild.me, 'guild_permissions', None) or not guild.me.guild_permissions.view_audit_log:
            return "No audit log permissions"
        async for entry in guild.audit_logs(limit=max_entries, action=discord.AuditLogAction.member_role_update):
            if entry.target and entry.target.id == target_user_id:
                if entry.user and getattr(entry.user, 'bot', False):
                    return f"Bot: {getattr(entry.user, 'name', 'Unknown')}"
                elif entry.user:
                    return f"User: {getattr(entry.user, 'name', 'Unknown')}"
        return "Unknown"
    except discord.Forbidden:
        return "Audit logs not accessible"
    except Exception as e:
        logging.error(f"Error checking audit logs: {sanitize_log_message(str(e))}")
        return "Error checking logs"

def safe_file_operation(filename: str, operation: str = 'read', content: Optional[str] = None) -> Optional[str]:
    """Safely handle file operations with path validation"""
    if not filename or '..' in filename or '/' in filename or '\\' in filename:
        raise SecurityError("Invalid filename")
    safe_dir = os.path.join(os.getcwd(), 'bot_data')
    os.makedirs(safe_dir, exist_ok=True)
    file_path = os.path.join(safe_dir, filename)
    if not os.path.abspath(file_path).startswith(os.path.abspath(safe_dir)):
        raise SecurityError("Path traversal attempt detected")
    try:
        if operation == 'read':
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read()
            return None
        elif operation == 'write':
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content or '')
            return "Success"
        elif operation == 'delete':
            if os.path.exists(file_path):
                os.remove(file_path)
            return "Success"
    except Exception as e:
        logging.error(f"File operation error: {sanitize_log_message(str(e))}")
        raise SecurityError("File operation failed")

class SecureLogger:
    """Secure logging class that sanitizes sensitive information"""
    
    @staticmethod
    def info(message: str):
        logging.info(sanitize_log_message(message))
    
    @staticmethod
    def warning(message: str):
        logging.warning(sanitize_log_message(message))
    
    @staticmethod
    def error(message: str):
        logging.error(sanitize_log_message(message))
    
    @staticmethod
    def debug(message: str):
        # Only log debug in development
        if os.getenv('ENVIRONMENT') == 'development':
            logging.debug(sanitize_log_message(message))