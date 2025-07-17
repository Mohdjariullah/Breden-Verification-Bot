import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import os
import logging

# Helper to get environment role IDs
def get_env_role_id(var_name):
    env_value = os.getenv(var_name)
    if env_value is None:
        raise ValueError(f"Environment variable '{var_name}' is not set")
    return int(env_value)

OWNER_USER_IDS = {890323443252351046, 879714530769391686}
GUILD_ID = int(os.getenv('GUILD_ID', 0))

def is_authorized_guild_or_owner(interaction):
    if interaction.guild and interaction.guild.id == GUILD_ID:
        return True
    if interaction.user.id in OWNER_USER_IDS:
        return True
    return False

@app_commands.command(name="test_vip_join", description="Test VIP user join with automatic Member role assignment")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(user="The user to test VIP join with")
async def test_vip_join(interaction: discord.Interaction, user: discord.Member):
    if not is_authorized_guild_or_owner(interaction):
        return await interaction.response.send_message(
            "❌ You are not authorized to use this command.", ephemeral=True
        )
    # SECURITY: Block DMs and check admin permissions
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server!", ephemeral=True)
    if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ You need Administrator permissions!", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    # Get role IDs
    launchpad_role_id = get_env_role_id('LAUNCHPAD_ROLE_ID')
    member_role_id = get_env_role_id('MEMBER_ROLE_ID')
    # Check current roles
    current_roles = [role.name for role in user.roles]
    current_role_ids = {role.id for role in user.roles}
    embed = discord.Embed(
        title="🧪 VIP Join Test",
        description=f"Testing VIP join functionality for {user.mention}",
        color=discord.Color.blue()
    )
    embed.add_field(name="Current Roles", value=", ".join(current_roles) if current_roles else "None", inline=False)
    embed.add_field(name="VIP Role ID", value=str(launchpad_role_id) if launchpad_role_id else "Not set", inline=True)
    embed.add_field(name="Member Role ID", value=str(member_role_id) if member_role_id else "Not set", inline=True)
    # Simulate VIP join by adding VIP role first
    if not launchpad_role_id:
        await interaction.followup.send("❌ VIP role ID not configured!", ephemeral=True)
        return
    vip_role = interaction.guild.get_role(launchpad_role_id)
    if not vip_role:
        await interaction.followup.send("❌ VIP role not found!", ephemeral=True)
        return
    try:
        # Add VIP role to simulate Whop integration
        await user.add_roles(vip_role, reason="Test VIP join simulation")
        embed.add_field(name="✅ VIP Role Added", value="Simulated Whop integration", inline=False)
        # Wait a moment then trigger the join logic
        await asyncio.sleep(2)
        # Call the join logic manually (simulate on_member_join)
        # You may want to import and call the actual logic if needed
        # For now, just log and show roles
        updated_roles = [role.name for role in user.roles]
        updated_role_ids = {role.id for role in user.roles}
        embed.add_field(name="After Processing", value=", ".join(updated_roles) if updated_roles else "None", inline=False)
        # Check if Member role was automatically added
        if member_role_id in updated_role_ids:
            embed.add_field(name="🎁 Member Role", value="✅ Automatically added to VIP user", inline=True)
        else:
            embed.add_field(name="🎁 Member Role", value="❌ Not automatically added", inline=True)
        # Check if roles are being monitored (optional, if you want to import tracking logic)
        # Check stored roles (optional)
        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        error_embed = discord.Embed(
            title="❌ VIP Join Test Failed",
            description=f"Error during test: {str(e)}",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=error_embed, ephemeral=True)
        logging.error(f"VIP join test failed for {user.name}: {e}")

async def setup(bot: commands.Bot):
    bot.tree.add_command(test_vip_join) 