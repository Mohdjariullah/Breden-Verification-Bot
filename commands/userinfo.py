import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
import discord.abc
import os

OWNER_USER_IDS = {890323443252351046, 879714530769391686}
GUILD_ID = int(os.getenv('GUILD_ID', 0))

def is_authorized_guild_or_owner(interaction):
    if interaction.guild and interaction.guild.id == GUILD_ID:
        return True
    if interaction.user.id in OWNER_USER_IDS:
        return True
    return False

# Discord badge emoji map (partial, can be extended)
BADGE_EMOJIS = {
    "staff": "<:discordstaff:1392224691661574194>",
    "partner": "<:discord_partner:112233445566778899>",
    "hypesquad": "<:hypesquadevents:1392224777669709925>",
    "hypesquad_bravery": "<:hypesquadbravery:1392224734200205472>",
    "hypesquad_brilliance": "<:hypesquadbrilliance:1392224753812639856>",
    "hypesquad_balance": "<:hypesquadbalance:1392224713702637598>",
    "early_supporter": "<:discordearlysupporter:1392224602738131184>",
    "verified_developer": "<:discordbotdev:1392224644483776685>",
    "active_developer": "<:activedev:1042545590640324608>",
    # Add more as needed
}


@app_commands.command(name="userinfo", description="Show detailed info about a user")
@app_commands.describe(user="The user to show info for (leave blank for yourself)")
async def userinfo(
    interaction: discord.Interaction, user: Optional[discord.Member] = None
):
    if not is_authorized_guild_or_owner(interaction):
        return await interaction.response.send_message(
            "❌ You are not authorized to use this command.", ephemeral=True
        )
    guild = interaction.guild
    if user is None:
        user = (
            interaction.user if isinstance(interaction.user, discord.Member) else None
        )
    if user is None or not isinstance(user, discord.Member):
        await interaction.response.send_message(
            "❌ Could not find member in this server.", ephemeral=True
        )
        return
    member = user
    # Always fetch the global user object for badges
    user_obj = await interaction.client.fetch_user(member.id)
    display_user = member
    if display_user is None:
        await interaction.response.send_message(
            "❌ Could not find user.", ephemeral=True
        )
        return
    embed = discord.Embed(
        title=f"User Information - {display_user}",
        color=(
            member.color
            if member and hasattr(member, "color")
            else discord.Color.blurple()
        ),
    )
    embed.set_author(name=str(display_user), icon_url=display_user.display_avatar.url)
    embed.set_thumbnail(url=display_user.display_avatar.url)
    # Global avatar
    if hasattr(display_user, "avatar") and display_user.avatar is not None:
        embed.add_field(
            name="Global Avatar",
            value=f"[Link]({display_user.avatar.url})",
            inline=True,
        )
    # Server avatar (if different)
    if member and member.display_avatar.url != (
        display_user.avatar.url
        if hasattr(display_user, "avatar") and display_user.avatar
        else ""
    ):
        embed.add_field(
            name="Server Avatar",
            value=f"[Link]({member.display_avatar.url})",
            inline=True,
        )
    # Mention and ID
    embed.add_field(name="Mention", value=display_user.mention, inline=True)
    embed.add_field(name="User ID", value=str(display_user.id), inline=True)
    # Bot/system
    bot_status = "Yes" if getattr(display_user, "bot", False) else "No"
    system_status = "Yes" if getattr(display_user, "system", False) else "No"
    embed.add_field(name="Bot?", value=bot_status, inline=True)
    embed.add_field(name="System?", value=system_status, inline=True)
    # For badges, use user_obj.public_flags and a flag-to-badge mapping
    flag_to_badge = {
        "active_developer": "<:activedeveloper:1392224621851443280>",
        "bot_http_interactions": "🤖",
        "bug_hunter": "<:bughunter:112233445566778899>",
        "bug_hunter_level_2": "<:bughunter2:112233445566778899>",
        "discord_certified_moderator": "<:certifiedmod:112233445566778899>",
        "early_supporter": "<:discordearlysupporter:1392224602738131184>",
        "early_verified_bot_developer": "<:discordbotdev:1392224644483776685>",
        "hypesquad": "<:hypesquadevents:1392224777669709925>",
        "hypesquad_balance": "<:hypesquadbalance:1392224713702637598>",
        "hypesquad_bravery": "<:hypesquadbravery:1392224734200205472>",
        "hypesquad_brilliance": "<:hypesquadbrilliance:1392224753812639856>",
        "partner": "<:discord_partner:112233445566778899>",
        "staff": "<:discordstaff:1392224691661574194>",
        "system": "<:system:112233445566778899>",
        "team_user": "<:teamuser:112233445566778899>",
        "verified_bot": "<:verifiedbot:112233445566778899>",
        "verified_bot_developer": "<:discordbotdev:1392224644483776685>",
        "spammer": "🚫",
    }
    badges = []
    flags = user_obj.public_flags
    for flag, emoji in flag_to_badge.items():
        if hasattr(flags, flag) and getattr(flags, flag):
            badges.append(emoji)
    embed.add_field(name="Badges", value=" ".join(badges) if badges else "None", inline=False)
    # Account info
    created_at = (
        getattr(display_user, "created_at", None)
        if isinstance(display_user, (discord.User, discord.Member))
        else None
    )
    if created_at is not None:
        embed.add_field(
            name="Account Created",
            value=f"<t:{int(created_at.timestamp())}:F> (<t:{int(created_at.timestamp())}:R>)",
            inline=True,
        )
    if member and hasattr(member, "joined_at") and member.joined_at is not None:
        embed.add_field(
            name="Joined Server",
            value=f"<t:{int(member.joined_at.timestamp())}:F> (<t:{int(member.joined_at.timestamp())}:R>)",
            inline=True,
        )
    # Nitro/boosting
    if member and hasattr(member, "premium_since") and member.premium_since is not None:
        embed.add_field(
            name="Server Booster",
            value=f"Since <t:{int(member.premium_since.timestamp())}:F>",
            inline=True,
        )
    # Roles
    if member:
        roles = [role for role in member.roles if role != member.guild.default_role]
        if roles:
            roles_sorted = sorted(roles, key=lambda r: r.position, reverse=True)
            roles_str = " ".join(role.mention for role in roles_sorted)
            embed.add_field(name=f"Roles [{len(roles)}]", value=roles_str, inline=False)
            # Top role
            embed.add_field(name="Top Role", value=member.top_role.mention, inline=True)
            # Hoist role
            hoist_role = next((role for role in roles_sorted if role.hoist), None)
            if hoist_role:
                embed.add_field(
                    name="Hoist Role", value=hoist_role.mention, inline=True
                )
        else:
            embed.add_field(name="Roles", value="None", inline=False)
    # Ephemeral for non-admins, public for admins
    is_admin = False
    if isinstance(interaction.user, discord.Member):
        is_admin = interaction.user.guild_permissions.administrator
    await interaction.response.send_message(embed=embed, ephemeral=not is_admin)


async def setup(bot: commands.Bot):
    bot.tree.add_command(userinfo)
