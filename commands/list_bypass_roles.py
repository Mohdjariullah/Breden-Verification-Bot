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

@app_commands.command(name="list_bypass_roles", description="List all roles that bypass verification")
@app_commands.default_permissions(administrator=True)
async def list_bypass_roles(interaction: discord.Interaction):
    if not is_authorized_guild_or_owner(interaction):
        return await interaction.response.send_message(
            "❌ You are not authorized to use this command.", ephemeral=True
        )
    # SECURITY: Block DMs and check admin permissions
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server!", ephemeral=True)
    if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ You need Administrator permissions!", ephemeral=True)
    bypass_roles = bypass_manager.get_bypass_roles()
    if not bypass_roles:
        embed = discord.Embed(
            title="📋 Bypass Roles List",
            description="No roles are currently set to bypass verification.",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="ℹ️ How to add bypass roles",
            value="Use `/add_bypass_role <role>` to add roles that skip verification",
            inline=False
        )
    else:
        embed = discord.Embed(
            title="📋 Bypass Roles List",
            description="\n".join([f"<@&{role_id}>" for role_id in bypass_roles]),
            color=discord.Color.blue()
        )
        embed.add_field(
            name="ℹ️ How to add bypass roles",
            value="Use `/add_bypass_role <role>` to add roles that skip verification",
            inline=False
        )
    embed.set_footer(text=f"Total Bypass Roles: {len(bypass_roles)}")
    await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot):
    bot.tree.add_command(list_bypass_roles) 