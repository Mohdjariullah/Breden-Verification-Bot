import discord
from discord.ext import commands
from discord import app_commands
import logging
import os
import asyncio
from typing import Dict, List, Set
from datetime import datetime, timezone

class MemberManagement(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Store member roles when they join
        self.member_original_roles: Dict[int, List[int]] = {}
        # Track users who need role monitoring (prevent Whop bot from re-adding)
        self.users_awaiting_verification: Set[int] = set()
        # Track users currently being verified to prevent race conditions
        self.users_being_verified: Set[int] = set()
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
            launchpad_role_id = int(launchpad_role_env)
            member_role_id = int(member_role_env)
            
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
                int(os.getenv('LAUNCHPAD_ROLE_ID')),
                int(os.getenv('MEMBER_ROLE_ID'))
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
                    role = after.guild.get_role(role_id)
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
            # Mark user as being verified to prevent race conditions
            self.users_being_verified.add(member.id)
            print(f"🔄 DEBUG: Starting verification for {member.name}")
            
            # Small delay to ensure any pending role updates are processed
            await asyncio.sleep(1)
            
            restored_roles = []
            if member.id in self.member_original_roles:
                original_role_ids = self.member_original_roles[member.id]
                
                if original_role_ids:
                    # Get role objects from IDs
                    roles_to_restore = []
                    for role_id in original_role_ids:
                        role = member.guild.get_role(role_id)
                        if role:
                            roles_to_restore.append(role)
                        else:
                            logging.warning(f"Role with ID {role_id} not found for {member.name}")
                    
                    if roles_to_restore:
                        # IMPORTANT: Remove from monitoring BEFORE adding roles
                        self.users_awaiting_verification.discard(member.id)
                        print(f"✅ DEBUG: Removed {member.name} from monitoring list BEFORE role restoration")
                        
                        # Now restore the roles
                        await member.add_roles(*roles_to_restore, reason="Subscription verification completed")
                        restored_roles = roles_to_restore
                        role_names = [role.name for role in roles_to_restore]
                        print(f"✅ DEBUG: Successfully restored roles for {member.name}: {role_names}")
                        logging.info(f"Restored subscription roles for {member.name}: {role_names}")
                    else:
                        logging.info(f"No valid subscription roles to restore for {member.name}")
                        # Still remove from monitoring even if no roles to restore
                        self.users_awaiting_verification.discard(member.id)
                else:
                    logging.info(f"No original subscription roles to restore for {member.name}")
                    # Still remove from monitoring
                    self.users_awaiting_verification.discard(member.id)
                
                # Remove from tracking
                del self.member_original_roles[member.id]
                
            else:
                logging.warning(f"No stored subscription roles found for {member.name}")
                # Remove from monitoring anyway
                self.users_awaiting_verification.discard(member.id)
            
            # Remove from verification process
            self.users_being_verified.discard(member.id)
            print(f"✅ DEBUG: Completed verification process for {member.name}")
            
            return restored_roles
                
        except Exception as e:
            # Make sure to clean up even if there's an error
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
                for role_id in self.member_original_roles[user.id]:
                    role = interaction.guild.get_role(role_id)
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
                int(os.getenv('LAUNCHPAD_ROLE_ID')): "Launchpad ($98/mo)",
                int(os.getenv('MEMBER_ROLE_ID')): "Member (Free)"
            }
            
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
                    pending_users.append(f"• {user.mention} - {roles_text} ({status})")
            
            if pending_users:
                embed.add_field(
                    name="Recent Pending Verifications",
                    value="\n".join(pending_users) + (f"\n... and {count - len(pending_users)} more" if count > 5 else ""),
                    inline=False
                )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="force_verify", description="Manually verify a user and restore their subscription roles")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(user="The user to verify")
    async def force_verify(self, interaction: discord.Interaction, user: discord.Member):
        """Manually verify a user and restore their subscription roles"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            restored_roles = await self.restore_member_roles(user)
            
            if restored_roles:
                role_names = [role.name for role in restored_roles]
                embed = discord.Embed(
                    title="✅ Manual Verification Complete",
                    description=f"Successfully verified {user.mention} and restored their subscription roles.",
                    color=discord.Color.green()
                )
                embed.add_field(name="Restored Roles", value=", ".join(role_names), inline=False)
                
                # Log manual verification
                await self.log_member_event(
                    interaction.guild,
                    "🔧 Manual Verification",
                    f"{user.mention} was manually verified by {interaction.user.mention}",
                    user,
                    discord.Color.purple(),
                    restored_roles
                )
            else:
                embed = discord.Embed(
                    title="⚠️ No Roles to Restore",
                    description=f"{user.mention} has no stored subscription roles to restore.",
                    color=discord.Color.yellow()
                )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(f"❌ Error during manual verification: {e}", ephemeral=True)

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
        launchpad_id = os.getenv('LAUNCHPAD_ROLE_ID')
        member_id = os.getenv('MEMBER_ROLE_ID')
        embed.add_field(name="Expected Role IDs", value=f"Launchpad: {launchpad_id}\nMember: {member_id}", inline=False)
        
        # Check if user has subscription roles
        user_role_ids = {role.id for role in user.roles}
        subscription_roles = {int(launchpad_id), int(member_id)}
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
        
        # Clean stored roles for users not in server
        for user_id in list(self.member_original_roles.keys()):
            if not interaction.guild.get_member(user_id):
                del self.member_original_roles[user_id]
                cleaned_stored += 1
        
        # Clean monitoring list
        for user_id in list(self.users_awaiting_verification):
            if not interaction.guild.get_member(user_id):
                self.users_awaiting_verification.discard(user_id)
                cleaned_monitoring += 1
        
        # Clean verifying list
        for user_id in list(self.users_being_verified):
            if not interaction.guild.get_member(user_id):
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

async def setup(bot):
    await bot.add_cog(MemberManagement(bot))