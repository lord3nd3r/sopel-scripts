from sopel import plugin
from sopel.config.types import StaticSection, BooleanAttribute, ValidatedAttribute
import logging
import time
import threading

# Set up logging
logger = logging.getLogger(__name__)

# Define the configuration section
class PromoteMeSection(StaticSection):
    """Configuration section for the PromoteMe plugin."""
    require_admin = BooleanAttribute('require_admin', default=True)
    """Whether only admins can use the command."""
    require_bot_op = BooleanAttribute('require_bot_op', default=True)
    """Whether the bot requires operator status to promote users."""
    success_message = ValidatedAttribute('success_message', default="Promoted {nick} to operator in {channel}.")
    """Customizable success message with {nick} and {channel} placeholders."""
    modes = ValidatedAttribute('modes', default='+o')
    """IRC modes to apply (e.g., '+o' for operator)."""
    allow_in_all_channels = BooleanAttribute('allow_in_all_channels', default=True)
    """Whether the command can be used in all channels."""
    allowed_channels = ValidatedAttribute('allowed_channels', default='')
    """Comma-separated list of allowed channels if allow_in_all_channels is False."""
    cooldown_seconds = ValidatedAttribute('cooldown_seconds', int, default=60)
    """User-specific cooldown in seconds."""
    temporary_promotion = BooleanAttribute('temporary_promotion', default=False)
    """Whether promotions are temporary."""
    promotion_duration = ValidatedAttribute('promotion_duration', int, default=300)
    """Duration in seconds for temporary promotions."""

# Setup function to initialize the plugin
def setup(bot):
    """Initialize the PromoteMe plugin by defining its configuration section."""
    bot.config.define_section('promoteme', PromoteMeSection)
    logger.info("PromoteMe plugin initialized.")

# Main command function
@plugin.command('promoteme')
def promote_me(bot, trigger):
    """
    Handle the !promoteme command to promote a user in a channel.

    Args:
        bot: The Sopel bot instance.
        trigger: The command trigger containing user and message details.
    """
    # Check if the command is used in a private message
    if trigger.is_privmsg:
        bot.reply("This command can only be used in a channel.")
        return

    # Get channel and user details
    channel = trigger.sender
    nick = trigger.nick
    target = trigger.group(2) or nick  # Target is the argument or the user themselves

    # Cooldown checks
    user_key = f"promoteme_user_{nick}"
    channel_key = f"promoteme_channel_{channel}"
    last_used_user = bot.memory.get(user_key, 0)
    if time.time() - last_used_user < bot.config.promoteme.cooldown_seconds:
        bot.reply(f"Please wait {bot.config.promoteme.cooldown_seconds} seconds between uses.")
        return
    last_used_channel = bot.memory.get(channel_key, 0)
    if time.time() - last_used_channel < 300:  # Hardcoded channel cooldown of 300 seconds
        bot.reply("This command is on cooldown in this channel.")
        return

    # Channel restrictions
    if not bot.config.promoteme.allow_in_all_channels:
        allowed_channels = [ch.strip() for ch in bot.config.promoteme.allowed_channels.split(',')]
        if channel not in allowed_channels:
            bot.reply("This command is not allowed in this channel.")
            return

    # Permission checks
    if bot.config.promoteme.require_admin and not trigger.admin:
        bot.reply("You don't have permission to use this command.")
        return

    # Bot privilege check
    if bot.config.promoteme.require_bot_op:
        if channel not in bot.channels or not bot.channels[channel].privileges.get(bot.nick, 0) & plugin.OP:
            bot.reply("I need operator status to promote users!")
            return

    # Apply modes
    modes = bot.config.promoteme.modes
    try:
        bot.write(['MODE', channel, modes, target])
        success_msg = bot.config.promoteme.success_message.format(nick=target, channel=channel)
        bot.reply(success_msg)
        logger.info(f"Applied {modes} to {target} in {channel}.")

        # Handle temporary promotion
        if bot.config.promoteme.temporary_promotion:
            inverse_modes = modes.replace('+', '-')
            threading.Timer(
                bot.config.promoteme.promotion_duration,
                bot.write,
                args=(['MODE', channel, inverse_modes, target],)
            ).start()
            bot.reply(f"This promotion is temporary and will revert in {bot.config.promoteme.promotion_duration} seconds.")

        # Update cooldowns
        bot.memory[user_key] = time.time()
        bot.memory[channel_key] = time.time()

    except Exception as e:
        bot.reply("Failed to promote the user due to an error.")
        logger.error(f"Error applying {modes} to {target} in {channel}: {str(e)}")
