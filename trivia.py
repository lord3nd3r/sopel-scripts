#!/usr/bin/env python3
"""
Sopel Trivia Bot Plugin
Commands:
  $trivia [category] [number] - Start trivia game (default 100 questions)
  $trivia categories          - List all available question categories
  $strivia                    - Stop the current trivia game
  $tstats [nick]              - Show player trivia statistics
  $ttop                       - Show channel leaderboard
  $ttopserver                 - Show server-wide leaderboard
"""
import os
import threading
import time
from datetime import datetime
from sopel import plugin, tools


def _get_prefix(bot):
    """Get the bot's command prefix character from config.
    
    The config stores prefix as a regex pattern (e.g. '\\$'),
    so we strip the leading backslash to get the actual character.
    Falls back to '.' if not configured.
    """
    try:
        raw = bot.config.core.prefix
        if raw:
            return raw.lstrip('\\')
    except (AttributeError, TypeError):
        pass
    return '.'


# Import our trivia game engine
import sys
import importlib
sys.path.insert(0, os.path.dirname(__file__))

import trivia_game
import trivia_db
# Force reload helper modules if the plugin is reloaded via bot rehash
if 'trivia_game' in sys.modules:
    importlib.reload(trivia_game)
if 'trivia_db' in sys.modules:
    importlib.reload(trivia_db)

from trivia_game import TriviaGame
from trivia_db import TriviaDB


def _get_categories(questions_file):
    """Retrieve unique trivia categories from TriviaGame or directly from questions.json."""
    if hasattr(TriviaGame, 'get_categories'):
        return TriviaGame.get_categories(questions_file)
    try:
        import json
        with open(questions_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return sorted({q.get('category', '').strip() for q in data if q.get('category')})
    except Exception:
        return []


# Per-channel game state
channel_games = {}

# Global database instance (lazy-initialized to avoid creating the DB
# file at import time if trivia is never used)
_db = None


def _get_db():
    """Get or create the global TriviaDB instance."""
    global _db
    if _db is None:
        _db = TriviaDB()
    return _db


class ChannelTrivia:
    """Manages trivia state for a single channel."""
    
    def __init__(self, bot, channel, num_questions, questions_file, started_by, category=None):
        self.bot = bot
        self.channel = channel
        self.started_by = started_by
        self.category = category
        self.server = bot.config.core.host if hasattr(bot.config.core, 'host') else 'default'
        self.game = TriviaGame.load_from_file(questions_file, category=category)
        self.game.shuffle()
        self.max_questions = min(num_questions, len(self.game.questions))
        self.current_question = None
        self.question_start_time = None
        self.running = False
        self.unanswered_count = 0
        self.hint_thread = None
        self.scores = {}  # nick -> total points
        self.question_answered = False
        self.stop_hints = False  # Flag to stop current hint thread
        self.question_timed_out = False  # Flag to prevent answers after timeout
        self.next_question_scheduled = False  # Prevent double-scheduling
        self._lock = threading.RLock()  # Reentrant lock for thread safety
        self.game_id = None  # Database game ID
        
    def start(self):
        """Start the trivia game loop."""
        self.running = True
        db = _get_db()
        self.game_id = db.start_game(self.channel, self.server, self.max_questions)
        self.next_question()
    
    def stop(self):
        """Stop the trivia game and record ending in DB."""
        self.running = False
        self.stop_hints = True
        if self.hint_thread:
            self.hint_thread = None
        if self.game_id:
            db = _get_db()
            db.end_game(self.game_id, self.game.score)
            self.game_id = None
    
    def next_question(self):
        """Ask the next question."""
        with self._lock:
            try:
                if not self.running:
                    return
                
                self.next_question_scheduled = False
                
                if self.game.current >= self.max_questions or self.game.remaining() == 0:
                    self.end_game()
                    return
                
                # Stop any previous hint thread
                self.stop_hints = True
                if self.hint_thread and self.hint_thread.is_alive() and threading.current_thread() != self.hint_thread:
                    self.hint_thread.join(timeout=1.0)
                
                self.current_question = self.game.next_question()
                if not self.current_question:
                    self.end_game()
                    return
                
                self.question_answered = False
                self.stop_hints = False
                self.question_timed_out = False
                self.question_start_time = time.time()
                
                # Display question
                q_num = self.game.current
                category = self.current_question.get("category", "")
                q_text = self.current_question.get("question", "")
                choices = self.current_question.get("choices")
                
                if category:
                    self.bot.say(f"{q_num}. [{category}] {q_text}", self.channel)
                else:
                    self.bot.say(f"{q_num}. {q_text}", self.channel)
                
                # Show choices clearly with letters (e.g. A) Option1 | B) Option2)
                if choices:
                    labeled = [f"{chr(ord('A') + i)}) {c}" for i, c in enumerate(choices)]
                    self.bot.say(f"Options: {' | '.join(labeled)}", self.channel)
                
                # Start hint thread
                self.hint_thread = threading.Thread(target=self._hint_loop, daemon=True)
                self.hint_thread.start()
            except Exception as e:
                print(f"Error in next_question: {e}")
                self.bot.say(f"[ERROR] Question error: {e} - ending game", self.channel)
                self.end_game()
    
    def _handle_timeout(self, answer):
        """Handle question timeout (shared by single-char and normal hint paths)."""
        self.bot.say(f"Time's up! The answer was: {answer}", self.channel)
        self.game.check_answer(self.current_question, None)
        self.unanswered_count += 1
        
        # Check inactivity
        if self.unanswered_count >= 5:
            self.bot.say("Trivia stopped due to inactivity (5 unanswered questions).", self.channel)
            self.end_game()
            return True
        elif self.unanswered_count >= 3:
            remaining = 5 - self.unanswered_count
            self.bot.say(
                f"Warning: {self.unanswered_count} unanswered in a row! "
                f"Game stops after {remaining} more.", self.channel
            )
        return False
    
    def _schedule_next_from_hint_thread(self):
        """Schedule next question after a 5-second pause (called from hint thread)."""
        with self._lock:
            if self.next_question_scheduled:
                return
            self.next_question_scheduled = True
        
        for _ in range(10):  # 5 second pause
            if not self.running:
                return
            time.sleep(0.5)
        if self.running:
            self.next_question()
    
    def _hint_loop(self):
        """Display progressive hints with delays."""
        my_question = self.current_question
        if not my_question or self.stop_hints:
            return
        
        answer = self.game.get_answer_text(my_question)
        
        # Skip hints for single-character answers
        if len(answer.strip()) == 1:
            for _ in range(60):  # 30 seconds total
                if not self.running or self.question_answered or self.stop_hints:
                    return
                time.sleep(0.5)
            
            with self._lock:
                if self.current_question != my_question or self.question_answered:
                    return
                self.question_timed_out = True
            
            if self._handle_timeout(answer):
                return
            self._schedule_next_from_hint_thread()
            return
        
        hints = self.game.generate_hints(answer, num_hints=3)
        
        # Display hints with 10-second intervals
        for hint in hints:
            for _ in range(20):  # 10 seconds
                if not self.running or self.question_answered or self.stop_hints:
                    return
                time.sleep(0.5)
            
            if not self.running or self.question_answered or self.stop_hints:
                return
            if self.current_question == my_question:
                self.bot.say(f"Hint: {hint}", self.channel)
            else:
                return
        
        # Final delay before timeout
        for _ in range(20):  # 10 seconds
            if not self.running or self.question_answered or self.stop_hints:
                return
            time.sleep(0.5)
        
        if not self.running or self.question_answered or self.stop_hints:
            return
        
        with self._lock:
            if self.current_question != my_question or self.question_answered:
                return
            self.question_timed_out = True
        
        if self._handle_timeout(answer):
            return
        self._schedule_next_from_hint_thread()
    
    def check_answer(self, nick, answer_text):
        """Check if a user's answer is correct using smart matching."""
        with self._lock:
            if not self.current_question or self.question_answered or self.question_timed_out:
                return False
            
            # Delegate to TriviaGame smart matching (handles punctuation, articles, choices, alternatives)
            correct = self.game.check_answer(self.current_question, answer_text, winner_name=nick)
            if not correct:
                return False
            
            # Correct answer — mark immediately
            self.question_answered = True
            self.stop_hints = True
            elapsed = time.time() - self.question_start_time
            
            # Calculate points (speed bonus)
            points = 1
            if elapsed < 5:
                points = 3
            elif elapsed < 10:
                points = 2
            
            if nick not in self.scores:
                self.scores[nick] = 0
            self.scores[nick] += points
            
            # Display winner message
            answer = self.game.get_answer_text(self.current_question)
            self.bot.say(
                f"Winner: {nick}; Answer: {answer}; Time: {elapsed:.3f}s; "
                f"Streak: {self.game.streak}; Points: {points}; Total: {self.scores[nick]}",
                self.channel
            )
            
            # Record to database
            db = _get_db()
            if self.game_id:
                db.record_answer(
                    self.game_id, nick, self.server, self.channel,
                    self.current_question.get('question', ''),
                    answer, points, elapsed, self.game.streak
                )
            
            self.unanswered_count = 0
            
            if not self.next_question_scheduled:
                self.next_question_scheduled = True
                threading.Thread(target=self._delayed_next, daemon=True).start()
            return True
    
    def _delayed_next(self):
        """Wait 5 seconds then ask next question."""
        try:
            for _ in range(10):  # 5 seconds
                if not self.running:
                    return
                time.sleep(0.5)
            
            if self.running:
                self.next_question()
        except Exception as e:
            print(f"Error in _delayed_next: {e}")
            try:
                self.bot.say(f"[DEBUG] Error scheduling next question: {e}", self.channel)
            except Exception:
                pass
    
    def end_game(self):
        """End the game, update DB, and show final scores."""
        self.stop()
        
        prefix = _get_prefix(self.bot)
        self.bot.say(f"Trivia stopped. '{prefix}trivia [number]' to start playing again.", self.channel)
        self.show_scores()
        
        channel_games.pop(self.channel, None)
    
    def show_scores(self):
        """Display final scoreboard."""
        score_text = f"Total Questions: {self.game.current}"
        self.bot.say(score_text, self.channel)
        
        if not self.scores:
            self.bot.say("No points were scored this round.", self.channel)
            return
        
        sorted_scores = sorted(self.scores.items(), key=lambda x: -x[1])
        db = _get_db()
        lines = []
        for nick, score in sorted_scores[:5]:
            try:
                db_stats = db.get_player_stats(nick, self.server, self.channel)
                total_db = db_stats['total_points'] if db_stats and 'total_points' in db_stats else 0
            except Exception:
                total_db = 0
            lines.append(f"{nick} ({score} pts - Total: {total_db})")

        if lines:
            self.bot.say(" | ".join(lines), self.channel)


@plugin.command('trivia')
@plugin.example('$trivia 10')
@plugin.example('$trivia science 20')
@plugin.example('$trivia categories')
def trivia_start(bot, trigger):
    """Start a trivia game in the current channel."""
    channel = trigger.sender
    prefix = _get_prefix(bot)
    
    # Must be in a channel, not a private message
    if not channel.startswith(('#', '&', '+', '!')):
        bot.say("Trivia can only be played in a channel.", channel)
        return
    
    questions_file = os.path.join(os.path.dirname(__file__), 'questions.json')
    
    # Check if user wants category listing
    arg = trigger.group(2).strip() if trigger.group(2) else ""
    if arg.lower() in ('categories', 'cats', 'category'):
        try:
            cats = _get_categories(questions_file)
            bot.say(f"Available trivia categories: {', '.join(cats)}", channel)
        except Exception as e:
            bot.say(f"Error loading categories: {e}", channel)
        return
    
    if channel in channel_games and channel_games[channel].running:
        bot.say(f"A trivia game is already running! Use {prefix}strivia to stop it first.", channel)
        return
    
    # Parse arguments: can be [number], [category], or [category] [number] / [number] [category]
    num_questions = 100
    chosen_category = None
    
    if arg:
        tokens = arg.split()
        available_cats = {c.lower(): c for c in _get_categories(questions_file)}
        for token in tokens:
            if token.isdigit():
                val = int(token)
                if val < 1:
                    num_questions = 10
                elif val > 500:
                    num_questions = 500
                else:
                    num_questions = val
            elif token.lower() in available_cats:
                chosen_category = available_cats[token.lower()]
        
        # If user typed something that didn't match an int or known category, check partial match
        if not chosen_category and not any(t.isdigit() for t in tokens):
            partial = [real for low, real in available_cats.items() if low.startswith(arg.lower())]
            if partial:
                chosen_category = partial[0]
            else:
                bot.say(f"Unknown category '{arg}'. Type {prefix}trivia categories to see available ones.", channel)
                return
    
    # Create and start game
    try:
        game = ChannelTrivia(
            bot=bot,
            channel=channel,
            num_questions=num_questions,
            questions_file=questions_file,
            started_by=trigger.nick,
            category=chosen_category
        )
        if len(game.game.questions) == 0:
            bot.say(f"No questions found for category '{chosen_category}'.", channel)
            return
        
        channel_games[channel] = game
        cat_str = f" [{chosen_category}]" if chosen_category else ""
        bot.say(
            f"Starting trivia{cat_str}! {game.max_questions} questions loaded. Answer in the channel!",
            channel
        )
        game.start()
    except FileNotFoundError:
        bot.say("Error: questions.json not found!", channel)
    except Exception as e:
        bot.say(f"Error starting trivia: {e}", channel)


@plugin.command('tcategories', 'tcats')
@plugin.example('$tcategories')
def trivia_categories(bot, trigger):
    """List all available trivia categories."""
    channel = trigger.sender
    questions_file = os.path.join(os.path.dirname(__file__), 'questions.json')
    try:
        cats = _get_categories(questions_file)
        bot.say(f"Available trivia categories: {', '.join(cats)}", channel)
    except Exception as e:
        bot.say(f"Error loading categories: {e}", channel)


@plugin.command('strivia')
@plugin.example('$strivia')
def trivia_stop(bot, trigger):
    """Stop the current trivia game."""
    channel = trigger.sender
    
    if channel not in channel_games or not channel_games[channel].running:
        bot.say("No trivia game is currently running.", channel)
        return
    
    game = channel_games[channel]
    game.end_game()


@plugin.rule(r'.*')
@plugin.priority('low')
def check_trivia_answer(bot, trigger):
    """Listen for answers to trivia questions."""
    channel = trigger.sender
    
    if not channel.startswith(('#', '&', '+', '!')):
        return
    
    if channel not in channel_games or not channel_games[channel].running:
        return
    
    # Ignore commands (skip messages starting with the bot's prefix)
    prefix = _get_prefix(bot)
    if trigger.match.group(0).startswith(prefix):
        return
    
    game = channel_games[channel]
    nick = trigger.nick
    answer = trigger.match.group(0).strip()
    
    if answer:
        game.check_answer(nick, answer)


@plugin.command('tstats', 'triviastats')
@plugin.example('$tstats')
@plugin.example('$tstats Nick')
def trivia_stats(bot, trigger):
    """Show trivia statistics for yourself or another player."""
    channel = trigger.sender
    server = bot.config.core.host if hasattr(bot.config.core, 'host') else 'default'
    
    target_nick = trigger.group(2).strip() if trigger.group(2) else trigger.nick
    
    db = _get_db()
    stats = db.get_player_stats(target_nick, server, channel)
    
    if not stats or stats['total_points'] == 0:
        bot.say(f"{target_nick} has no trivia stats in this channel yet.", channel)
        return
    
    fastest = f"{stats['fastest_time']:.2f}s" if stats['fastest_time'] else "N/A"
    
    bot.say(
        f"{target_nick}: {stats['total_points']} points | "
        f"{stats['total_wins']} wins | "
        f"{stats['longest_streak']} streak | "
        f"Fastest: {fastest}",
        channel
    )


@plugin.command('ttop', 'triviatop')
@plugin.example('$ttop')
def trivia_top(bot, trigger):
    """Show top 10 players in this channel."""
    channel = trigger.sender
    server = bot.config.core.host if hasattr(bot.config.core, 'host') else 'default'
    
    db = _get_db()
    top_players = db.get_channel_stats(channel, server, limit=10)
    
    if not top_players:
        bot.say("No trivia stats for this channel yet.", channel)
        return
    
    bot.say(f"[TOP] Top Players in {channel}:", channel)
    for i, (nick, points, answers, wins, streak, fastest) in enumerate(top_players, 1):
        fastest_str = f"{fastest:.2f}s" if fastest else "N/A"
        bot.say(
            f"{i}. {nick}: {points} pts | {wins} wins | {streak} streak | Fastest: {fastest_str}",
            channel
        )


@plugin.command('ttopserver', 'triviatopserver')
@plugin.example('$ttopserver')
def trivia_top_server(bot, trigger):
    """Show top 10 players across the entire server."""
    channel = trigger.sender
    server = bot.config.core.host if hasattr(bot.config.core, 'host') else 'default'
    
    db = _get_db()
    top_players = db.get_server_stats(server, limit=10)
    
    if not top_players:
        bot.say("No trivia stats for this server yet.", channel)
        return
    
    bot.say("[TOP] Top Players Server-Wide:", channel)
    for i, (nick, points, answers, wins, streak, fastest) in enumerate(top_players, 1):
        fastest_str = f"{fastest:.2f}s" if fastest else "N/A"
        bot.say(
            f"{i}. {nick}: {points} pts | {wins} wins | {streak} streak | Fastest: {fastest_str}",
            channel
        )
