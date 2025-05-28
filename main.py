import sys
import subprocess
import pkg_resources
import logging
import discord
from discord.ext import commands
import asyncio
from dotenv import load_dotenv
import os

def check_and_install_requirements():
    try:
        with open('requirements.txt') as f:
            requirements = [line.strip() for line in f if line.strip()]
        
        installed = {pkg.key for pkg in pkg_resources.working_set}
        missing = []
        
        for requirement in requirements:
            pkg_name = requirement.split('>=')[0]
            if pkg_name.lower() not in installed:
                missing.append(requirement)
        
        if missing:
            print("Installing missing packages...")
            subprocess.check_call([sys.executable, '-m', 'pip', 'install'] + missing)
            print("All required packages installed successfully!")
        else:
            print("All required packages already installed!")
            
    except Exception as e:
        print(f"Error checking/installing packages: {e}")
        sys.exit(1)

# Run the check at startup
check_and_install_requirements()

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(
    filename='bot.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Set up intents
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True
intents.guild_messages = True

class BredenBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=intents)
        
    async def setup_hook(self):
        print("Loading cogs...")
        
        # Load all cogs
        try:
            await self.load_extension('cogs.verification')
            print("✅ Loaded verification cog")
        except Exception as e:
            print(f"❌ Failed to load verification cog: {e}")
            
        try:
            await self.load_extension('cogs.member_management')
            print("✅ Loaded member_management cog")
        except Exception as e:
            print(f"❌ Failed to load member_management cog: {e}")
            
        try:
            await self.load_extension('cogs.welcome')
            print("✅ Loaded welcome cog")
        except Exception as e:
            print(f"❌ Failed to load welcome cog: {e}")
        
        print("Syncing slash commands...")
        
        # Sync commands globally
        try:
            synced = await self.tree.sync()
            print(f"✅ Synced {len(synced)} slash commands globally")
            for cmd in synced:
                print(f"  - /{cmd.name}")
        except Exception as e:
            print(f"❌ Failed to sync commands: {e}")

    async def on_ready(self):
        print(f"🤖 Bot is online as {self.user}")
        print(f"📊 Connected to {len(self.guilds)} guilds")
        
        # List all available slash commands
        print("\n📋 Available slash commands:")
        for command in self.tree.get_commands():
            print(f"  /{command.name} - {command.description}")
        
        await self.change_presence(
            status=discord.Status.online,
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="for new members to verify"
            )
        )
        logging.info(f"Bot started successfully as {self.user}")

    async def on_command_error(self, ctx, error):
        """Handle command errors"""
        if isinstance(error, commands.CommandNotFound):
            return
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You don't have permission to use this command!")
        else:
            print(f"Command error: {error}")
            logging.error(f"Command error: {error}")

    async def on_application_command_error(self, interaction: discord.Interaction, error):
        """Handle slash command errors"""
        if isinstance(error, discord.app_commands.MissingPermissions):
            await interaction.response.send_message("❌ You don't have permission to use this command!", ephemeral=True)
        else:
            print(f"Slash command error: {error}")
            logging.error(f"Slash command error: {error}")
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ An error occurred while processing this command.", ephemeral=True)

# Create bot instance
bot = BredenBot()

# Add a simple test command to verify slash commands work
@bot.tree.command(name="ping", description="Test if the bot is responding")
async def ping(interaction: discord.Interaction):
    """Simple ping command to test slash commands"""
    latency = round(bot.latency * 1000)
    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"Bot latency: {latency}ms",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

# Add this to main.py after the ping command
@bot.tree.command(name="debug", description="Debug information for admins")
@discord.app_commands.default_permissions(administrator=True)
async def debug(interaction: discord.Interaction):
    """Debug command to check bot status"""
    embed = discord.Embed(
        title="🔧 Debug Information",
        color=discord.Color.blue()
    )
    
    # Check cogs
    cogs_status = []
    for cog_name in ['Verification', 'MemberManagement', 'Welcome']:
        cog = bot.get_cog(cog_name)
        status = "✅ Loaded" if cog else "❌ Not loaded"
        cogs_status.append(f"{cog_name}: {status}")
    
    embed.add_field(name="Cogs Status", value="\n".join(cogs_status), inline=False)
    
    # Check commands
    commands = [cmd.name for cmd in bot.tree.get_commands()]
    embed.add_field(name="Slash Commands", value=", ".join(commands) if commands else "None", inline=False)
    
    # Check environment variables
    env_vars = []
    for var in ['GUILD_ID', 'WELCOME_CHANNEL_ID', 'LAUNCHPAD_ROLE_ID', 'MEMBER_ROLE_ID']:
        value = os.getenv(var)
        status = "✅ Set" if value else "❌ Missing"
        env_vars.append(f"{var}: {status}")
    
    embed.add_field(name="Environment Variables", value="\n".join(env_vars), inline=False)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

if __name__ == "__main__":
    print("🚀 Starting Breden Verification Bot...")
    try:
        bot.run(os.getenv('TOKEN'))
    except Exception as e:
        print(f"❌ Failed to start bot: {e}")
        logging.error(f"Failed to start bot: {e}")