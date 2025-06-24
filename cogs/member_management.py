import discord
from discord.ext import commands
from discord import app_commands
import logging
import os
import asyncio
from typing import Dict, List, Set, Optional
from datetime import datetime, timezone

def get_env_role_id(var_name):
    value = os.getenv(var_name)
    try:
        return int(value) if value is not None else None
    except Exception:
        return None

class MemberManagement(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Store member roles when they join
        self.member_original_roles: Dict[int, List[int]] = {}
        # Track users who need role monitoring (prevent Whop bot from re-adding)
        self.users_awaiting_verification: Set[int] = set()
        # Track users currently being verified to prevent race conditions
        self.users_being_verified: Set[int] = set()
        # Track if a failed verification log was already sent for a user
        self.failed_verification_logged: Dict[int, bool] = {}
        # Track total successful verifications
        self.total_verified: int = 0
        print("🔧 MemberManagement cog initialized")

    @commands.Cog.listener()
    async def on_ready(self):
        """Called when the cog is ready"""
        print("🔧 MemberManagement cog is ready!")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Handle new member joins - check for subscription roles and remove them for verification"""
        try:
            print(f"\n🔍 DEBUG: Member {member.name} joined server {member.guild.name}")
            print(f"🔍 DEBUG: Member roles: {[role.name for role in member.roles]}")
            print(f"🔍 DEBUG: Member role IDs: {[role.id for role in member.roles]}")
            
            # Check environment variables first
            launchpad_role_env = os.getenv('LAUNCHPAD_ROLE_ID')
            member_role_env = os.getenv('MEMBER_ROLE_ID')
            
            print(f"🔍 DEBUG: LAUNCHPAD_ROLE_ID from env: {launchpad_role_env}")
            print(f"🔍 DEBUG: MEMBER_ROLE_ID from env: {member_role_env}")
            
            if not launchpad_role_env or not member_role_env:
                print("❌ ERROR: Role IDs not set in environment variables!")
                return
            
            # Define the subscription roles that need verification
            launchpad_role_id = get_env_role_id('LAUNCHPAD_ROLE_ID')
            member_role_id = get_env_role_id('MEMBER_ROLE_ID')
            
            print(f"🔍 DEBUG: Looking for Launchpad role ID: {launchpad_role_id}")
            print(f"🔍 DEBUG: Looking for Member role ID: {member_role_id}")
            
            subscription_roles = {launchpad_role_id, member_role_id}
            
            # Get user's current roles (excluding @everyone)
            current_roles = [role for role in member.roles if role != member.guild.default_role]
            user_role_ids = {role.id for role in current_roles}
            
            print(f"🔍 DEBUG: User role IDs (excluding @everyone): {user_role_ids}")
            print(f"🔍 DEBUG: Subscription role IDs to check: {subscription_roles}")
            
            # Check if user has any subscription roles
            has_subscription_roles = user_role_ids & subscription_roles
            print(f"🔍 DEBUG: Has subscription roles: {has_subscription_roles}")
            
            if has_subscription_roles:
                print(f"✅ DEBUG: User has subscription roles, removing them...")
                # User joined with subscription roles - needs verification
                roles_to_remove = [role for role in current_roles if role.id in subscription_roles]
                
                print(f"🔍 DEBUG: Roles to remove: {[role.name for role in roles_to_remove]}")
                
                # Store original roles (as role IDs for persistence)
                self.member_original_roles[member.id] = [role.id for role in roles_to_remove]
                
                # Add to monitoring list to prevent Whop bot from re-adding
                self.users_awaiting_verification.add(member.id)
                
                # Remove subscription roles
                await member.remove_roles(*roles_to_remove, reason="Subscription verification required")
                
                role_names = [role.name for role in roles_to_remove]
                print(f"✅ DEBUG: Successfully removed roles: {role_names}")
                print(f"🔍 DEBUG: Added user {member.name} to monitoring list")
                logging.info(f"Removed subscription roles from {member.name} ({member.id}): {role_names}")
                
                # Log member join with subscription
                await self.log_member_event(
                    member.guild,
                    "🛒 Subscriber Joined",
                    f"{member.mention} joined with subscription roles - verification required",
                    member,
                    discord.Color.orange(),
                    roles_to_remove
                )
            else:
                print(f"ℹ️ DEBUG: User has no subscription roles, no action needed")
                # User joined without subscription roles - regular member
                logging.info(f"Regular member {member.name} ({member.id}) joined without subscription roles")
                
                # Log regular member join
                await self.log_member_event(
                    member.guild,
                    "👋 Member Joined",
                    f"{member.mention} joined the server (no subscription roles)",
                    member,
                    discord.Color.blue()
                )
                
        except Exception as e:
            print(f"❌ DEBUG: Error in on_member_join: {e}")
            logging.error(f"Error in on_member_join for {member.name}: {e}")
            import traceback
            traceback.print_exc()

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        """Handle member leaves - stop monitoring and log if they had subscription roles"""
        try:
            print(f"\n👋 DEBUG: Member {member.name} left server {member.guild.name}")
            
            # Check if user was being tracked
            had_stored_roles = member.id in self.member_original_roles
            was_monitored = member.id in self.users_awaiting_verification
            was_verifying = member.id in self.users_being_verified
            
            stored_roles_info = []
            
            if had_stored_roles:
                # Get the stored role information before cleaning up
                stored_role_ids = self.member_original_roles[member.id]
                
                # Convert role IDs to role names for logging
                subscription_roles_map = {
                    get_env_role_id('LAUNCHPAD_ROLE_ID'): "🚀 VIP ($98/mo),($750/yr), or $1,000 for lifetime access)",
                    get_env_role_id('MEMBER_ROLE_ID'): "👤 Member (Free)"
                }
                
                for role_id in stored_role_ids:
                    role_name = subscription_roles_map.get(role_id, f"Unknown Role (ID: {role_id})")
                    stored_roles_info.append(role_name)
                
                print(f"🔍 DEBUG: User {member.name} left with stored subscription roles: {stored_roles_info}")
                
                # Clean up tracking data
                del self.member_original_roles[member.id]
                self.users_awaiting_verification.discard(member.id)
                self.users_being_verified.discard(member.id)
                
                # Log member leave with subscription roles
                await self.log_member_event(
                    member.guild,
                    "🚪 Subscriber Left",
                    f"{member.mention} left the server with unverified subscription roles: {', '.join(stored_roles_info)}",
                    member,
                    discord.Color.red(),
                    stored_roles_info
                )
                
                logging.info(f"Member {member.name} ({member.id}) left with stored subscription roles: {stored_roles_info}")
                
            else:
                # Regular member left (no subscription roles)
                print(f"ℹ️ DEBUG: Regular member {member.name} left (no stored roles)")
                
                # Still clean up any monitoring data just in case
                self.users_awaiting_verification.discard(member.id)
                self.users_being_verified.discard(member.id)
                
                # Log regular member leave
                await self.log_member_event(
                    member.guild,
                    "👋 Member Left",
                    f"{member.mention} left the server",
                    member,
                    discord.Color.greyple()
                )
                
                logging.info(f"Regular member {member.name} ({member.id}) left the server")
                
        except Exception as e:
            print(f"❌ DEBUG: Error in on_member_remove: {e}")
            logging.error(f"Error in on_member_remove for {member.name}: {e}")
            import traceback
            traceback.print_exc()

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        """Monitor role changes and prevent Whop bot from re-adding roles to unverified users"""
        try:
            # Skip if user is not being monitored
            if after.id not in self.users_awaiting_verification:
                return
            
            # Skip if user is currently being verified (prevents race condition)
            if after.id in self.users_being_verified:
                print(f"🔄 DEBUG: Skipping role check for {after.name} - currently being verified")
                return
            
            # Define subscription roles
            subscription_roles = {
                get_env_role_id('LAUNCHPAD_ROLE_ID'),
                get_env_role_id('MEMBER_ROLE_ID')
            }
            
            # Check if any subscription roles were added
            before_role_ids = {role.id for role in before.roles}
            after_role_ids = {role.id for role in after.roles}
            
            # Find newly added subscription roles
            added_roles = after_role_ids - before_role_ids
            added_subscription_roles = added_roles & subscription_roles
            
            if added_subscription_roles:
                print(f"🚨 DEBUG: Whop bot re-added roles to {after.name}! Removing again...")
                
                # Get the role objects to remove
                roles_to_remove = []
                for role_id in added_subscription_roles:
                    role = after.guild.get_role(role_id) if after.guild else None
                    if role:
                        roles_to_remove.append(role)
                
                if roles_to_remove:
                    # Remove the roles again (DO NOT remove from monitoring here!)
                    await after.remove_roles(*roles_to_remove, reason="User awaiting verification - Whop bot interference")
                    
                    role_names = [role.name for role in roles_to_remove]
                    print(f"✅ DEBUG: Re-removed roles from {after.name}: {role_names}")
                    print(f"🔍 DEBUG: User {after.name} still being monitored")
                    logging.info(f"Re-removed subscription roles from {after.name} (Whop bot interference): {role_names}")
                    
                    # Log the interference
                    await self.log_member_event(
                        after.guild,
                        "🔄 Role Re-Removal",
                        f"Whop bot re-added roles to {after.mention} - removed again (awaiting verification)",
                        after,
                        discord.Color.yellow(),
                        roles_to_remove
                    )
                    
        except Exception as e:
            print(f"❌ DEBUG: Error in on_member_update: {e}")
            logging.error(f"Error in on_member_update for {after.name}: {e}")

    async def restore_member_roles(self, member):
        """Restore original subscription roles to a member after verification"""
        try:
            self.users_being_verified.add(member.id)
            print(f"🔄 DEBUG: Starting verification for {member.name}")
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
                    if roles_to_restore:
                        self.users_awaiting_verification.discard(member.id)
                        await member.add_roles(*roles_to_restore, reason="Subscription verification completed")
                        restored_roles = roles_to_restore
                        role_names = [role.name for role in roles_to_restore]
                        print(f"✅ DEBUG: Successfully restored roles for {member.name}: {role_names}")
                        logging.info(f"Restored subscription roles for {member.name}: {role_names}")
                        subscription_role_ids = set([role.id for role in roles_to_restore])
                        max_retries = 5
                        retry_delay = 2
                        success = False
                        for attempt in range(max_retries):
                            await asyncio.sleep(retry_delay)
                            user_role_ids = {role.id for role in member.roles}
                            if subscription_role_ids.issubset(user_role_ids):
                                success = True
                                print(f"✅ Post-verification check: {member.name} has all roles after {attempt+1} attempt(s)")
                                break
                            else:
                                print(f"⚠️ Post-verification check: {member.name} missing roles, retrying ({attempt+1}/{max_retries})")
                                try:
                                    await member.add_roles(*roles_to_restore, reason="Retrying role restoration after verification")
                                except Exception as e:
                                    logging.error(f"Error retrying role restoration for {member.name}: {e}")
                        if not success:
                            logging.error(f"❌ Failed to restore roles for {member.name} after verification retries!")
                            self.failed_verification_logged[member.id] = True
                            await self.log_member_event(
                                member.guild,
                                "❌ Verification Role Restoration Failed",
                                f"{member.mention} did not receive all subscription roles after verification retries. Manual intervention required.",
                                member,
                                discord.Color.red(),
                                roles_to_restore
                            )
                        else:
                            # Only log success if not already failed
                            if not self.failed_verification_logged.get(member.id, False):
                                monitor_seconds = 120
                                print(f"⏳ Monitoring {member.name} for {monitor_seconds} seconds post-verification...")
                                for _ in range(monitor_seconds // 5):
                                    await asyncio.sleep(5)
                                    user_role_ids = {role.id for role in member.roles}
                                    missing = subscription_role_ids - user_role_ids
                                    if missing:
                                        print(f"⚠️ {member.name} lost roles {missing} during monitoring. Re-adding...")
                                        try:
                                            to_readd = [member.guild.get_role(rid) for rid in missing if member.guild.get_role(rid)]
                                            if to_readd:
                                                await member.add_roles(*to_readd, reason="Re-adding lost roles during post-verification monitoring")
                                                logging.info(f"Re-added lost roles to {member.name} during monitoring: {to_readd}")
                                        except Exception as e:
                                            logging.error(f"Error re-adding lost roles to {member.name} during monitoring: {e}")
                                print(f"✅ Monitoring complete for {member.name}")
                                # Log success only if not failed
                                await self.log_member_event(
                                    member.guild,
                                    "✅ Subscription Verification Completed",
                                    f"{member.mention} completed verification - restored: {', '.join(role_names)}",
                                    member,
                                    discord.Color.green(),
                                    roles_to_restore
                                )
                                # Increment total_verified and clear failed flag if present
                                self.total_verified += 1
                                if member.id in self.failed_verification_logged:
                                    del self.failed_verification_logged[member.id]
                            # Clean up the flag after monitoring
                            if member.id in self.failed_verification_logged:
                                del self.failed_verification_logged[member.id]
                    else:
                        logging.info(f"No valid subscription roles to restore for {member.name}")
                        self.users_awaiting_verification.discard(member.id)
                else:
                    logging.info(f"No original subscription roles to restore for {member.name}")
                    self.users_awaiting_verification.discard(member.id)
                del self.member_original_roles[member.id]
            else:
                logging.warning(f"No stored subscription roles found for {member.name}")
                self.users_awaiting_verification.discard(member.id)
            self.users_being_verified.discard(member.id)
            print(f"✅ DEBUG: Completed verification process for {member.name}")
            return restored_roles
        except Exception as e:
            self.users_being_verified.discard(member.id)
            self.users_awaiting_verification.discard(member.id)
            logging.error(f"Error restoring subscription roles for {member.name}: {e}")
            raise

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

    @app_commands.command(name="test_member_join", description="Test the member join functionality")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(user="The user to test with")
    async def test_member_join(self, interaction: discord.Interaction, user: discord.Member):
        """Test the member join functionality manually"""
        await interaction.response.defer(ephemeral=True)
        
        # Create test log embed
        test_embed = discord.Embed(
            title="🧪 Manual Test Started",
            description=f"Testing member join functionality for {user.mention}",
            color=discord.Color.yellow(),
            timestamp=datetime.now(timezone.utc)
        )
        test_embed.add_field(name="Tested By", value=interaction.user.mention, inline=True)
        test_embed.add_field(name="Test Subject", value=user.mention, inline=True)
        test_embed.add_field(name="Current Roles", value=", ".join([role.name for role in user.roles]) if user.roles else "None", inline=False)
        test_embed.set_footer(text="Manual Test")
        
        # Send to logs
        await self.send_to_logs(interaction.guild, test_embed)
        
        print(f"🧪 MANUAL TEST: Testing member join for {user.name}")
        
        # Run the test
        try:
            await self.on_member_join(user)
            
            # Create success log
            success_embed = discord.Embed(
                title="✅ Manual Test Completed",
                description=f"Member join test completed for {user.mention}",
                color=discord.Color.green(),
                timestamp=datetime.now(timezone.utc)
            )
            
            # Check if user was processed
            if user.id in self.member_original_roles:
                stored_roles = []
                guild = interaction.guild
                if guild is not None:
                    for role_id in self.member_original_roles[user.id]:
                        role = guild.get_role(role_id)
                        if role:
                            stored_roles.append(role.name)
                success_embed.add_field(name="Roles Stored", value=", ".join(stored_roles) if stored_roles else "None", inline=False)
                success_embed.add_field(name="Monitoring Status", value="✅ Added to monitoring" if user.id in self.users_awaiting_verification else "❌ Not monitored", inline=True)
            else:
                success_embed.add_field(name="Result", value="No subscription roles found - no action taken", inline=False)
            
            success_embed.set_footer(text="Manual Test Result")
            
            # Send to logs
            await self.send_to_logs(interaction.guild, success_embed)
            
            await interaction.followup.send(f"✅ Test completed for {user.mention}. Check logs channel for detailed results.", ephemeral=True)
            
        except Exception as e:
            # Create error log
            error_embed = discord.Embed(
                title="❌ Manual Test Failed",
                description=f"Error during member join test for {user.mention}",
                color=discord.Color.red(),
                timestamp=datetime.now(timezone.utc)
            )
            error_embed.add_field(name="Error", value=str(e), inline=False)
            error_embed.set_footer(text="Manual Test Error")
            
            # Send to logs
            await self.send_to_logs(interaction.guild, error_embed)
            
            await interaction.followup.send(f"❌ Test failed for {user.mention}. Check logs channel for error details.", ephemeral=True)

    async def send_to_logs(self, guild, embed):
        """Helper function to send embeds to logs channel"""
        logs_channel_id = os.getenv('LOGS_CHANNEL_ID')
        if logs_channel_id:
            logs_channel = guild.get_channel(int(logs_channel_id))
            if logs_channel:
                try:
                    await logs_channel.send(embed=embed)
                except Exception as e:
                    print(f"❌ Failed to send to logs channel: {e}")
            else:
                print(f"❌ Logs channel not found: {logs_channel_id}")
        else:
            print("❌ LOGS_CHANNEL_ID not set in environment variables")

    @app_commands.command(name="check_stored_roles", description="Check how many members have stored subscription roles")
    @app_commands.default_permissions(administrator=True)
    async def check_stored_roles(self, interaction: discord.Interaction):
        """Check how many members have stored subscription roles"""
        count = len(self.member_original_roles)
        monitoring_count = len(self.users_awaiting_verification)
        verifying_count = len(self.users_being_verified)
        
        embed = discord.Embed(
            title="📊 Pending Verifications",
            description=f"Currently tracking subscription roles for **{count}** members awaiting verification.",
            color=discord.Color.blue()
        )
        
        embed.add_field(name="👥 Users Awaiting Verification", value=str(count), inline=True)
        embed.add_field(name="🔍 Users Being Monitored", value=str(monitoring_count), inline=True)
        embed.add_field(name="⚙️ Users Being Verified", value=str(verifying_count), inline=True)
        embed.add_field(name="🛡️ Protection Status", value="Active" if monitoring_count > 0 else "Inactive", inline=True)
        
        if count > 0:
            # Show some details about pending verifications
            pending_users = []
            subscription_roles = {
                get_env_role_id('LAUNCHPAD_ROLE_ID'): "🚀 VIP ($98/mo),($750/yr), or $1,000 for lifetime access)",
                get_env_role_id('MEMBER_ROLE_ID'): "👤 Member (Free)"
            }
            
            if interaction.guild is not None:
                for user_id in list(self.member_original_roles.keys())[:5]:  # Show first 5
                    user = interaction.guild.get_member(user_id)
                    if user:
                        user_roles = []
                        for role_id in self.member_original_roles[user_id]:
                            role_name = subscription_roles.get(role_id, f"Role ID: {role_id}")
                        user_roles.append(role_name)
                    
                    roles_text = ", ".join(user_roles) if user_roles else "Unknown"
                    
                    # Status indicators
                    status_parts = []
                    if user_id in self.users_awaiting_verification:
                        status_parts.append("🔍 Monitored")
                    if user_id in self.users_being_verified:
                        status_parts.append("⚙️ Verifying")
                    
                    status = " | ".join(status_parts) if status_parts else "⚠️ Not tracked"
                    if user is not None:
                        pending_users.append(f"• {user.mention} - {roles_text} ({status})")
                    else:
                        pending_users.append(f"• [User Left] (ID: {user_id}) - {roles_text} ({status})")
            
            if pending_users:
                embed.add_field(
                    name="Recent Pending Verifications",
                    value="\n".join(pending_users) + (f"\n... and {count - len(pending_users)} more" if count > 5 else ""),
                    inline=False
                )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    def get_pending_verification_users(self, guild):
        # Return a list of discord.Member objects for users who have not completed verification
        pending = []
        for user_id in self.member_original_roles:
            if user_id in self.users_awaiting_verification or user_id in self.users_being_verified:
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
        for user_id in list(cog.member_original_roles.keys()):
            member = guild.get_member(user_id)
            if member and (user_id in cog.users_awaiting_verification or user_id in cog.users_being_verified):
                if current.lower() in member.display_name.lower():
                    suggestions.append(app_commands.Choice(name=member.display_name, value=str(member.id)))
                if len(suggestions) >= 20:
                    break
        return suggestions

    @app_commands.command(name="force_verify", description="Manually verify a user and restore their subscription roles")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(user="The user to verify (optional)")
    async def force_verify(self, interaction: discord.Interaction, user: Optional[str] = None):
        """Manually verify a user and restore their subscription roles. If no user is provided, suggest pending users."""
        await interaction.response.defer(ephemeral=True)
        member = None
        if user:
            # Try to resolve user as ID, but only if interaction.guild is not None
            if interaction.guild is not None:
                try:
                    member = interaction.guild.get_member(int(user))
                except Exception:
                    member = None
            else:
                member = None
            if member is None:
                member_mention = 'Unknown User'
            else:
                member_mention = member.mention
            pending = self.get_pending_verification_users(interaction.guild)
            if not pending:
                await interaction.followup.send("✅ No users are currently pending verification!", ephemeral=True)
                return
            embed = discord.Embed(
                title="Pending Users for Verification",
                description="Select a user to force verify:",
                color=discord.Color.blue()
            )
            for member in pending[:10]:
                embed.add_field(name=member.display_name, value=member.mention, inline=True)
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        # Only call restore_member_roles if user is not None
        try:
            member_mention = member.mention if member is not None else 'Unknown User'
            restored_roles = await self.restore_member_roles(member)
            if restored_roles:
                role_names = [role.name for role in restored_roles]
                embed = discord.Embed(
                    title="✅ Manual Verification Complete",
                    description=f"Successfully verified {member_mention} and restored their subscription roles.",
                    color=discord.Color.green()
                )
                embed.add_field(name="Restored Roles", value=", ".join(role_names), inline=False)
                await self.log_member_event(
                    interaction.guild,
                    "🔧 Manual Verification",
                    f"{member_mention} was manually verified by {interaction.user.mention}",
                    member,
                    discord.Color.purple(),
                    restored_roles
                )
            else:
                embed = discord.Embed(
                    title="⚠️ No Roles to Restore",
                    description=f"{member_mention} has no stored subscription roles to restore.",
                    color=discord.Color.yellow()
                )
            await interaction.followup.send(embed=embed, ephemeral=True)
            log_embed = discord.Embed(title="Admin Command Used", description=f"/force_verify used by {interaction.user.mention}", color=discord.Color.purple())
            log_embed.add_field(name="Target", value=member_mention, inline=True)
            await self.send_to_logs(interaction.guild, log_embed)
        except Exception as e:
            await interaction.followup.send(f"❌ Error during manual verification: {e}", ephemeral=True)

    @force_verify.autocomplete('user')
    async def force_verify_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self.pending_users_autocomplete(interaction, current)

    @app_commands.command(name="debug_roles", description="Debug role information for a user")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(user="The user to check")
    async def debug_roles(self, interaction: discord.Interaction, user: discord.Member):
        """Debug role information for a user"""
        embed = discord.Embed(
            title=f"🔍 Role Debug for {user.name}",
            color=discord.Color.blue()
        )
        
        # Show all roles
        all_roles = [f"{role.name} (ID: {role.id})" for role in user.roles]
        embed.add_field(name="All Roles", value="\n".join(all_roles) if all_roles else "None", inline=False)
        
        # Show environment variables
        launchpad_id = get_env_role_id('LAUNCHPAD_ROLE_ID')
        member_id = get_env_role_id('MEMBER_ROLE_ID')
        embed.add_field(name="Expected Role IDs", value=f"Launchpad: {launchpad_id}\nMember: {member_id}", inline=False)
        
        # Check if user has subscription roles
        user_role_ids = {role.id for role in user.roles}
        subscription_roles = {launchpad_id, member_id}
        has_subscription = user_role_ids & subscription_roles
        embed.add_field(name="Has Subscription Roles", value=str(bool(has_subscription)), inline=False)
        
        # Check stored roles
        stored = self.member_original_roles.get(user.id, [])
        embed.add_field(name="Stored Roles", value=str(stored) if stored else "None", inline=False)
        
        # Check monitoring status
        is_monitored = user.id in self.users_awaiting_verification
        is_verifying = user.id in self.users_being_verified
        embed.add_field(name="Being Monitored", value=str(is_monitored), inline=False)
        embed.add_field(name="Currently Verifying", value=str(is_verifying), inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="cleanup_tracking", description="Clean up orphaned tracking data")
    @app_commands.default_permissions(administrator=True)
    async def cleanup_tracking(self, interaction: discord.Interaction):
        """Clean up tracking data for users who are no longer in the server"""
        await interaction.response.defer(ephemeral=True)
        
        cleaned_stored = 0
        cleaned_monitoring = 0
        cleaned_verifying = 0
        
        # Get the guild object robustly
        guild = interaction.guild
        if guild is None and hasattr(self.bot, 'get_guild'):
            guild_id = os.getenv('GUILD_ID')
            if guild_id:
                guild = self.bot.get_guild(int(guild_id))
        
        # Clean stored roles for users not in server
        for user_id in list(self.member_original_roles.keys()):
            member = guild.get_member(user_id) if guild and hasattr(guild, 'get_member') else None
            if not member:
                del self.member_original_roles[user_id]
                cleaned_stored += 1
        
        # Clean monitoring list
        for user_id in list(self.users_awaiting_verification):
            member = guild.get_member(user_id) if guild and hasattr(guild, 'get_member') else None
            if not member:
                self.users_awaiting_verification.discard(user_id)
                cleaned_monitoring += 1
        
        # Clean verifying list
        for user_id in list(self.users_being_verified):
            member = guild.get_member(user_id) if guild and hasattr(guild, 'get_member') else None
            if not member:
                self.users_being_verified.discard(user_id)
                cleaned_verifying += 1
        
        embed = discord.Embed(
            title="🧹 Cleanup Complete",
            description="Removed tracking data for users who left the server.",
            color=discord.Color.green()
        )
        embed.add_field(name="Stored Roles Cleaned", value=str(cleaned_stored), inline=True)
        embed.add_field(name="Monitoring Cleaned", value=str(cleaned_monitoring), inline=True)
        embed.add_field(name="Verifying Cleaned", value=str(cleaned_verifying), inline=True)
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        log_embed = discord.Embed(title="Admin Command Used", description=f"/cleanup_tracking used by {interaction.user.mention}", color=discord.Color.purple())
        await self.send_to_logs(interaction.guild, log_embed)

    @app_commands.command(name="help_admin", description="List all admin commands and their descriptions")
    @app_commands.default_permissions(administrator=True)
    async def help_admin(self, interaction: discord.Interaction):
        """List all admin commands and their descriptions"""
        commands_info = [
            ("/force_verify <user>", "Manually verify a user and restore their subscription roles."),
            ("/remove_verification <user>", "Remove all subscription roles and tracking for a user."),
            ("/pending_verifications", "List all users currently awaiting verification or with failed verifications."),
            ("/retry_verification <user>", "Retry the verification/role restoration process for a user."),
            ("/bot_status", "Show bot uptime, latency, loaded cogs, and environment variable status."),
            ("/show_logs <count>", "Show the last N log entries (from a file or memory)."),
            ("/debug_roles <user>", "Show all roles, expected roles, and tracking status for a user."),
            ("/cleanup_tracking", "Remove tracking for users who have left the server."),
            ("/reset_tracking", "Clear all tracking data (dangerous, admin only)."),
            ("/refresh_welcome", "Re-post the welcome/verification message."),
            ("/setup_permissions", "Set up channel permissions for onboarding."),
            ("/set_logs_channel <channel>", "Set the channel for logs."),
            ("/set_welcome_channel <channel>", "Set the channel for welcome/verification."),
            ("/help_admin", "List all admin commands and what they do."),
        ]
        embed = discord.Embed(
            title="🛠️ Admin Commands Help",
            description="List of available admin commands:",
            color=discord.Color.blue()
        )
        for cmd, desc in commands_info:
            embed.add_field(name=cmd, value=desc, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        log_embed = discord.Embed(title="Admin Command Used", description=f"/help_admin used by {interaction.user.mention}", color=discord.Color.purple())
        await self.send_to_logs(interaction.guild, log_embed)

async def setup(bot):
    await bot.add_cog(MemberManagement(bot))