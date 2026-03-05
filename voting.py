"""
IRC Voting Module for Sopel
Allows halfops and above to create polls with multiple options and time limits
"""

from sopel import plugin, tools
from sopel.config.types import StaticSection, ValidatedAttribute
import sqlite3
import threading
import time
from datetime import datetime, timedelta
import re
from collections import defaultdict

# Database lock for thread safety
db_lock = threading.Lock()

# Active votes tracking (in-memory for quick access)
active_votes = {}
vote_timers = {}


class VotingSection(StaticSection):
    """Configuration section for voting module."""
    db_path = ValidatedAttribute('db_path', default='voting.db')
    message_delay = ValidatedAttribute('message_delay', default=0.5)  # Delay between messages in seconds


def setup(bot):
    """Setup the module and initialize database."""
    bot.config.define_section('voting', VotingSection)
    init_database(bot)


def init_database(bot):
    """Initialize the SQLite database for storing votes."""
    db_path = bot.config.voting.db_path
    
    with db_lock:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Table for vote metadata
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS votes (
                vote_id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel TEXT NOT NULL,
                creator TEXT NOT NULL,
                question TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                status TEXT DEFAULT 'active',
                total_votes INTEGER DEFAULT 0
            )
        ''')
        
        # Table for vote options
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS vote_options (
                option_id INTEGER PRIMARY KEY AUTOINCREMENT,
                vote_id INTEGER NOT NULL,
                option_number INTEGER NOT NULL,
                option_text TEXT NOT NULL,
                vote_count INTEGER DEFAULT 0,
                FOREIGN KEY (vote_id) REFERENCES votes(vote_id)
            )
        ''')
        
        # Table for tracking who voted
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vote_id INTEGER NOT NULL,
                nick TEXT NOT NULL,
                option_number INTEGER NOT NULL,
                voted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (vote_id) REFERENCES votes(vote_id),
                UNIQUE(vote_id, nick)
            )
        ''')
        
        conn.commit()
        conn.close()


def parse_time_duration(time_str):
    """Parse time duration like '24h', '30m', '2d' into seconds."""
    time_str = time_str.lower().strip()
    
    # Match pattern like 24h, 30m, 2d
    match = re.match(r'^(\d+)([smhd])$', time_str)
    if not match:
        return None
    
    value, unit = match.groups()
    value = int(value)
    
    if unit == 's':
        return value
    elif unit == 'm':
        return value * 60
    elif unit == 'h':
        return value * 3600
    elif unit == 'd':
        return value * 86400
    
    return None


def is_halfop_or_above(bot, channel, nick):
    """Check if user has halfop or higher privileges."""
    if not channel.startswith('#'):
        return False
    
    if channel not in bot.channels:
        return False
    
    if nick not in bot.channels[channel].users:
        return False
    
    privileges = bot.channels[channel].privileges.get(nick, 0)
    
    # Check for halfop (4), op (8), admin (16), or owner (32)
    return privileges >= 4


@plugin.command('votehelp')
@plugin.example('.votehelp')
def vote_help(bot, trigger):
    """
    Send voting help information via PM.
    Usage: .votehelp or .vote help
    """
    nick = trigger.nick
    
    # Send help via PM using bot.say with destination parameter
    bot.say("📚 ═══════════════════════════════════════", destination=nick)
    bot.say("🗳️  VOTING SYSTEM HELP", destination=nick)
    bot.say("📚 ═══════════════════════════════════════", destination=nick)
    bot.say("", destination=nick)
    bot.say("🎯 CREATING A VOTE (Halfop+ only)", destination=nick)
    bot.say("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", destination=nick)
    bot.say("Command: .vote Q:question A1:option1 A2:option2 T:duration", destination=nick)
    bot.say("", destination=nick)
    bot.say("📝 Format:", destination=nick)
    bot.say("  Q: = Your question", destination=nick)
    bot.say("  A1: = First option", destination=nick)
    bot.say("  A2: = Second option", destination=nick)
    bot.say("  A3: = Third option (optional)", destination=nick)
    bot.say("  T: = Time duration", destination=nick)
    bot.say("", destination=nick)
    bot.say("⏰ Time formats:", destination=nick)
    bot.say("  30s = 30 seconds", destination=nick)
    bot.say("  15m = 15 minutes", destination=nick)
    bot.say("  24h = 24 hours", destination=nick)
    bot.say("  7d = 7 days", destination=nick)
    bot.say("", destination=nick)
    bot.say("💡 Example:", destination=nick)
    bot.say("  .vote Q:Best pizza? A1:Pepperoni A2:Cheese A3:Veggie T:1h", destination=nick)
    bot.say("", destination=nick)
    bot.say("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", destination=nick)
    bot.say("🗳️  CASTING YOUR VOTE", destination=nick)
    bot.say("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", destination=nick)
    bot.say("Command: .v <number>", destination=nick)
    bot.say("", destination=nick)
    bot.say("💡 Examples:", destination=nick)
    bot.say("  .v 1    - Vote for option 1", destination=nick)
    bot.say("  .v 2    - Vote for option 2", destination=nick)
    bot.say("", destination=nick)
    bot.say("✨ You can change your vote anytime!", destination=nick)
    bot.say("", destination=nick)
    bot.say("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", destination=nick)
    bot.say("📊 VIEWING STATISTICS", destination=nick)
    bot.say("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", destination=nick)
    bot.say("Commands:", destination=nick)
    bot.say("  .votestats   - Show current results", destination=nick)
    bot.say("  .vstats      - Same as above", destination=nick)
    bot.say("  .voteresults - Same as above", destination=nick)
    bot.say("", destination=nick)
    bot.say("Shows: vote counts, percentages, progress bars, time left", destination=nick)
    bot.say("", destination=nick)
    bot.say("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", destination=nick)
    bot.say("🛑 ENDING A VOTE EARLY", destination=nick)
    bot.say("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", destination=nick)
    bot.say("Command: .endvote", destination=nick)
    bot.say("", destination=nick)
    bot.say("⚠️  Only the vote creator or halfops+ can end votes", destination=nick)
    bot.say("", destination=nick)
    bot.say("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", destination=nick)
    bot.say("ℹ️  ADDITIONAL INFO", destination=nick)
    bot.say("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", destination=nick)
    bot.say("• One active vote per channel at a time", destination=nick)
    bot.say("• One vote per person (can be changed)", destination=nick)
    bot.say("• Votes auto-close when time expires", destination=nick)
    bot.say("• Winner announced with 🏆 trophy", destination=nick)
    bot.say("• All votes saved to database", destination=nick)
    bot.say("", destination=nick)
    bot.say("📚 ═══════════════════════════════════════", destination=nick)
    
    # Confirm in channel
    bot.reply("📬 Help information sent via PM!")


@plugin.command('vote')
@plugin.example('.vote Q:Should we add a new feature? A1:Yes A2:No A3:Maybe T:24h')
def create_vote(bot, trigger):
    """
    Create a new vote/poll in the channel.
    Usage: .vote Q:question A1:option1 A2:option2 [A3:option3...] T:duration
    Duration format: 30m, 24h, 2d (minutes, hours, days)
    Requires halfop or above.
    Use .vote help for detailed instructions.
    """
    # Check for help command
    if trigger.group(2) and trigger.group(2).strip().lower() == 'help':
        vote_help(bot, trigger)
        return
    
    # Check if user has required privileges
    if not is_halfop_or_above(bot, trigger.sender, trigger.nick):
        bot.reply("❌ You need to be at least halfop to create a vote!")
        return
    
    if not trigger.group(2):
        bot.reply("Usage: .vote Q:question A1:option1 A2:option2 T:duration (or .vote help)")
        return
    
    # Parse the vote command
    args = trigger.group(2)
    
    # Extract question
    q_match = re.search(r'Q:([^A]+?)(?=A\d+:|$)', args, re.IGNORECASE)
    if not q_match:
        bot.reply("❌ Missing question! Use Q:your question here")
        return
    
    question = q_match.group(1).strip()
    
    # Extract options
    options = {}
    option_matches = re.finditer(r'A(\d+):([^AT]+?)(?=A\d+:|T:|$)', args, re.IGNORECASE)
    for match in option_matches:
        opt_num = int(match.group(1))
        opt_text = match.group(2).strip()
        options[opt_num] = opt_text
    
    if len(options) < 2:
        bot.reply("❌ You need at least 2 options! Use A1:option1 A2:option2")
        return
    
    # Extract time duration
    t_match = re.search(r'T:(\d+[smhd])', args, re.IGNORECASE)
    if not t_match:
        bot.reply("❌ Missing time duration! Use T:24h (or 30m, 2d, etc.)")
        return
    
    duration_seconds = parse_time_duration(t_match.group(1))
    if not duration_seconds:
        bot.reply("❌ Invalid time format! Use format like: 30m, 24h, 2d")
        return
    
    # Create vote in database
    db_path = bot.config.voting.db_path
    expires_at = datetime.now() + timedelta(seconds=duration_seconds)
    
    with db_lock:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Insert vote
        cursor.execute('''
            INSERT INTO votes (channel, creator, question, expires_at)
            VALUES (?, ?, ?, ?)
        ''', (trigger.sender, trigger.nick, question, expires_at))
        
        vote_id = cursor.lastrowid
        
        # Insert options
        for opt_num, opt_text in sorted(options.items()):
            cursor.execute('''
                INSERT INTO vote_options (vote_id, option_number, option_text)
                VALUES (?, ?, ?)
            ''', (vote_id, opt_num, opt_text))
        
        conn.commit()
        conn.close()
    
    # Store in active votes
    active_votes[trigger.sender] = {
        'vote_id': vote_id,
        'question': question,
        'options': options,
        'expires_at': expires_at,
        'creator': trigger.nick
    }
    
    # Schedule vote end
    timer = threading.Timer(duration_seconds, end_vote, args=[bot, trigger.sender, vote_id])
    timer.start()
    vote_timers[trigger.sender] = timer
    
    # Get message delay setting
    delay = bot.config.voting.message_delay
    
    # Announce the vote (with anti-flood delays)
    bot.say(f"📊 ═══════════════════════════════════════")
    time.sleep(delay)
    bot.say(f"🗳️  NEW VOTE by {trigger.nick}")
    time.sleep(delay)
    bot.say(f"❓ {question}")
    time.sleep(delay)
    bot.say(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    time.sleep(delay)
    
    for opt_num, opt_text in sorted(options.items()):
        emoji = get_number_emoji(opt_num)
        bot.say(f"{emoji} Option {opt_num}: {opt_text}")
        time.sleep(delay)
    
    bot.say(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    time.sleep(delay)
    bot.say(f"⏰ Vote ends in {format_duration(duration_seconds)}")
    time.sleep(delay)
    bot.say(f"💡 Vote with: .v {' or '.join([str(n) for n in sorted(options.keys())])}")
    time.sleep(delay)
    bot.say(f"📊 ═══════════════════════════════════════")


@plugin.command('v', 'castvote')
@plugin.example('.v 1')
def cast_vote(bot, trigger):
    """
    Cast your vote for an active poll.
    Usage: .v <option_number>
    """
    if trigger.sender not in active_votes:
        bot.reply("❌ No active vote in this channel!")
        return
    
    if not trigger.group(2):
        bot.reply("Usage: .v <option_number>")
        return
    
    try:
        option_num = int(trigger.group(2).strip())
    except ValueError:
        bot.reply("❌ Please provide a valid option number!")
        return
    
    vote_data = active_votes[trigger.sender]
    
    if option_num not in vote_data['options']:
        bot.reply(f"❌ Invalid option! Choose from: {', '.join([str(n) for n in sorted(vote_data['options'].keys())])}")
        return
    
    # Record vote in database
    db_path = bot.config.voting.db_path
    vote_id = vote_data['vote_id']
    
    with db_lock:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if user already voted
        cursor.execute('''
            SELECT option_number FROM user_votes
            WHERE vote_id = ? AND nick = ?
        ''', (vote_id, trigger.nick))
        
        existing_vote = cursor.fetchone()
        
        if existing_vote:
            old_option = existing_vote[0]
            
            # Update vote
            cursor.execute('''
                UPDATE user_votes
                SET option_number = ?, voted_at = CURRENT_TIMESTAMP
                WHERE vote_id = ? AND nick = ?
            ''', (option_num, vote_id, trigger.nick))
            
            # Update vote counts
            cursor.execute('''
                UPDATE vote_options
                SET vote_count = vote_count - 1
                WHERE vote_id = ? AND option_number = ?
            ''', (vote_id, old_option))
            
            cursor.execute('''
                UPDATE vote_options
                SET vote_count = vote_count + 1
                WHERE vote_id = ? AND option_number = ?
            ''', (vote_id, option_num))
            
            conn.commit()
            conn.close()
            
            emoji = get_number_emoji(option_num)
            bot.reply(f"✅ Vote changed to {emoji} Option {option_num}!")
        else:
            # Insert new vote
            cursor.execute('''
                INSERT INTO user_votes (vote_id, nick, option_number)
                VALUES (?, ?, ?)
            ''', (vote_id, trigger.nick, option_num))
            
            # Update vote count
            cursor.execute('''
                UPDATE vote_options
                SET vote_count = vote_count + 1
                WHERE vote_id = ? AND option_number = ?
            ''', (vote_id, option_num))
            
            # Update total votes
            cursor.execute('''
                UPDATE votes
                SET total_votes = total_votes + 1
                WHERE vote_id = ?
            ''', (vote_id,))
            
            conn.commit()
            conn.close()
            
            emoji = get_number_emoji(option_num)
            bot.reply(f"✅ Vote recorded for {emoji} Option {option_num}!")


@plugin.command('votestats', 'vstats', 'voteresults')
@plugin.example('.votestats')
def show_vote_stats(bot, trigger):
    """
    Show current statistics for the active vote.
    Usage: .votestats
    """
    if trigger.sender not in active_votes:
        bot.reply("❌ No active vote in this channel!")
        return
    
    vote_data = active_votes[trigger.sender]
    vote_id = vote_data['vote_id']
    
    # Get current stats from database
    db_path = bot.config.voting.db_path
    
    with db_lock:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT option_number, option_text, vote_count
            FROM vote_options
            WHERE vote_id = ?
            ORDER BY option_number
        ''', (vote_id,))
        
        options = cursor.fetchall()
        
        cursor.execute('''
            SELECT total_votes FROM votes WHERE vote_id = ?
        ''', (vote_id,))
        
        total_votes = cursor.fetchone()[0]
        conn.close()
    
    # Calculate time remaining
    time_left = (vote_data['expires_at'] - datetime.now()).total_seconds()
    
    # Get message delay setting
    delay = bot.config.voting.message_delay
    
    # Display stats (with anti-flood delays)
    bot.say(f"📊 ═══════════════════════════════════════")
    time.sleep(delay)
    bot.say(f"📈 VOTE STATISTICS")
    time.sleep(delay)
    bot.say(f"❓ {vote_data['question']}")
    time.sleep(delay)
    bot.say(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    time.sleep(delay)
    bot.say(f"🗳️  Total Votes: {total_votes}")
    time.sleep(delay)
    bot.say(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    time.sleep(delay)
    
    for opt_num, opt_text, vote_count in options:
        percentage = (vote_count / total_votes * 100) if total_votes > 0 else 0
        bar = create_progress_bar(percentage)
        emoji = get_number_emoji(opt_num)
        
        bot.say(f"{emoji} Option {opt_num}: {opt_text}")
        time.sleep(delay)
        bot.say(f"   {bar} {vote_count} votes ({percentage:.1f}%)")
        time.sleep(delay)
    
    bot.say(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    time.sleep(delay)
    
    if time_left > 0:
        bot.say(f"⏰ Time remaining: {format_duration(int(time_left))}")
    else:
        bot.say(f"⏰ Vote has ended!")
    
    time.sleep(delay)
    bot.say(f"📊 ═══════════════════════════════════════")


@plugin.command('endvote')
def manual_end_vote(bot, trigger):
    """
    Manually end the active vote (creator or halfop+ only).
    Usage: .endvote
    """
    if trigger.sender not in active_votes:
        bot.reply("❌ No active vote in this channel!")
        return
    
    vote_data = active_votes[trigger.sender]
    
    # Check if user is creator or has privileges
    if trigger.nick != vote_data['creator'] and not is_halfop_or_above(bot, trigger.sender, trigger.nick):
        bot.reply("❌ Only the vote creator or halfops+ can end the vote!")
        return
    
    # Cancel timer if exists
    if trigger.sender in vote_timers:
        vote_timers[trigger.sender].cancel()
        del vote_timers[trigger.sender]
    
    # End the vote
    end_vote(bot, trigger.sender, vote_data['vote_id'])


def end_vote(bot, channel, vote_id):
    """End a vote and display final results."""
    if channel not in active_votes:
        return
    
    vote_data = active_votes[channel]
    
    # Mark vote as closed in database
    db_path = bot.config.voting.db_path
    
    with db_lock:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE votes
            SET status = 'closed'
            WHERE vote_id = ?
        ''', (vote_id,))
        
        cursor.execute('''
            SELECT option_number, option_text, vote_count
            FROM vote_options
            WHERE vote_id = ?
            ORDER BY vote_count DESC, option_number
        ''', (vote_id,))
        
        options = cursor.fetchall()
        
        cursor.execute('''
            SELECT total_votes FROM votes WHERE vote_id = ?
        ''', (vote_id,))
        
        total_votes = cursor.fetchone()[0]
        conn.commit()
        conn.close()
    
    # Get message delay setting
    delay = bot.config.voting.message_delay
    
    # Display final results (with anti-flood delays)
    bot.say(f"🏁 ═══════════════════════════════════════", destination=channel)
    time.sleep(delay)
    bot.say(f"🎉 VOTE ENDED - FINAL RESULTS", destination=channel)
    time.sleep(delay)
    bot.say(f"❓ {vote_data['question']}", destination=channel)
    time.sleep(delay)
    bot.say(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", destination=channel)
    time.sleep(delay)
    bot.say(f"🗳️  Total Votes: {total_votes}", destination=channel)
    time.sleep(delay)
    bot.say(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", destination=channel)
    time.sleep(delay)
    
    if total_votes > 0:
        winner = options[0]
        winner_emoji = get_number_emoji(winner[0])
        
        for opt_num, opt_text, vote_count in options:
            percentage = (vote_count / total_votes * 100) if total_votes > 0 else 0
            bar = create_progress_bar(percentage)
            emoji = get_number_emoji(opt_num)
            
            # Add trophy for winner
            trophy = "🏆 " if opt_num == winner[0] else "   "
            
            bot.say(f"{trophy}{emoji} Option {opt_num}: {opt_text}", destination=channel)
            time.sleep(delay)
            bot.say(f"   {bar} {vote_count} votes ({percentage:.1f}%)", destination=channel)
            time.sleep(delay)
        
        bot.say(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", destination=channel)
        time.sleep(delay)
        bot.say(f"🏆 WINNER: {winner_emoji} Option {winner[0]} - {winner[1]}", destination=channel)
    else:
        bot.say(f"😔 No votes were cast!", destination=channel)
    
    time.sleep(delay)
    bot.say(f"🏁 ═══════════════════════════════════════", destination=channel)
    
    # Clean up
    del active_votes[channel]
    if channel in vote_timers:
        del vote_timers[channel]


def create_progress_bar(percentage, length=20):
    """Create a visual progress bar."""
    filled = int(length * percentage / 100)
    empty = length - filled
    
    bar = "█" * filled + "░" * empty
    return f"[{bar}]"


def get_number_emoji(num):
    """Get emoji representation of a number."""
    emoji_map = {
        1: "1️⃣",
        2: "2️⃣",
        3: "3️⃣",
        4: "4️⃣",
        5: "5️⃣",
        6: "6️⃣",
        7: "7️⃣",
        8: "8️⃣",
        9: "9️⃣",
        10: "🔟"
    }
    return emoji_map.get(num, f"#{num}")


def format_duration(seconds):
    """Format seconds into human-readable duration."""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes}m"
    elif seconds < 86400:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        if minutes > 0:
            return f"{hours}h {minutes}m"
        return f"{hours}h"
    else:
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        if hours > 0:
            return f"{days}d {hours}h"
        return f"{days}d"
