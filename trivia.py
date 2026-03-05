#!/usr/bin/env python3
"""
Sopel Trivia Bot Plugin
Commands:
  $trivia [number] - Start trivia game (default 100 questions)
  $strivia - Stop the current trivia game
"""
import os
import threading
import time
from datetime import datetime
from sopel import plugin, tools

# Import our trivia game engine
import sys
sys.path.insert(0, os.path.dirname(__file__))
from trivia_game import TriviaGame
from trivia_db import TriviaDB


# Per-channel game state
channel_games = {}
channel_locks = {}

# Global database instance
db = TriviaDB()


class ChannelTrivia:
    """Manages trivia state for a single channel."""
    
    def __init__(self, bot, channel, num_questions, questions_file):
        self.bot = bot
        self.channel = channel
        self.server = bot.config.core.host if hasattr(bot.config.core, 'host') else 'default'
        self.game = TriviaGame.load_from_file(questions_file)
        self.game.shuffle()
        self.max_questions = num_questions
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
        self._lock = threading.Lock()  # Thread safety
        self.game_id = None  # Database game ID
        
    def start(self):
        """Start the trivia game loop."""
        self.running = True
        self.game_id = db.start_game(self.channel, self.server, self.max_questions)
        self.next_question()
    
    def stop(self):
        """Stop the trivia game."""
        self.running = False
        if self.hint_thread:
            self.hint_thread = None
    
    def next_question(self):
        """Ask the next question."""
        with self._lock:  # Ensure only one thread can call this at a time
            try:
                if not self.running:
                    return
                
                self.next_question_scheduled = False  # Reset flag
                
                if self.game.current >= self.max_questions or self.game.remaining() == 0:
                    self.end_game()
                    return
                
                # Stop any previous hint thread
                self.stop_hints = True
                # Only wait if we're NOT being called from the hint thread (avoid deadlock)
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
                
                if category:
                    self.bot.say(f"{q_num}. {category}: {q_text}", self.channel)
                else:
                    self.bot.say(f"{q_num}. {q_text}", self.channel)
                
                # Start hint thread
                self.hint_thread = threading.Thread(target=self._hint_loop, daemon=True)
                self.hint_thread.start()
            except Exception as e:
                print(f"Error in next_question: {e}")
                # Try to recover by ending game gracefully
                self.bot.say(f"[ERROR] Question error: {e} - ending game", self.channel)
                self.end_game()
    
    def _hint_loop(self):
        """Display progressive hints with delays."""
        # Capture the question at thread start to avoid race conditions
        my_question = self.current_question
        if not my_question or self.stop_hints:
            return
        
        answer = self.game.get_answer_text(my_question)
        
        # Skip hints for single-character answers
        if len(answer.strip()) == 1:
            # Just wait for timeout without hints
            for _ in range(60):  # 60 * 0.5 = 30 seconds total
                if not self.running or self.question_answered or self.stop_hints:
                    return
                time.sleep(0.5)
            # Timeout without hints
            if self.current_question == my_question and not self.question_answered:
                self.question_timed_out = True
                self.bot.say(f"Time's up! The answer was: {answer}", self.channel)
                self.game.check_answer(self.current_question, None)
                self.unanswered_count += 1
                
                if self.unanswered_count >= 3 and self.unanswered_count < 5:
                    self.bot.say("Warning: Nobody has answered the last 3 questions! Game will stop after 5 unanswered.", self.channel)
                elif self.unanswered_count >= 5:
                    self.bot.say("Trivia stopped due to inactivity (5 unanswered questions).", self.channel)
                    self.show_scores()
                    self.stop()
                    return
                
                if not self.next_question_scheduled:
                    self.next_question_scheduled = True
                    for _ in range(10):  # 5 second pause
                        if not self.running:
                            return
                        time.sleep(0.5)
                    if self.running:
                        self.next_question()
            return
        
        hints = self.game.generate_hints(answer, num_hints=3)
        
        # Display hints with 10-second intervals
        for hint in hints:
            # Break sleep into smaller chunks to check stop flag more frequently
            for _ in range(20):  # 20 * 0.5 = 10 seconds
                if not self.running or self.question_answered or self.stop_hints:
                    return
                time.sleep(0.5)
            
            if not self.running or self.question_answered or self.stop_hints:
                return
            # Only show hint if we're still on the same question
            if self.current_question == my_question:
                self.bot.say(f"Hint: {hint}", self.channel)
            else:
                return  # Question changed, stop this thread
        
        # Final delay before timeout (also in small chunks)
        for _ in range(20):  # 20 * 0.5 = 10 seconds
            if not self.running or self.question_answered or self.stop_hints:
                return
            time.sleep(0.5)
        
        if not self.running or self.question_answered or self.stop_hints:
            return
        
        # Only show timeout if we're still on the same question
        if self.current_question != my_question:
            return
        
        # Time's up
        self.question_timed_out = True
        self.bot.say(f"Time's up! The answer was: {answer}", self.channel)
        self.game.check_answer(self.current_question, None)
        self.unanswered_count += 1
        
        # Check inactivity
        if self.unanswered_count >= 3 and self.unanswered_count < 5:
            self.bot.say("Warning: Nobody has answered the last 3 questions! Game will stop after 5 unanswered.", self.channel)
        elif self.unanswered_count >= 5:
            self.bot.say("Trivia stopped due to inactivity (5 unanswered questions).", self.channel)
            self.show_scores()
            self.stop()
            return
        
        # Next question after 5 second pause
        if not self.next_question_scheduled:  # Only if answer didn't schedule it
            self.next_question_scheduled = True
            for _ in range(10):  # 10 * 0.5 = 5 seconds, with checks
                if not self.running:  # Only check if game stopped, not stop_hints
                    return
                time.sleep(0.5)
            
            if self.running:
                self.next_question()
    
    def check_answer(self, nick, answer_text):
        """Check if a user's answer is correct."""
        if not self.current_question or self.question_answered or self.question_timed_out:
            return False
        
        # Try to match the answer
        correct = False
        expected = self.game.get_answer_text(self.current_question).strip().lower()
        given = answer_text.strip().lower()
        
        # Check for exact match or partial match (for flexibility)
        if expected == given or expected in given or given in expected:
            correct = True
        
        if correct:
            self.question_answered = True
            self.stop_hints = True  # Stop hints immediately
            elapsed = time.time() - self.question_start_time
            
            # Update score
            old_streak = self.game.streak
            self.game.check_answer(self.current_question, given, winner_name=nick)
            
            # Calculate points (can be customized)
            points = 1
            if elapsed < 5:
                points = 3  # Fast answer bonus
            elif elapsed < 10:
                points = 2
            
            if nick not in self.scores:
                self.scores[nick] = 0
            self.scores[nick] += points
            
            # Display winner message (IRC bot style)
            answer = self.game.get_answer_text(self.current_question)
            self.bot.say(
                f"Winner: {nick}; Answer: {answer}; Time: {elapsed:.3f}s; "
                f"Streak: {self.game.streak}; Points: {points}; Total: {self.scores[nick]}",
                self.channel
            )
            
            # Record to database
            if self.game_id:
                db.record_answer(
                    self.game_id, nick, self.server, self.channel,
                    self.current_question.get('question', ''),
                    answer, points, elapsed, self.game.streak
                )
            
            self.unanswered_count = 0  # Reset inactivity counter
            
            # Schedule next question in background thread (only if not already scheduled)
            if not self.next_question_scheduled:
                self.next_question_scheduled = True
                threading.Thread(target=self._delayed_next, daemon=True).start()
            return True
        
        return False
    
    def _delayed_next(self):
        """Wait 5 seconds then ask next question."""
        try:
            # Break into smaller sleeps to check game state
            for _ in range(10):  # 10 * 0.5 = 5 seconds
                if not self.running:
                    return
                time.sleep(0.5)
            
            if self.running:
                self.next_question()
        except Exception as e:
            # Log error and try to continue anyway
            print(f"Error in _delayed_next: {e}")
            try:
                self.bot.say(f"[DEBUG] Error scheduling next question: {e}", self.channel)
            except:
                pass
    
    def end_game(self):
        """End the game and show final scores."""
        self.running = False
        
        # Update database
        if self.game_id:
            db.end_game(self.game_id, self.game.current)
        
        self.bot.say("Trivia stopped. '.trivia [number]' to start playing again.", self.channel)
        self.show_scores()
    
    def show_scores(self):
        """Display final scoreboard."""
        if not self.scores:
            return
        
        # Sort by score descending
        sorted_scores = sorted(self.scores.items(), key=lambda x: -x[1])
        
        score_text = f"Total Questions: {self.game.current}"
        self.bot.say(score_text, self.channel)
        # Show top 5 session scores and cumulative DB totals where available
        lines = []
        for nick, score in sorted_scores[:5]:
            try:
                db_stats = db.get_player_stats(nick, self.server, self.channel)
                total_db = db_stats['total_points'] if db_stats and 'total_points' in db_stats else 0
            except Exception:
                total_db = 0
            lines.append(f"{nick} ({score} points - Total: {total_db})")

        if lines:
            self.bot.say(" ".join(lines), self.channel)


@plugin.command('trivia')
@plugin.example('$trivia 10')
def trivia_start(bot, trigger):
    """Start a trivia game in the current channel."""
    channel = trigger.sender
    
    if channel in channel_games and channel_games[channel].running:
        bot.say("A trivia game is already running! Use $strivia to stop it first.", channel)
        return
    
    # Parse number of questions
    num_questions = 100  # default
    if trigger.group(2):
        try:
            num_questions = int(trigger.group(2).strip())
            if num_questions < 1:
                num_questions = 100
            elif num_questions > 500:
                num_questions = 500
        except ValueError:
            pass
    
    # Create game
    questions_file = os.path.join(os.path.dirname(__file__), 'questions.json')
    try:
        game = ChannelTrivia(bot, channel, num_questions, questions_file)
        channel_games[channel] = game
        bot.say(f"Starting trivia! {num_questions} questions loaded. Answer in the channel!", channel)
        game.start()
    except FileNotFoundError:
        bot.say("Error: questions.json not found!", channel)
    except Exception as e:
        bot.say(f"Error starting trivia: {e}", channel)


@plugin.command('strivia')
@plugin.example('$strivia')
def trivia_stop(bot, trigger):
    """Stop the current trivia game."""
    channel = trigger.sender
    
    if channel not in channel_games or not channel_games[channel].running:
        bot.say("No trivia game is currently running.", channel)
        return
    
    game = channel_games[channel]
    game.stop()
    game.show_scores()
    del channel_games[channel]


@plugin.rule(r'.*')
@plugin.priority('low')
def check_trivia_answer(bot, trigger):
    """Listen for answers to trivia questions."""
    channel = trigger.sender
    
    # Ignore if not in a channel or no game running
    if not channel.startswith('#'):
        return
    
    if channel not in channel_games or not channel_games[channel].running:
        return
    
    # Ignore commands
    if trigger.match.group(0).startswith('$'):
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
    
    # Get target nick (yourself or specified player)
    target_nick = trigger.group(2).strip() if trigger.group(2) else trigger.nick
    
    # Get stats for this channel
    stats = db.get_player_stats(target_nick, server, channel)
    
    if not stats or stats['total_points'] == 0:
        bot.say(f"{target_nick} has no trivia stats in this channel yet.", channel)
        return
    
    # Format fastest time
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
    
    top_players = db.get_channel_stats(channel, server, limit=10)
    
    if not top_players:
        bot.say("No trivia stats for this channel yet.", channel)
        return
    
    bot.say(f"🏆 Top Players in {channel}:", channel)
    for i, (nick, points, answers, wins, streak, fastest) in enumerate(top_players, 1):
        fastest_str = f"{fastest:.2f}s" if fastest else "N/A"
        bot.say(
            f"{i}. {nick}: {points} pts | {wins} wins | {streak} streak | ⚡{fastest_str}",
            channel
        )


@plugin.command('ttopserver', 'triviatopserver')
@plugin.example('$ttopserver')
def trivia_top_server(bot, trigger):
    """Show top 10 players across the entire server."""
    channel = trigger.sender
    server = bot.config.core.host if hasattr(bot.config.core, 'host') else 'default'
    
    top_players = db.get_server_stats(server, limit=10)
    
    if not top_players:
        bot.say("No trivia stats for this server yet.", channel)
        return
    
    bot.say(f"🏆 Top Players Server-Wide:", channel)
    for i, (nick, points, answers, wins, streak, fastest) in enumerate(top_players, 1):
        fastest_str = f"{fastest:.2f}s" if fastest else "N/A"
        bot.say(
            f"{i}. {nick}: {points} pts | {wins} wins | {streak} streak | ⚡{fastest_str}",
            channel
        )
