import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View
import os
import logging
import asyncio
from datetime import datetime, timezone, timedelta

class VerificationView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Start Verification",
        style=discord.ButtonStyle.green,
        custom_id="verify_button",
        emoji="🔒"
    )
    async def verify_button(self, interaction: discord.Interaction, button: discord.Button):
        await interaction.response.defer(ephemeral=True)

        # Check if user already has any of the subscription roles
        subscription_roles = {
            int(os.getenv('LAUNCHPAD_ROLE_ID')),  # $98/mo role
            int(os.getenv('MEMBER_ROLE_ID'))      # Free role
        }
        user_roles = {r.id for r in interaction.user.roles}

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
        member_cog = interaction.client.get_cog('MemberManagement')
        if not member_cog or interaction.user.id not in member_cog.member_original_roles:
            return await interaction.followup.send(
                embed=discord.Embed(
                    title="❌ No Subscription Found",
                    description="You don't have any subscription roles that need verification. Please purchase a subscription first.",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )

        # Prevent duplicate tickets
        ticket_name = f"verify-{interaction.user.name.lower()}"
        existing = discord.utils.get(interaction.guild.channels, name=ticket_name)
        if existing:
            close_ts = int((datetime.now(timezone.utc) + timedelta(seconds=20)).timestamp())
            await interaction.followup.send(
                embed=discord.Embed(
                    title="🎫 Active Ticket Found",
                    description=(
                        f"You already have an active verification ticket: {existing.mention}\n"
                        f"This message will auto-close <t:{close_ts}:R>"
                    ),
                    color=discord.Color.yellow()
                ),
                ephemeral=True
            )
            # Schedule deletion in 20s
            await asyncio.sleep(20)
            try:
                await existing.delete()
                logging.info(f"Deleted duplicate ticket for {interaction.user}")
            except Exception as e:
                logging.warning(f"Could not delete duplicate ticket: {e}")
            return

        # Create the ticket channel under same category
        ticket_channel = await interaction.guild.create_text_channel(
            name=ticket_name,
            category=interaction.channel.category
        )

        # Lock it down: only the user can see/send
        await ticket_channel.set_permissions(interaction.user, read_messages=True, send_messages=True)
        await ticket_channel.set_permissions(interaction.guild.default_role, read_messages=False)

        # Get user's subscription info
        stored_role_ids = member_cog.member_original_roles[interaction.user.id]
        subscription_info = []
        for role_id in stored_role_ids:
            if role_id == int(os.getenv('LAUNCHPAD_ROLE_ID')):
                subscription_info.append("🚀 Launchpad ($98/mo)")
            elif role_id == int(os.getenv('MEMBER_ROLE_ID')):
                subscription_info.append("👤 Member (Free)")

        # Send the welcome embed with booking CTA
        expiry = datetime.now(timezone.utc) + timedelta(hours=24)
        exp_ts = int(expiry.timestamp())
        embed = discord.Embed(
            title="🎉 Welcome to Your Verification Process!",
            description=(
                "To complete your verification and gain access to your subscription, please follow these steps:\n\n"
                "# 📅 STEP 1: BOOK YOUR CALL\n"
                f"## 👉 [**CLICK HERE TO BOOK YOUR ONBOARDING CALL**]({os.getenv('CALENDLY_LINK')}) 👈\n\n"
                "**2.** After booking, click the 'I Have Booked' button below\n\n"
                f"**Note:** This ticket closes <t:{exp_ts}:R>"
            ),
            color=discord.Color.green()
        )
        embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1370122090631532655/1377305621044531290/1228868654c7a053f79777f7b16ff623.png")
        embed.add_field(name="📅 Booking Status", value="Pending", inline=True)
        embed.add_field(name="⏱️ Expires", value=f"<t:{exp_ts}:f>", inline=True)
        embed.add_field(name="🎯 Subscription", value="\n".join(subscription_info), inline=False)
        embed.set_footer(text=f"User ID: {interaction.user.id}")

        await ticket_channel.send(
            f"Welcome {interaction.user.mention}! Let's verify your subscription access.",
            embed=embed,
            view=ConfirmBookingView(interaction.user)
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
                # Send DM to user before closing ticket
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
                            f"• [Book Your Call]({os.getenv('CALENDLY_LINK')})\n"
                            "• Return to server to create new ticket"
                        ),
                        inline=False
                    )
                    dm_embed.set_footer(text=f"Server: {interaction.guild.name}")
                    
                    await interaction.user.send(embed=dm_embed)
                    logging.info(f"Sent DM notification to {interaction.user.name} about expired ticket")
                    
                except discord.Forbidden:
                    logging.warning(f"Could not send DM to {interaction.user.name} - DMs disabled")
                except Exception as e:
                    logging.error(f"Error sending DM to {interaction.user.name}: {e}")

                # Delete the ticket channel
                await ticket_channel.delete()
                
                # Log the auto-close
                await self.log_verification_event(
                    interaction.guild,
                    "⏰ Verification Ticket Auto-Closed",
                    f"Verification ticket for {interaction.user.mention} auto-closed after 24 hours (DM sent)",
                    interaction.user,
                    discord.Color.orange()
                )
                logging.info(f"Auto-closed verification ticket for {interaction.user}")
                
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
    def __init__(self, authorized_user):
        super().__init__(timeout=None)
        self.authorized_user = authorized_user

    @discord.ui.button(label="I Have Booked", style=discord.ButtonStyle.green, emoji="✅")
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check if the person clicking is the authorized user
        if interaction.user.id != self.authorized_user.id:
            return await interaction.response.send_message(
                "❌ Only the person who started this verification can use this button!",
                ephemeral=True
            )
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Get the member management cog to restore roles
            member_cog = interaction.client.get_cog('MemberManagement')
            if member_cog:
                restored_roles = await member_cog.restore_member_roles(interaction.user)
                
                if restored_roles:
                    role_names = [role.name for role in restored_roles]
                    # Log successful verification
                    await self.log_verification_event(
                        interaction.guild,
                        "✅ Subscription Verification Completed",
                        f"{interaction.user.mention} completed verification - restored: {', '.join(role_names)}",
                        interaction.user,
                        discord.Color.green(),
                        restored_roles
                    )
                    
                    await interaction.followup.send(f"✅ Verification complete! Your subscription roles have been restored: {', '.join(role_names)}", ephemeral=True)
                else:
                    await interaction.followup.send("✅ Verification complete! No roles to restore.", ephemeral=True)
            
            # Close ticket channel
            await asyncio.sleep(5)
            await interaction.channel.delete()
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

    @app_commands.command(name="setup_logs", description="Set a channel as verification logs channel")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(channel="The channel to use for verification logs")
    async def setup_logs(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Set a channel as verification logs channel"""
        
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
        embed.add_field(name="Current Logs Channel", value=f"<#{os.getenv('LOGS_CHANNEL_ID')}>" if os.getenv('LOGS_CHANNEL_ID') else "Not set", inline=True)
        
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

async def setup(bot):
    await bot.add_cog(Verification(bot))