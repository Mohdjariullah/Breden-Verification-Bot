import discord
from discord import app_commands
from discord.ext import commands
import os
import io
import json
import json as pyjson

UNVERIFIED_FILE = 'unverified_users.json'

OWNER_USER_IDS = {890323443252351046, 879714530769391686}
GUILD_ID = int(os.getenv('GUILD_ID', 0))

def is_authorized_guild_or_owner(interaction):
    if interaction.guild and interaction.guild.id == GUILD_ID:
        return True
    if interaction.user.id in OWNER_USER_IDS:
        return True
    return False

def get_env_role_id(var_name):
    env_value = os.getenv(var_name)
    if env_value is None:
        raise ValueError(f"Environment variable '{var_name}' is not set")
    return int(env_value)

def load_unverified():
    try:
        with open(UNVERIFIED_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return {}

def save_unverified(data):
    with open(UNVERIFIED_FILE, 'w') as f:
        json.dump(data, f, indent=2)

@app_commands.command(name="mass_verify_unverified", description="Mass-verify all users with the Unverified role and send a JSON report to logs.")
@app_commands.default_permissions(administrator=True)
async def mass_verify_unverified(interaction: discord.Interaction):
    if not is_authorized_guild_or_owner(interaction):
        return await interaction.response.send_message(
            "❌ You are not authorized to use this command.", ephemeral=True
        )
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server!", ephemeral=True)
    if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ You need Administrator permissions!", ephemeral=True)
    await interaction.response.defer(ephemeral=True)

    guild = interaction.guild
    UNVERIFIED_ROLE_ID = int(os.getenv('UNVERIFIED_ROLE_ID', 0))
    unverified_role = guild.get_role(UNVERIFIED_ROLE_ID)
    member_role_id = get_env_role_id('MEMBER_ROLE_ID')
    if member_role_id is None:
        return await interaction.followup.send("❌ MEMBER_ROLE_ID is not set!", ephemeral=True)
    member_role = guild.get_role(member_role_id)
    if not unverified_role or not member_role:
        return await interaction.followup.send("❌ Unverified or Member role not found! Check your environment variables.", ephemeral=True)

    unverified_users = load_unverified()
    affected = []
    to_remove_from_json = []
    for member in guild.members:
        if unverified_role in member.roles:
            # Prepare report entry
            user_entry = {
                "user_id": member.id,
                "username": str(member),
                "original_roles": unverified_users.get(str(member.id), {}).get("original_roles", [])
            }
            affected.append(user_entry)
            # Add Member role, remove Unverified
            try:
                await member.add_roles(member_role, reason="Mass verification by admin command")
            except Exception as e:
                print(f"Could not add Member role to {member}: {e}")
            try:
                await member.remove_roles(unverified_role, reason="Mass verification by admin command")
            except Exception as e:
                print(f"Could not remove Unverified role from {member}: {e}")
            # Remove from JSON
            if str(member.id) in unverified_users:
                to_remove_from_json.append(str(member.id))
    # Clean up JSON
    for uid in to_remove_from_json:
        del unverified_users[uid]
    save_unverified(unverified_users)

    # Prepare JSON file for logs
    json_bytes = pyjson.dumps(affected, indent=2).encode('utf-8')
    json_file = discord.File(io.BytesIO(json_bytes), filename="mass_verified_unverified_users.json")

    # Send to logs channel
    logs_channel_id = os.getenv('LOGS_CHANNEL_ID')
    logs_channel = guild.get_channel(int(logs_channel_id)) if logs_channel_id else None
    # Only send if logs_channel is a TextChannel
    embed = discord.Embed(
        title="✅ Mass Verified Unverified Users",
        description=f"{len(affected)} users were given the Member role and removed from Unverified." if affected else "No users with the Unverified role were found.",
        color=discord.Color.green()
    )
    if affected:
        embed.add_field(
            name="Users Updated",
            value="\n".join([f"<@{u['user_id']}>" for u in affected][:10]) +
                  (f"\n...and {len(affected)-10} more" if len(affected) > 10 else ""),
            inline=False
        )
    if logs_channel and isinstance(logs_channel, discord.TextChannel):
        await logs_channel.send(embed=embed, file=json_file)
    await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot):
    bot.tree.add_command(mass_verify_unverified) 