import discord
from discord import app_commands
from discord.ext import commands
import os
from cogs.bypass_manager import bypass_manager

OWNER_USER_IDS = {890323443252351046, 879714530769391686}
GUILD_ID = int(os.getenv('GUILD_ID', 0))

def is_authorized_guild_or_owner(interaction):
    if interaction.guild and interaction.guild.id == GUILD_ID:
        return True
    if interaction.user.id in OWNER_USER_IDS:
        return True
    return False

@app_commands.command(name="remove_bypass_role", description="Remove a role from the verification bypass list")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(role="The role to remove from bypass list")
async def remove_bypass_role(interaction: discord.Interaction, role: str):
    if not is_authorized_guild_or_owner(interaction):
        return await interaction.response.send_message(
            "❌ You are not authorized to use this command.", ephemeral=True
        )
    # SECURITY: Block DMs and check admin permissions
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server!", ephemeral=True)
    if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ You need Administrator permissions!", ephemeral=True)
    # Convert role ID string to role object
    try:
        role_id = int(role)
    except Exception:
        return await interaction.response.send_message("❌ Invalid role selected!", ephemeral=True)
    role_obj = interaction.guild.get_role(role_id)
    if not role_obj:
        return await interaction.response.send_message("❌ Role not found!", ephemeral=True)
    # Check if role is in bypass list
    if role_id not in bypass_manager.get_bypass_roles():
        return await interaction.response.send_message(
            f"❌ Role **{role_obj.name}** is not in the bypass list!",
            ephemeral=True
        )
    # Remove role from bypass list
    success = bypass_manager.remove_bypass_role(role_id)
    if success:
        embed = discord.Embed(
            title="✅ Bypass Role Removed",
            description=f"Role **{role_obj.name}** has been removed from the verification bypass list.",
            color=discord.Color.red()
        )
        embed.add_field(name="Role", value=role_obj.mention, inline=True)
        embed.add_field(name="Role ID", value=f"`{role_obj.id}`", inline=True)
        embed.add_field(
            name="Effect", 
            value="Users with this role will now need to verify", 
            inline=False
        )
        # Optionally log the action (if you want to import log_member_event, do so)
        await interaction.response.send_message(embed=embed, ephemeral=True)

@remove_bypass_role.autocomplete('role')
async def remove_bypass_role_autocomplete(interaction: discord.Interaction, current: str):
    # Only suggest roles that are in the bypass list
    bypass_role_ids = set(bypass_manager.get_bypass_roles())
    if not interaction.guild:
        return []
    suggestions = []
    for role in interaction.guild.roles:
        if role.id in bypass_role_ids and current.lower() in role.name.lower():
            suggestions.append(app_commands.Choice(name=role.name, value=str(role.id)))
            if len(suggestions) >= 20:
                break
    return suggestions

async def setup(bot: commands.Bot):
    bot.tree.add_command(remove_bypass_role) 