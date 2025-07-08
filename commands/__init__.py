import logging
from discord.ext import commands
import importlib

from .add_bypass_role import setup as setup_add_bypass_role
from .remove_bypass_role import setup as setup_remove_bypass_role
from .list_bypass_roles import setup as setup_list_bypass_roles
from .help_admin import setup as setup_help_admin
from .cleanup_tracking import setup as setup_cleanup_tracking
from .debug_roles import setup as setup_debug_roles
from .force_verify import setup as setup_force_verify
from .check_stored_roles import setup as setup_check_stored_roles
from .test_member_join import setup as setup_test_member_join
from .test_vip_join import setup as setup_test_vip_join
from .mass_verify_unverified import setup as setup_mass_verify_unverified
from .setup_permissions import setup as setup_setup_permissions
from .restore_permissions import setup as setup_restore_permissions
from .refresh_welcome import setup as setup_refresh_welcome
from .userinfo import setup as setup_userinfo
from .debug_logs import setup as setup_debug_logs

async def setup(bot: commands.Bot) -> None:
    """Add admin commands to the bot."""
    logger = logging.getLogger(__name__)
    msg = "Loaded commands.{}"
    await setup_add_bypass_role(bot)
    logger.debug(msg.format("add_bypass_role"))
    await setup_remove_bypass_role(bot)
    logger.debug(msg.format("remove_bypass_role"))
    await setup_list_bypass_roles(bot)
    logger.debug(msg.format("list_bypass_roles"))
    await setup_help_admin(bot)
    logger.debug(msg.format("help_admin"))
    await setup_cleanup_tracking(bot)
    logger.debug(msg.format("cleanup_tracking"))
    await setup_debug_roles(bot)
    logger.debug(msg.format("debug_roles"))
    await setup_force_verify(bot)
    logger.debug(msg.format("force_verify"))
    await setup_check_stored_roles(bot)
    logger.debug(msg.format("check_stored_roles"))
    await setup_test_member_join(bot)
    logger.debug(msg.format("test_member_join"))
    await setup_test_vip_join(bot)
    logger.debug(msg.format("test_vip_join"))
    await setup_mass_verify_unverified(bot)
    logger.debug(msg.format("mass_verify_unverified"))
    await setup_setup_permissions(bot)
    logger.debug(msg.format("setup_permissions"))
    await setup_restore_permissions(bot)
    logger.debug(msg.format("restore_permissions"))
    await setup_refresh_welcome(bot)
    logger.debug(msg.format("refresh_welcome"))
    await setup_userinfo(bot)
    logger.debug(msg.format("userinfo"))
    await setup_debug_logs(bot)
    logger.debug(msg.format("debug_logs"))
