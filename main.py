import sys
import subprocess
import importlib.metadata  # Replace deprecated pkg_resources
import logging
import discord
from discord.ext import commands
import asyncio
from dotenv import load_dotenv
import os
from datetime import datetime, timezone

def check_and_install_requirements():
    """Check and install required packages using modern importlib.metadata"""
    try:
        with open('requirements.txt') as f:
            requirements = [line.strip() for line in f if line.strip()]
        
        # Use importlib.metadata instead of deprecated pkg_resources
        try:
            installed = {dist.metadata['name'].lower().replace('-', '_') for dist in importlib.metadata.distributions()}
        except Exception:
            # Fallback for older Python versions
            import pkg_resources
            installed = {pkg.key for pkg in pkg_resources.working_set}
        
        missing = []
        for requirement in requirements:
            pkg_name = requirement.split('>=')[0].lower().replace('-', '_')
            if pkg_name not in installed:
                missing.append(requirement)
        
        if missing:
            print("📦 Installing missing packages...")
            subprocess.check_call([sys.executable, '-m', 'pip', 'install'] + missing, 
                                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            print("✅ All required packages installed!")
        else:
            print("✅ All required packages already installed!")
            
    except Exception as e:
        print(f"❌ Error checking/installing packages: {e}")
        sys.exit(1)

# Run the check at startup
print("🔍 Checking dependencies...", end=" ")
check_and_install_requirements()

# Load environment variables
load_dotenv()

def setup_logging():
    """Setup clean, production-ready logging"""
    # Clear any existing handlers
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)-15s | %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # File handler
    file_handler = logging.FileHandler('bot.log', encoding='utf-8')
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    
    # Console handler (minimal output)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter('%(levelname)-8s | %(message)s'))
    console_handler.setLevel(logging.ERROR)  # Only errors to console
    
    # Setup root logger
    logging.basicConfig(
        level=logging.INFO,
        handlers=[file_handler, console_handler]
    )
    
    # Reduce discord.py logging noise
    logging.getLogger('discord').setLevel(logging.ERROR)
    logging.getLogger('discord.http').setLevel(logging.ERROR)
    logging.getLogger('discord.gateway').setLevel(logging.ERROR)

setup_logging()

# Set up intents
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True
intents.guild_messages = True

class AIdapticsWhopGatekeeper(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=intents)
        self.startup_time = datetime.now(timezone.utc)
        
    async def setup_hook(self):
        print("🔧 Loading cogs...", end=" ")
        try:
            await self.load_extension('cogs')
            print(f"✅ All cogs loaded successfully!")
            logging.info("All cogs loaded via cogs/__init__.py loader")
        except Exception as e:
            print(f"❌ Failed to load cogs: {e}")
            logging.error(f"Failed to load cogs: {e}")

        print("🔧 Loading commands...", end=" ")
        try:
            await self.load_extension('commands')
            print(f"✅ All commands loaded successfully!")
            logging.info("All commands loaded via commands/__init__.py loader")
        except Exception as e:
            print(f"❌ Failed to load commands: {e}")
            logging.error(f"Failed to load commands: {e}")
        
        print("🔄 Syncing commands...", end=" ")
        
        # Sync commands globally
        try:
            synced = await self.tree.sync()
            print(f"✅ Synced {len(synced)} slash commands")
            logging.info(f"Synced {len(synced)} slash commands globally")
        except Exception as e:
            print(f"❌ Failed to sync commands: {e}")
            logging.error(f"Failed to sync commands: {e}")

    async def on_ready(self):
        print(f"\n🤖 {self.user} is now online!")
        print(f"📊 Connected to {len(self.guilds)} guild(s)")
        print(f"👥 Serving {sum(guild.member_count or 0 for guild in self.guilds)} members")
        
        # Set custom status
        try:
            await self.change_presence(
                status=discord.Status.dnd,
                activity=discord.Activity(
                    type=discord.ActivityType.watching,
                    name="Gates of Server"
                )
            )
            print("✅ Status set: DND - Watching Gates of Server")
        except Exception as e:
            print(f"❌ Failed to set status: {e}")
        
        # Fixed deprecation warning here
        current_time = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        print(f"\n🚀 Bot fully initialized at {current_time} UTC")
        print("=" * 60)
        
        logging.info(f"Bot started successfully as {self.user}")

    async def on_command_error(self, ctx, error):
        """Handle command errors"""
        if isinstance(error, commands.CommandNotFound):
            return
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You don't have permission to use this command!")
        else:
            logging.error(f"Command error: {error}")

    async def on_application_command_error(self, interaction, error):
        """Handle slash command errors"""
        error_id = f"ERR_{hash(str(error)) % 10000:04d}"
        
        if isinstance(error, discord.app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ You don't have permission to use this command!", 
                ephemeral=True
            )
        else:
            logging.error(f"Slash command error [{error_id}]: {error}")
            
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        f"❌ An error occurred. Error ID: `{error_id}`", 
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        f"❌ An error occurred. Error ID: `{error_id}`", 
                        ephemeral=True
                    )
            except:
                pass

# Create bot instance
bot = AIdapticsWhopGatekeeper()

# Add a simple test command
@bot.tree.command(name="ping", description="Test if the bot is responding")
async def ping(interaction):
    """Simple ping command"""
    if not interaction.guild:
        return await interaction.response.send_message(
            "❌ This command can only be used in a server!", 
            ephemeral=True
        )
    
    latency = round(bot.latency * 1000)
    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"Bot latency: {latency}ms",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="debug", description="Debug information for admins")
@discord.app_commands.default_permissions(administrator=True)
async def debug(interaction):
    """Debug command to check bot status"""
    if not interaction.guild:
        return await interaction.response.send_message(
            "❌ This command can only be used in a server!", 
            ephemeral=True
        )
    
    # Check admin permissions
    if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message(
            "❌ You need Administrator permissions to use this command!",
            ephemeral=True
        )
    
    embed = discord.Embed(
        title="🔧 Debug Information",
        color=discord.Color.blue()
    )
    
    # Check cogs
    cogs_status = []
    expected_cogs = ['Verification', 'MemberManagement', 'Welcome']
    for cog_name in expected_cogs:
        cog = bot.get_cog(cog_name)
        status = "✅ Loaded" if cog else "❌ Not loaded"
        cogs_status.append(f"{cog_name}: {status}")
    
    embed.add_field(name="Cogs Status", value="\n".join(cogs_status), inline=False)
    
    # Check commands
    commands = [cmd.name for cmd in bot.tree.get_commands()]
    embed.add_field(
        name="Slash Commands", 
        value=f"{len(commands)} commands loaded", 
        inline=False
    )
    
    # Check environment variables (safely)
    env_vars = []
    required_vars = ['GUILD_ID', 'WELCOME_CHANNEL_ID', 'LAUNCHPAD_ROLE_ID', 'MEMBER_ROLE_ID', 'LOGS_CHANNEL_ID']
    for var in required_vars:
        value = os.getenv(var)
        status = "✅ Set" if value else "❌ Missing"
        env_vars.append(f"{var}: {status}")
    
    embed.add_field(name="Environment Variables", value="\n".join(env_vars), inline=False)
    
    # Bot stats
    uptime = datetime.now(timezone.utc) - bot.startup_time
    embed.add_field(
        name="Bot Stats", 
        value=f"Uptime: {str(uptime).split('.')[0]}\nLatency: {round(bot.latency * 1000)}ms", 
        inline=False
    )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

if __name__ == "__main__":
    print("🚀 Starting AIdaptics Whop Gatekeeper...")
    print("=" * 60)
    
    token = os.getenv('TOKEN')
    if not token:
        print("❌ CRITICAL ERROR: TOKEN environment variable is not set!")
        print("   Please check your .env file and ensure TOKEN is properly configured.")
        logging.error("Bot startup failed: TOKEN environment variable missing")
        input("Press Enter to exit...")
        sys.exit(1)
    
    try:
        bot.run(token, log_handler=None)  # Disable discord.py's default logging
    except discord.LoginFailure:
        print("❌ CRITICAL ERROR: Invalid bot token!")
        print("   Please check your TOKEN in the .env file.")
        logging.error("Bot startup failed: Invalid token")
    except Exception as e:
        print(f"❌ CRITICAL ERROR: Failed to start bot: {e}")
        logging.error(f"Bot startup failed: {e}")
    finally:
        print("\n👋 Bot shutdown complete.")
        input("Press Enter to exit...")