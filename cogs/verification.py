import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View
import os
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Set

from cogs.security_utils import safe_int_convert, security_check

BOOKING_LINK = os.getenv('CALENDLY_LINK')

def get_env_role_id(var_name):
    value = os.getenv(var_name)
    try:
        return int(value) if value is not None else None
    except Exception:
        return None

def require_guild_admin(interaction: discord.Interaction) -> bool:
    """Security check for admin commands"""
    if not interaction.guild:
        return False
    if not isinstance(interaction.user, discord.Member):
        return False
    return interaction.user.guild_permissions.administrator

class VerificationView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.ticket_cooldowns = {}  # user_id: timestamp

    @discord.ui.button(
        label="Start Verification",
        style=discord.ButtonStyle.green,
        custom_id="verify_button",
        emoji="🔒"
    )
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        import time
        # SECURITY: Block DMs completely
        if not interaction.guild:
            return await interaction.response.send_message(
                "❌ Verification can only be started in the server!", 
                ephemeral=True
            )
        user_id = interaction.user.id
        now = time.time()
        cooldown = 10  # seconds
        # Cooldown check
        last_press = self.ticket_cooldowns.get(user_id, 0)
        if now - last_press < cooldown:
            return await interaction.response.send_message(
                f"⏳ Please wait {int(cooldown - (now - last_press))} seconds before trying again.",
                ephemeral=True
            )
        self.ticket_cooldowns[user_id] = now
        await interaction.response.defer(ephemeral=True)
        # Check if user already has any of the subscription roles
        launchpad_role_id = get_env_role_id('LAUNCHPAD_ROLE_ID')
        member_role_id = get_env_role_id('MEMBER_ROLE_ID')
        subscription_roles = set(filter(None, [launchpad_role_id, member_role_id]))
        user_roles = {r.id for r in getattr(interaction.user, 'roles', [])}
        if user_roles & subscription_roles:
            return await interaction.followup.send(
                embed=discord.Embed(
                    title="✅ Already Verified",
                    description="You already have subscription access! No verification needed.",
                    color=discord.Color.green()
                ),
                ephemeral=True
            )
        # Check if user has stored roles (meaning they need verification)
        member_cog = getattr(getattr(interaction, 'client', None), 'get_cog', lambda name: None)('MemberManagement')
        if not member_cog or interaction.user.id not in getattr(member_cog, 'member_original_roles', {}):
            return await interaction.followup.send(
                embed=discord.Embed(
                    title="❌ No Subscription Found",
                    description="You don't have any subscription roles that need verification. Please purchase a subscription first.",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )
        # --- Only allow one ticket per user ---
        if member_cog and user_id in member_cog.user_ticket_channels:
            channel_id = member_cog.user_ticket_channels[user_id]
            channel = interaction.guild.get_channel(channel_id)
            if channel:
                return await interaction.followup.send(
                    f"🔗 You already have a verification ticket: {channel.mention}",
                    ephemeral=True
                )
            else:
                # Clean up mapping if channel doesn't exist
                member_cog.unregister_ticket(user_id)
        # FIXED: Better duplicate ticket prevention
        ticket_name = f"verify-{interaction.user.name.lower()}"
        existing_tickets = []
        # Find ALL existing tickets for this user
        for channel in interaction.guild.channels:
            if isinstance(channel, discord.TextChannel) and channel.name.startswith(f"verify-{interaction.user.name.lower()}"):
                existing_tickets.append(channel)
        if existing_tickets:
            # Delete all existing tickets first
            for ticket in existing_tickets:
                try:
                    await ticket.delete(reason=f"Cleaning up duplicate tickets for {interaction.user.name}")
                    logging.info(f"Deleted existing ticket: {ticket.name}")
                except Exception as e:
                    logging.error(f"Failed to delete existing ticket {ticket.name}: {e}")
            # Small delay to ensure deletion completes
            await asyncio.sleep(2)
        # Create ticket channel with proper permissions from the start
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(
                view_channel=False,
                read_messages=False,
                send_messages=False
            ),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True,
                read_messages=True,
                read_message_history=True,
                send_messages=True,
                attach_files=True,
                embed_links=True,
                use_external_emojis=True
            ),
            interaction.guild.me: discord.PermissionOverwrite(
                view_channel=True,
                read_messages=True,
                read_message_history=True,
                send_messages=True,
                manage_messages=True,
                embed_links=True,
                attach_files=True,
                manage_channels=True
            )
        }
        # Add permissions for administrators
        for role in interaction.guild.roles:
            if role.permissions.administrator:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True,
                    read_messages=True,
                    read_message_history=True,
                    send_messages=True,
                    manage_messages=True
                )
        try:
            ticket_channel = await interaction.guild.create_text_channel(
                name=ticket_name,
                overwrites=overwrites,
                category=getattr(interaction.channel, 'category', None),
                topic=f"🎫 Verification ticket for {interaction.user.display_name} | User ID: {interaction.user.id}",
                reason=f"Verification ticket created for {interaction.user.name}"
            )
            logging.info(f"Created verification ticket: {ticket_channel.name} for {interaction.user.name}")
            # Register ticket in MemberManagement
            if member_cog:
                member_cog.register_ticket(user_id, ticket_channel.id)
        except Exception as e:
            await interaction.followup.send(f'❌ Failed to create ticket channel: {e}', ephemeral=True)
            logging.error(f"Failed to create ticket channel for {interaction.user.name}: {e}")
            return

        # Get user's subscription info
        stored_role_ids = member_cog.member_original_roles[interaction.user.id]
        subscription_info = []
        for role_id in stored_role_ids:
            if launchpad_role_id and role_id == launchpad_role_id:
                subscription_info.append("🚀 VIP ($98/mo),($750/yr), or $1,000 for lifetime access)")
            elif member_role_id and role_id == member_role_id:
                subscription_info.append("👤 Member (Free)")

        # Send the welcome embed with booking CTA
        expiry = datetime.now(timezone.utc) + timedelta(hours=24)
        exp_ts = int(expiry.timestamp())
        embed = discord.Embed(
            title="🎉 Welcome to Your Verification Process!",
            description=(
                "To complete your verification and gain access to your subscription, please follow these steps:\n\n"
                "# 📅 STEP 1: BOOK YOUR CALL\n"
                f"## 👉 [**CLICK HERE TO BOOK YOUR ONBOARDING CALL**]({BOOKING_LINK}) 👈\n\n"
                "**2.** After booking, click the 'I Have Booked' button below\n\n"
                f"**Note:** This ticket closes <t:{exp_ts}:R>"
            ),
            color=discord.Color.green()
        )
        embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1370122090631532655/1386775344631119963/65fe71ca-e301-40a0-b69b-de77def4f57e.jpeg")
        embed.add_field(name="📅 Booking Status", value="Pending", inline=True)
        embed.add_field(name="⏱️ Expires", value=f"<t:{exp_ts}:f>", inline=True)
        embed.add_field(name="🎯 Subscription", value="\n".join(subscription_info), inline=False)
        embed.set_footer(text=f"User ID: {interaction.user.id}")

        await ticket_channel.send(
            f"Welcome {interaction.user.mention}! Let's verify your subscription access.",
            embed=embed,
            view=ConfirmBookingView(interaction.user, ticket_channel.id)
        )

        # Log verification start
        await self.log_verification_event(
            interaction.guild,
            "🎫 Subscription Verification Started",
            f"{interaction.user.mention} started verification for: {', '.join(subscription_info)}",
            interaction.user,
            discord.Color.blue()
        )

        # Auto-close after 24 hours with DM notification
        async def auto_close():
            await asyncio.sleep(86400)
            try:
                # Check if ticket still exists and user is still in server
                current_ticket = interaction.guild.get_channel(ticket_channel.id) if interaction.guild else None
                current_member = interaction.guild.get_member(interaction.user.id) if interaction.guild else None
                
                if not current_ticket:
                    logging.info(f"Ticket for {interaction.user.name} already deleted - skipping auto-close")
                    return
                
                # Send DM to user before closing ticket (only if they're still in server)
                if current_member:
                    try:
                        dm_embed = discord.Embed(
                            title="⏰ Verification Ticket Expired",
                            description=(
                                "Your verification ticket has been automatically closed after 24 hours.\n\n"
                                "**To continue your verification:**\n"
                                "1. Return to the verification channel\n"
                                "2. Click the 'Start Verification' button again\n"
                                "3. Complete your booking and verification process\n\n"
                                "We are waiting for you to return and complete your verification!"
                            ),
                            color=discord.Color.orange()
                        )
                        dm_embed.add_field(
                            name="📋 Your Subscription",
                            value="\n".join(subscription_info),
                            inline=False
                        )
                        dm_embed.add_field(
                            name="🔗 Quick Actions",
                            value=(
                                f"• [Book Your Call]({BOOKING_LINK})\n"
                                "• Return to server to create new ticket"
                            ),
                            inline=False
                        )
                        dm_embed.set_footer(text=f"Server: {getattr(interaction.guild, 'name', 'Unknown')}")
                        
                        await interaction.user.send(embed=dm_embed)
                        logging.info(f"Sent DM notification to {interaction.user.name} about expired ticket")
                        
                    except discord.Forbidden:
                        logging.warning(f"Could not send DM to {interaction.user.name} - DMs disabled")
                    except Exception as e:
                        logging.error(f"Error sending DM to {interaction.user.name}: {e}")

                # Delete the ticket channel
                try:
                    await current_ticket.delete(reason="Verification ticket expired after 24 hours")
                    logging.info(f"Auto-deleted expired ticket for {interaction.user.name}")
                    
                    # Unregister ticket
                    if member_cog:
                        member_cog.unregister_ticket(interaction.user.id)
                        
                except Exception as e:
                    logging.error(f'Failed to delete expired ticket channel: {e}')
                
                # Log the auto-close
                await self.log_verification_event(
                    interaction.guild,
                    "⏰ Verification Ticket Auto-Closed",
                    f"Verification ticket for {interaction.user.mention} auto-closed after 24 hours (DM sent: {'Yes' if current_member else 'No - user left'})",
                    interaction.user,
                    discord.Color.orange()
                )
                
            except Exception as e:
                logging.error(f"Error in auto-close for {interaction.user.name}: {e}")

        asyncio.create_task(auto_close())

        # Let them know
        await interaction.followup.send(
            f"✅ Your verification ticket is ready: {ticket_channel.mention}",
            ephemeral=True
        )

    async def log_verification_event(self, guild, title, description, user, color):
        """Log verification events to the logs channel"""
        if not guild:
            return
            
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
                embed.set_footer(text=f"Guild: {guild.name}")
                
                try:
                    await logs_channel.send(embed=embed)
                except Exception as e:
                    logging.error(f"Failed to send log message: {e}")

class ConfirmBookingView(discord.ui.View):
    def __init__(self, authorized_user, ticket_channel_id):
        super().__init__(timeout=None)
        self.authorized_user = authorized_user
        self.ticket_channel_id = ticket_channel_id

    @discord.ui.button(label="I Have Booked", style=discord.ButtonStyle.green, emoji="✅")
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # SECURITY: Check authorized user and guild context
        if not interaction.guild:
            return await interaction.response.send_message(
                "❌ This command can only be used in a server, not in DMs!",
                ephemeral=True
            )
            
        if interaction.user.id != self.authorized_user.id:
            return await interaction.response.send_message(
                "❌ Only the person who started this verification can use this button!",
                ephemeral=True
            )
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Get the member management cog to restore roles
            member_cog = getattr(getattr(interaction, 'client', None), 'get_cog', lambda name: None)('MemberManagement')
            if member_cog:
                await interaction.followup.send(
                    "⏳ Please wait while we restore your subscription roles and double-check your access. This may take up to 2 minutes...",
                    ephemeral=True
                )
                restored_roles = await member_cog.restore_member_roles(interaction.user)
                
                # Refresh the member object to get latest roles
                member = None
                if interaction.guild and hasattr(interaction.guild, 'get_member'):
                    member = interaction.guild.get_member(interaction.user.id)
                
                subscription_role_ids = set([role.id for role in restored_roles]) if restored_roles else set()
                user_role_ids = {role.id for role in member.roles} if member else set()
                missing_roles = subscription_role_ids - user_role_ids
                
                if restored_roles and not missing_roles:
                    role_names = [role.name for role in restored_roles]
                    await interaction.followup.send(
                        f"✅ Verification complete! Your subscription roles have been restored: {', '.join(role_names)}\n\n"
                        "We will continue to monitor your access for a short period to ensure no other bot removes your roles.", 
                        ephemeral=True
                    )
                    
                    # Schedule a DM after 20 seconds to congratulate the user
                    async def send_verified_dm():
                        await asyncio.sleep(20)
                        try:
                            dm_embed = discord.Embed(
                                title="🎉 You Are Verified!",
                                description="You now have full access to the server. Enjoy your stay and make the most of your subscription!",
                                color=discord.Color.green()
                            )
                            dm_embed.set_footer(text=f"Server: {getattr(interaction.guild, 'name', 'Unknown')}")
                            await interaction.user.send(embed=dm_embed)
                        except Exception as e:
                            logging.warning(f"Could not send verification DM to {interaction.user.name}: {e}")
                    asyncio.create_task(send_verified_dm())
                elif restored_roles and missing_roles:
                    await interaction.followup.send(
                        f"⚠️ We tried to restore your roles, but some roles could not be added: {', '.join(str(rid) for rid in missing_roles)}. Please contact an admin for help",
                        ephemeral=True
                    )
                    await self.log_verification_event(
                        interaction.guild,
                        "❌ Verification Role Restoration Failed",
                        f"{interaction.user.mention} did not receive all subscription roles after verification retries. Manual intervention required.",
                        interaction.user,
                        discord.Color.red(),
                        restored_roles
                    )
                else:
                    await interaction.followup.send("✅ Verification complete! No roles to restore.", ephemeral=True)
            # For deleting the ticket channel, use interaction.channel (the current ticket channel)
            channel_to_delete = getattr(interaction, 'channel', None)
            if channel_to_delete and hasattr(channel_to_delete, 'delete'):
                try:
                    await asyncio.sleep(5)
                    await channel_to_delete.delete()
                except Exception as e:
                    logging.error(f'Failed to delete ticket channel: {e}')
            logging.info(f"Closed verification ticket for {interaction.user.name}")
        
        except discord.Forbidden:
            logging.error(f"Permission error during role restoration for {interaction.user.name}")
            await interaction.followup.send("❌ Bot lacks required permissions to restore roles", ephemeral=True)
            # Log failed verification
            await self.log_verification_event(
                interaction.guild,
                "❌ Verification Failed",
                f"Permission error during verification for {interaction.user.mention}",
                interaction.user,
                discord.Color.red()
            )
        except Exception as e:
            logging.error(f"Error in verification process for {interaction.user.name}: {e}")
            await interaction.followup.send("❌ Error during verification process", ephemeral=True)
            # Log failed verification
            await self.log_verification_event(
                interaction.guild,
                "❌ Verification Failed",
                f"Error during verification for {interaction.user.mention}: {str(e)}",
                interaction.user,
                discord.Color.red()
            )

    async def log_verification_event(self, guild, title, description, user, color, restored_roles=None):
        """Log verification events to the logs channel"""
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
                
                if restored_roles:
                    roles_text = ", ".join([role.name for role in restored_roles]) if restored_roles else "None"
                    embed.add_field(name="Restored Subscription Roles", value=roles_text, inline=False)
                
                embed.set_footer(text=f"Guild: {guild.name}")
                
                try:
                    await logs_channel.send(embed=embed)
                except Exception as e:
                    logging.error(f"Failed to send log message: {e}")

class Verification(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.booking_link = BOOKING_LINK

    @app_commands.command(name="setup_logs", description="Set a channel as verification logs channel")
    @app_commands.default_permissions(administrator=True)
    async def setup_logs(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Set a channel as verification logs channel"""
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
        
        # Validate channel permissions
        if not channel.permissions_for(interaction.guild.me).send_messages:
            return await interaction.response.send_message(
                "❌ Bot doesn't have permission to send messages in that channel!",
                ephemeral=True
            )
        
        embed = discord.Embed(
            title="📋 Logs Channel Setup",
            description=(
                f"To set {channel.mention} as the logs channel, update your `.env` file:\n\n"
                f"\nLOGS_CHANNEL_ID = {channel.id}\n\n\n"
                f"Then restart the bot for changes to take effect."
            ),
            color=discord.Color.blue()
        )
        embed.add_field(name="Selected Channel", value=channel.mention, inline=True)
        embed.add_field(name="Channel ID", value=f"`{channel.id}`", inline=True)
        
        current_logs_id_env = os.getenv('LOGS_CHANNEL_ID')
        current_logs_id = safe_int_convert(current_logs_id_env) if current_logs_id_env else None
        current_logs_channel = f"<#{current_logs_id}>" if current_logs_id else "Not set"
        embed.add_field(name="Current Logs Channel", value=current_logs_channel, inline=True)
        
        # Test if bot can send messages to the channel
        try:
            test_embed = discord.Embed(
                title="🧪 Test Log Message",
                description="This is a test message to verify the bot can send logs here.",
                color=discord.Color.green(),
                timestamp=datetime.now(timezone.utc)
            )
            test_embed.set_footer(text="Test message - you can delete this")
            
            await channel.send(embed=test_embed)
            embed.add_field(name="✅ Test Result", value="Bot can send messages to this channel", inline=False)
            
        except Exception as e:
            embed.add_field(name="❌ Test Result", value=f"Bot cannot send messages: {e}", inline=False)
            embed.color = discord.Color.red()
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="set_booking_link", description="Set the booking link for verification")
    @app_commands.default_permissions(administrator=True)
    async def set_booking_link(self, interaction: discord.Interaction, url: str):
        """Set the booking link for verification"""
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
        
        # Basic URL validation
        if not url.startswith(('http://', 'https://')):
            return await interaction.response.send_message(
                "❌ Please provide a valid URL starting with http:// or https://",
                ephemeral=True
            )
        
        global BOOKING_LINK
        self.booking_link = url
        BOOKING_LINK = url
        
        await interaction.response.send_message(f"✅ Booking link updated to: {url}", ephemeral=True)

    @app_commands.command(name="reload_cogs", description="Reload all bot cogs")
    @app_commands.default_permissions(administrator=True)
    async def reload_cogs(self, interaction: discord.Interaction):
        """Reload all bot cogs"""
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
        
        cogs = ["cogs.verification", "cogs.member_management", "cogs.welcome"]
        results = []
        
        for cog in cogs:
            try:
                await self.bot.reload_extension(cog)
                results.append(f"✅ {cog} reloaded")
                logging.info(f"Admin {interaction.user.name} reloaded cog: {cog}")
            except Exception as e:
                results.append(f"❌ {cog} failed: {str(e)[:50]}")
                logging.error(f"Failed to reload {cog}: {e}")
        
        await interaction.followup.send("\n".join(results), ephemeral=True)

    @app_commands.command(name="verification_stats", description="Show verification statistics")
    @app_commands.default_permissions(administrator=True)
    async def verification_stats(self, interaction: discord.Interaction):
        """Show verification statistics"""
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
        
        member_cog = self.bot.get_cog('MemberManagement')
        if not member_cog:
            await interaction.response.send_message("❌ MemberManagement cog not loaded.", ephemeral=True)
            return
            
        total_pending = len(getattr(member_cog, 'member_original_roles', {}))
        total_failed = sum(1 for v in getattr(member_cog, 'failed_verification_logged', {}).values() if v)
        total_verified = getattr(member_cog, 'total_verified', 0)
        
        embed = discord.Embed(
            title="📊 Verification Stats",
            color=discord.Color.blue(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Pending Verifications", value=str(total_pending), inline=True)
        embed.add_field(name="Failed Verifications", value=str(total_failed), inline=True)
        embed.add_field(name="Completed Verifications", value=str(total_verified), inline=True)
        embed.set_footer(text=f"Requested by {interaction.user.name}")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Verification(bot))