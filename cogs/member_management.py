import discord
from discord.ext import commands
from discord import app_commands
import logging
import os
import asyncio
from typing import Dict, List, Set, Optional, Any
from datetime import datetime, timezone
from .security_utils import (
    security_check, log_admin_action, safe_int_convert, 
    validate_input, check_rate_limit, safe_audit_log_check,
    SecureLogger, sanitize_log_message
)
from .bypass_manager import bypass_manager
import json
import io
import json as pyjson

UNVERIFIED_ROLE_ID = int(os.getenv('UNVERIFIED_ROLE_ID', 0))
WELCOME_CHANNEL_ID = int(os.getenv('WELCOME_CHANNEL_ID', 0))
UNVERIFIED_FILE = 'unverified_users.json'
PERIODIC_CHECK_INTERVAL = int(os.getenv('PERIODIC_CHECK_INTERVAL', 120))

def get_env_role_id(var_name: str) -> int:
    env_value = os.getenv(var_name)
    if env_value is None:
        raise ValueError(f"Environment variable '{var_name}' is not set")
    val = safe_int_convert(env_value, min_val=1, max_val=2**63-1)
    if val is None:
        raise ValueError(f"Environment variable '{var_name}' is not a valid int")
    return val

def load_unverified() -> dict:
    try:
        with open(UNVERIFIED_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return {}

def save_unverified(data: dict) -> None:
    with open(UNVERIFIED_FILE, 'w') as f:
        json.dump(data, f, indent=2)

class MemberManagement(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.member_original_roles: Dict[int, List[int]] = {}
        self.users_awaiting_verification: Set[int] = set()
        self.users_being_verified: Set[int] = set()
        self.failed_verification_logged: Dict[int, bool] = {}
        self.total_verified: int = 0
        self._role_lock = asyncio.Lock()
        self.user_ticket_channels: Dict[int, int] = {}
        self.users_started_verification: Set[int] = set()
        self.verification_logged: Set[int] = set()
        SecureLogger.info("MemberManagement cog initialized with production security and bypass system")
        self.unverified_users = load_unverified()

    def cleanup_user(self, user_id: int) -> None:
        """Remove a user from all tracking structures and persistent storage."""
        self.member_original_roles.pop(user_id, None)
        self.users_awaiting_verification.discard(user_id)
        self.users_being_verified.discard(user_id)
        self.user_ticket_channels.pop(user_id, None)
        self.unverified_users.pop(str(user_id), None)
        save_unverified(self.unverified_users)
        logging.info(f"[MemberManagement] User {user_id} removed from all tracking.")

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Called when the cog is ready."""
        SecureLogger.info("MemberManagement cog is ready!")
        await self.cog_load()
        self.start_periodic_unverified_check()

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        """Handle new member joins - Remove all roles except @everyone and Unverified, store for restoration, and log."""
        async with self._role_lock:
            try:
                SecureLogger.info(f"Member {member.name} joined server {member.guild.name}")
                # Send welcome DM (embed)
                try:
                    embed = discord.Embed(
                        title="👋 Welcome to the Server!",
                        description=(
                            "To access your subscription and the community, please complete the verification process.\n\n"
                            "Click the button below to start verifying!\n\n"
                            "We're excited to have you with us!"
                        ),
                        color=0x5865F2
                    )
                    embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1370122090631532655/1386775344631119963/65fe71ca-e301-40a0-b69b-de77def4f57e.jpeg")
                    embed.set_footer(text="Join our community today!")
                    # Try to add a button to the welcome channel if possible
                    welcome_channel_id = os.getenv('WELCOME_CHANNEL_ID')
                    if welcome_channel_id:
                        welcome_channel = member.guild.get_channel(int(welcome_channel_id))
                        if welcome_channel:
                            view = discord.ui.View()
                            view.add_item(discord.ui.Button(
                                label="Go to Verification",
                                style=discord.ButtonStyle.link,
                                url=welcome_channel.jump_url
                            ))
                            await member.send(embed=embed, view=view)
                        else:
                            await member.send(embed=embed)
                    else:
                        await member.send(embed=embed)
                except Exception as e:
                    logging.warning(f"Could not send welcome DM to {member.name}: {e}")
                unverified_role = member.guild.get_role(UNVERIFIED_ROLE_ID)
                if unverified_role and unverified_role not in member.roles:
                    try:
                        await member.add_roles(unverified_role, reason="User joined, pending verification")
                    except Exception as e:
                        logging.warning(f"Could not add Unverified role to {member.name}: {e}")
                if bypass_manager.has_bypass_role(member):
                    # Grant Member role to VIP/bypass users
                    member_role_id = get_env_role_id('MEMBER_ROLE_ID')
                    member_role = member.guild.get_role(member_role_id) if member_role_id else None
                    if member_role and member_role not in member.roles:
                        try:
                            await member.add_roles(member_role, reason="Bypass user - granting Member role")
                        except Exception as e:
                            logging.warning(f"Could not add Member role to bypass user {member.name}: {e}")
                    bypass_role_names = bypass_manager.get_bypass_role_names(member.guild)
                    await self.log_member_event(
                        member.guild,
                        "🎯 Verification Bypassed",
                        f"{member.mention} joined with bypass roles: {', '.join(bypass_role_names)} - no verification required",
                        member,
                        discord.Color.gold()
                    )
                    logging.info(f"User {member.name} bypassed verification with roles: {bypass_role_names}")
                    return
                roles_to_remove = [role for role in member.roles if role != member.guild.default_role and (not unverified_role or role != unverified_role)]
                if roles_to_remove:
                    if member.id not in self.member_original_roles or not self.member_original_roles[member.id]:
                        self.member_original_roles[member.id] = [role.id for role in roles_to_remove]
                    self.users_awaiting_verification.add(member.id)
                    await member.remove_roles(*[r for r in roles_to_remove if r is not None], reason="Verification required - all roles removed for onboarding")
                    await self.log_member_event(
                        member.guild,
                        "🛑 All Roles Removed for Verification",
                        f"Removed roles from {member.mention} for verification.\nRoles removed: {', '.join([role.name for role in roles_to_remove])}",
                        member,
                        discord.Color.orange(),
                        roles_to_remove
                    )
                else:
                    if member.id not in self.member_original_roles or not self.member_original_roles[member.id]:
                        member_role_id = get_env_role_id('MEMBER_ROLE_ID')
                        member_role = member.guild.get_role(member_role_id) if member_role_id else None
                        self.member_original_roles[member.id] = [member_role_id] if member_role_id else []
                    self.users_awaiting_verification.add(member.id)
                    await self.log_member_event(
                        member.guild,
                        "👋 User Joined - No Roles to Remove",
                        f"{member.mention} joined with no roles to remove. Will be granted Member role after verification.",
                        member,
                        discord.Color.blue(),
                        [member.guild.get_role(rid) for rid in self.member_original_roles[member.id] if member.guild.get_role(rid)] if self.member_original_roles[member.id] else None
                    )
                self.unverified_users[str(member.id)] = {
                    'original_roles': self.member_original_roles[member.id]
                }
                save_unverified(self.unverified_users)
            except Exception as e:
                logging.error(f"Error in on_member_join for {member.name}: {e}")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        """Handle member leaves - stop monitoring and log if they had subscription roles. Also delete their ticket if open."""
        async with self._role_lock:
            try:
                guild_id = member.guild.id if getattr(member, 'guild', None) is not None else 'unknown'
                logging.info(f"[MemberManagement] Member {member.name} ({member.id}) left server {guild_id}")
                ticket_channel_id = self.user_ticket_channels.get(member.id)
                if ticket_channel_id:
                    ticket_channel = member.guild.get_channel(ticket_channel_id) if member.guild else None
                    if ticket_channel:
                        try:
                            await ticket_channel.delete(reason="User left during verification")
                            if member.guild:
                                await self.log_member_event(
                                    member.guild,
                                    "🗑️ Verification Ticket Deleted",
                                    f"{member.mention}'s verification ticket was deleted because they left the server.",
                                    member,
                                    discord.Color.red(),
                                    None
                                )
                        except Exception as e:
                            logging.error(f"Failed to delete ticket for {member.name}: {e}")
                    self.unregister_ticket(member.id)
                self.cleanup_user(member.id)
                if member.guild:
                    await self.log_member_event(
                        member.guild,
                        "👋 User Left",
                        f"{member.mention} left the server. All tracking data cleaned up.",
                        member,
                        discord.Color.orange(),
                        None
                    )
            except Exception as e:
                logging.error(f"Error in on_member_remove for {member.name}: {e}")

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member) -> None:
        """Monitor role changes and prevent OTHER BOTS from re-adding roles to unverified users."""
        try:
            if after.id not in self.users_awaiting_verification:
                return
            if after.id in self.users_being_verified:
                return
            try:
                async for entry in after.guild.audit_logs(limit=1, action=discord.AuditLogAction.member_role_update):
                    if entry.target and entry.target.id == after.id:
                        if entry.user is not None and self.bot.user is not None and entry.user.id == self.bot.user.id:
                            return
                        break
            except Exception:
                pass
            subscription_roles = {
                get_env_role_id('LAUNCHPAD_ROLE_ID'),
                get_env_role_id('MEMBER_ROLE_ID')
            }
            before_role_ids = {role.id for role in before.roles}
            after_role_ids = {role.id for role in after.roles}
            added_roles = after_role_ids - before_role_ids
            added_subscription_roles = added_roles & subscription_roles
            if added_subscription_roles:
                is_admin = False
                source_info = "Unknown"
                try:
                    async for entry in after.guild.audit_logs(limit=5, action=discord.AuditLogAction.member_role_update):
                        if entry.target and entry.target.id == after.id:
                            if entry.user:
                                source_info = f"{entry.user} (ID: {entry.user.id})"
                                if isinstance(entry.user, discord.Member) and entry.user.guild_permissions.administrator:
                                    is_admin = True
                                break
                except Exception as e:
                    source_info = f"Audit log error: {e}"
                if is_admin:
                    await self.log_member_event(
                        after.guild,
                        "✅ Subscription Role Added by Admin",
                        f"Admin added roles to {after.mention} (awaiting verification). Allowing and completing verification.\nSource: {source_info}",
                        after,
                        discord.Color.green(),
                        [after.guild.get_role(role_id) for role_id in added_subscription_roles if after.guild.get_role(role_id)]
                    )
                    await self.restore_member_roles(after)
                else:
                    roles_to_remove = [after.guild.get_role(role_id) for role_id in added_subscription_roles if after.guild.get_role(role_id)]
                    if roles_to_remove:
                        await after.remove_roles(*[r for r in roles_to_remove if r is not None], reason="User awaiting verification - non-admin role assignment detected (real-time)")
                        await self.log_member_event(
                            after.guild,
                            "🛑 Removed Subscription Roles (Real-Time)",
                            f"Removed roles from {after.mention} (awaiting verification, non-admin assignment detected).\nSource: {source_info}",
                            after,
                            discord.Color.red(),
                        roles_to_remove
                    )
                        await asyncio.sleep(1)
                        refreshed_member = after.guild.get_member(after.id)
                        if refreshed_member:
                            remaining_sub_roles = [role for role in refreshed_member.roles if role.id in subscription_roles]
                            if remaining_sub_roles:
                                logging.warning(f"[DEBUG] After real-time removal, {after.name} still has subscription roles: {[role.name for role in remaining_sub_roles]}")
                            else:
                                logging.info(f"[DEBUG] After real-time removal, {after.name} has no subscription roles.")
        except Exception as e:
            logging.error(f"Error in on_member_update for {after.name}: {e}")

    async def restore_member_roles(self, member: discord.Member) -> List[discord.Role]:
        """Restore all stored roles to a member after verification and log."""
        async with self._role_lock:
            try:
                if member.id not in self.users_started_verification:
                    logging.warning(f"User {member.name} attempted verification without starting verification flow.")
                    return []
                self.users_being_verified.add(member.id)
                logging.info(f"[MemberManagement] Starting verification for {member.name} ({member.id})")
                await asyncio.sleep(1)
                restored_roles = []
                if member.id in self.member_original_roles:
                    original_role_ids = self.member_original_roles[member.id]
                    if original_role_ids:
                        roles_to_restore = []
                        for role_id in original_role_ids:
                            role = member.guild.get_role(role_id) if member.guild else None
                            if role:
                                roles_to_restore.append(role)
                            else:
                                logging.warning(f"Role with ID {role_id} not found for {member.name}")
                        # Always add Member role after verification
                        member_role_id = get_env_role_id('MEMBER_ROLE_ID')
                        member_role = member.guild.get_role(member_role_id) if member_role_id else None
                        if member_role and member_role not in roles_to_restore and member_role not in member.roles:
                            roles_to_restore.append(member_role)
                        if roles_to_restore:
                            self.users_awaiting_verification.discard(member.id)
                            await member.add_roles(*[r for r in roles_to_restore if r is not None], reason="Verification completed - restoring all original roles and Member role")
                            restored_roles = roles_to_restore
                            role_names = [role.name for role in roles_to_restore]
                            await self.log_member_event(
                                member.guild,
                                "✅ Verification Completed - Roles Restored",
                                f"{member.mention} completed verification. Restored roles: {', '.join(role_names)}",
                                member,
                                discord.Color.green(),
                                roles_to_restore
                            )
                        else:
                            logging.info(f"No valid roles to restore for {member.name}")
                            self.users_awaiting_verification.discard(member.id)
                    else:
                        # No original roles, but always add Member role
                        member_role_id = get_env_role_id('MEMBER_ROLE_ID')
                        member_role = member.guild.get_role(member_role_id) if member_role_id else None
                        if member_role and member_role not in member.roles:
                            await member.add_roles(member_role, reason="Verification completed - granting Member role")
                            restored_roles = [member_role]
                            await self.log_member_event(
                                member.guild,
                                "✅ Verification Completed - Member Role Granted",
                                f"{member.mention} completed verification. Granted Member role.",
                                member,
                                discord.Color.green(),
                                [member_role]
                            )
                        else:
                            logging.info(f"No original roles and no Member role to add for {member.name}")
                        self.users_awaiting_verification.discard(member.id)
                self.users_being_verified.discard(member.id)
                unverified_role = member.guild.get_role(UNVERIFIED_ROLE_ID)
                if unverified_role and unverified_role in member.roles:
                    try:
                        await member.remove_roles(unverified_role, reason="Verification complete")
                    except Exception as e:
                        logging.warning(f"Could not remove Unverified role from {member.name}: {e}")
                if str(member.id) in self.unverified_users:
                    del self.unverified_users[str(member.id)]
                    save_unverified(self.unverified_users)
                self.cleanup_user(member.id)
                return restored_roles
            except Exception as e:
                self.users_being_verified.discard(member.id)
                self.users_awaiting_verification.discard(member.id)
                logging.error(f"Error restoring roles for {member.name}: {e}")
                raise

    async def track_role_changes(self, before, after, added_roles, removed_roles, subscription_roles):
        """NEW: Track and log role changes with source detection"""
        try:
            # Get recent audit logs to identify who made the change
            source_info = "Unknown"
            try:
                async for entry in after.guild.audit_logs(limit=5, action=discord.AuditLogAction.member_role_update):
                    if entry.target.id == after.id:
                        if entry.user.bot:
                            source_info = f"Bot: {entry.user.name} ({entry.user.id})"
                        else:
                            source_info = f"User: {entry.user.name} ({entry.user.id})"
                        break
            except discord.Forbidden:
                source_info = "Audit logs not accessible"
            except Exception as e:
                source_info = f"Error checking audit logs: {str(e)[:50]}"
            
            # Log subscription role changes
            added_subscription = added_roles & subscription_roles
            removed_subscription = removed_roles & subscription_roles
            
            if added_subscription:
                role_names = []
                for role_id in added_subscription:
                    role = after.guild.get_role(role_id)
                    if role:
                        role_names.append(role.name)
                
                await self.log_member_event(
                    after.guild,
                    "➕ Subscription Role Added",
                    f"Subscription roles added to {after.mention}: {', '.join(role_names)}\n**Source:** {source_info}",
                    after,
                    discord.Color.green()
                )
            
            if removed_subscription:
                role_names = []
                for role_id in removed_subscription:
                    role = before.guild.get_role(role_id)
                    if role:
                        role_names.append(role.name)
                
                await self.log_member_event(
                    after.guild,
                    "➖ Subscription Role Removed",
                    f"Subscription roles removed from {after.mention}: {', '.join(role_names)}\n**Source:** {source_info}",
                    after,
                    discord.Color.orange()
                )
                
        except Exception as e:
            logging.error(f"Error in track_role_changes: {e}")

    async def _monitor_post_verification(self, member, expected_role_ids):
        """Monitor user for 2 minutes after verification to ensure roles stay"""
        try:
            monitor_seconds = 120
            print(f"⏳ Monitoring {member.name} for {monitor_seconds} seconds post-verification...")
            for _ in range(monitor_seconds // 5):  # Check every 5 seconds
                await asyncio.sleep(5)
                try:
                    # Get fresh member data
                    fresh_member = None
                    try:
                        fresh_member = await member.guild.fetch_member(member.id)
                    except discord.NotFound:
                        print(f"🛑 {member.name} is no longer in the server. Stopping monitoring.")
                        break
                    except Exception:
                        fresh_member = None
                    if not fresh_member:
                        break
                    user_role_ids = {role.id for role in fresh_member.roles}
                except Exception as e:
                    user_role_ids = {role.id for role in member.roles}
                missing = expected_role_ids - user_role_ids
                if missing:
                    print(f"⚠️ {member.name} lost roles {missing} during monitoring. Re-adding...")
                    try:
                        to_readd = [member.guild.get_role(rid) for rid in missing if member.guild.get_role(rid)]
                        if to_readd:
                            await member.add_roles(*[r for r in to_readd if r is not None], reason="Re-adding lost roles during post-verification monitoring")
                            logging.info(f"Re-added lost roles to {member.name} during monitoring")
                    except Exception as e:
                        logging.error(f"Error re-adding lost roles to {member.name} during monitoring: {e}")
                        # If user left (404 Not Found), stop monitoring to prevent spam
                        if "Unknown Member" in str(e) or "404" in str(e):
                            print(f"🛑 Stopping monitoring for {member.name} (left server)")
                            break
            print(f"✅ Monitoring complete for {member.name}")
            
        except Exception as e:
            logging.error(f"Error in post-verification monitoring for {member.name}: {e}")

    async def log_member_event(self, guild, title, description, user, color, roles=None):
        """Log member events to the logs channel"""
        logs_channel_id = os.getenv('LOGS_CHANNEL_ID')
        if logs_channel_id:
            logs_channel = guild.get_channel(int(logs_channel_id))
            if logs_channel:
                embed = discord.Embed(
                    title=title,
                    description=description,
                    color=color,
                    timestamp=datetime.now(timezone.utc)
                )
                embed.set_thumbnail(url=user.display_avatar.url)
                embed.add_field(name="User", value=f"{user.mention}\n({user.name})", inline=True)
                embed.add_field(name="User ID", value=user.id, inline=True)
                embed.add_field(name="Account Created", value=f"<t:{int(user.created_at.timestamp())}:R>", inline=True)
                
                if roles:
                    roles_text = ", ".join([role.name for role in roles]) if roles else "None"
                    embed.add_field(name="Subscription Roles", value=roles_text, inline=False)
                
                embed.set_footer(text=f"Guild: {guild.name}")
                
                try:
                    await logs_channel.send(embed=embed)
                except Exception as e:
                    logging.error(f"Failed to send log message: {e}")

    async def send_to_logs(self, guild, embed):
        """Helper function to send embeds to logs channel with safety checks"""
        if not guild:
            print("❌ No guild provided to send_to_logs")
            return
        
        logs_channel_id = os.getenv('LOGS_CHANNEL_ID')
        if logs_channel_id:
            try:
                logs_channel = guild.get_channel(int(logs_channel_id))
                if logs_channel:
                    await logs_channel.send(embed=embed)
                else:
                    print(f"❌ Logs channel not found: {logs_channel_id}")
            except Exception as e:
                print(f"❌ Failed to send to logs channel: {e}")
        else:
            print("❌ LOGS_CHANNEL_ID not set in environment variables")

    def get_pending_verification_users(self, guild: discord.Guild) -> list[discord.Member]:
        # Return a list of discord.Member objects for users who have not completed verification
        pending = []
        for user_id in self.member_original_roles:  # type: ignore
            if user_id in self.users_awaiting_verification or user_id in self.users_being_verified:  # type: ignore
                member = guild.get_member(user_id)
                if member:
                    pending.append(member)
        return pending

    async def pending_users_autocomplete(self, interaction: discord.Interaction, current: str):
        # Suggest up to 20 users pending verification, filtered by current input
        cog = self.bot.get_cog('MemberManagement')
        if not cog or not hasattr(cog, 'member_original_roles'):
            return []
        guild = interaction.guild
        if not guild:
            return []
        suggestions = []
        for user_id in list(getattr(cog, 'member_original_roles').keys()):  # type: ignore
            member = guild.get_member(user_id)
            if member and (user_id in getattr(cog, 'users_awaiting_verification') or user_id in getattr(cog, 'users_being_verified')):  # type: ignore
                if current.lower() in member.display_name.lower():
                    suggestions.append(app_commands.Choice(name=member.display_name, value=str(member.id)))
                if len(suggestions) >= 20:
                    break
        return suggestions

    # --- Ticket registration helpers ---
    def register_ticket(self, user_id: int, channel_id: int):
        self.user_ticket_channels[user_id] = channel_id

    def unregister_ticket(self, user_id: int):
        self.user_ticket_channels.pop(user_id, None)

    async def cog_load(self):
        guild_id = os.getenv('GUILD_ID')
        if not guild_id:
            return
        guild = self.bot.get_guild(int(guild_id))
        if not guild:
            return
        unverified_role = guild.get_role(UNVERIFIED_ROLE_ID)
        if not unverified_role:
            return
        for user_id in self.unverified_users:
            member = guild.get_member(int(user_id))
            if member and unverified_role not in member.roles:
                try:
                    await member.add_roles(unverified_role, reason="Restoring Unverified role after restart")
                except Exception as e:
                    logging.warning(f"Failed to re-apply Unverified role to {member}: {e}")

    def start_periodic_unverified_check(self):
        if not hasattr(self, '_periodic_check_started'):
            self._periodic_check_started = True
            self.bot.loop.create_task(self.periodic_unverified_check())

    async def periodic_unverified_check(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                guild_id = os.getenv('GUILD_ID')
                if not guild_id:
                    await asyncio.sleep(120)
                    continue
                guild = self.bot.get_guild(int(guild_id))
                if not guild:
                    await asyncio.sleep(120)
                    continue
                launchpad_role_id = get_env_role_id('LAUNCHPAD_ROLE_ID')
                member_role_id = get_env_role_id('MEMBER_ROLE_ID')
                subscription_roles = {launchpad_role_id, member_role_id}
                # Check all unverified users
                for user_id_str in list(self.unverified_users.keys()):
                    user_id = int(user_id_str)
                    member = guild.get_member(user_id)
                    if not member:
                        continue
                    user_role_ids = {role.id for role in member.roles}
                    added_roles = user_role_ids & subscription_roles
                    if added_roles:
                        # Only allow auto-verification if roles were added by admin
                        is_admin = False
                        try:
                            async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.member_role_update):
                                if entry.target and entry.target.id == member.id:
                                    if entry.user and isinstance(entry.user, discord.Member):
                                        if entry.user.guild_permissions.administrator:
                                            is_admin = True
                                        break
                        except Exception as e:
                            logging.warning(f"[PeriodicCheck] Audit log error for {member}: {e}")
                        if is_admin:
                            logging.info(f"[PeriodicCheck] User {member} ({member.id}) gained subscription role(s) from admin. Allowing.")
                            await self.restore_member_roles(member)
                        else:
                            # Remove the roles and require user to complete verification themselves
                            roles_to_remove = [guild.get_role(role_id) for role_id in added_roles if guild.get_role(role_id)]
                            if roles_to_remove:
                                await member.remove_roles(*[r for r in roles_to_remove if r is not None], reason="User must complete verification process themselves (periodic check)")
                                await self.log_member_event(
                                    guild,
                                    "🛑 Removed Subscription Roles (Periodic Check)",
                                    f"Removed roles from {member.mention} (user must complete verification process themselves)",
                                    member,
                                    discord.Color.red(),
                                    roles_to_remove
                                )
                # Check all users with open tickets (user_ticket_channels)
                for user_id, channel_id in list(self.user_ticket_channels.items()):
                    member = guild.get_member(user_id)
                    if not member:
                        continue
                    user_role_ids = {role.id for role in member.roles}
                    added_roles = user_role_ids & subscription_roles
                    if added_roles:
                        # Only allow auto-verification if roles were added by admin
                        is_admin = False
                        try:
                            async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.member_role_update):
                                if entry.target and entry.target.id == member.id:
                                    if entry.user and isinstance(entry.user, discord.Member):
                                        if entry.user.guild_permissions.administrator:
                                            is_admin = True
                                        break
                        except Exception as e:
                            logging.warning(f"[PeriodicCheck] Audit log error for {member}: {e}")
                        if is_admin:
                            logging.info(f"[PeriodicCheck] Ticket user {member} ({member.id}) gained subscription role(s) from admin. Allowing.")
                            await self.restore_member_roles(member)
                        else:
                            # Remove the roles and require user to complete verification themselves
                            roles_to_remove = [guild.get_role(role_id) for role_id in added_roles if guild.get_role(role_id)]
                            if roles_to_remove:
                                await member.remove_roles(*[r for r in roles_to_remove if r is not None], reason="User must complete verification process themselves (periodic check)")
                                await self.log_member_event(
                                    guild,
                                    "🛑 Removed Subscription Roles (Periodic Check)",
                                    f"Removed roles from {member.mention} (user must complete verification process themselves)",
                                    member,
                                    discord.Color.red(),
                                    roles_to_remove
                                )
            except Exception as e:
                logging.error(f"Error in periodic unverified check: {e}")
            await asyncio.sleep(120)

async def setup(bot):
    await bot.add_cog(MemberManagement(bot))