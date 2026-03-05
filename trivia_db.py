#!/usr/bin/env python3
"""Database handler for trivia game statistics."""
import sqlite3
import os
from datetime import datetime
from typing import Dict, List, Tuple, Optional


class TriviaDB:
    """Handles all trivia statistics persistence."""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = os.path.join(os.path.dirname(__file__), 'trivia_stats.db')
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize database tables."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS games (
                    game_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel TEXT NOT NULL,
                    server TEXT NOT NULL,
                    started_at TIMESTAMP NOT NULL,
                    ended_at TIMESTAMP,
                    total_questions INTEGER DEFAULT 0,
                    questions_answered INTEGER DEFAULT 0
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS player_stats (
                    player_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nick TEXT NOT NULL,
                    server TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    total_points INTEGER DEFAULT 0,
                    total_answers INTEGER DEFAULT 0,
                    total_wins INTEGER DEFAULT 0,
                    fastest_time REAL,
                    longest_streak INTEGER DEFAULT 0,
                    last_played TIMESTAMP,
                    UNIQUE(nick, server, channel)
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS game_answers (
                    answer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    game_id INTEGER NOT NULL,
                    nick TEXT NOT NULL,
                    question_text TEXT,
                    answer_text TEXT,
                    points INTEGER DEFAULT 0,
                    time_taken REAL,
                    streak INTEGER DEFAULT 0,
                    answered_at TIMESTAMP NOT NULL,
                    FOREIGN KEY (game_id) REFERENCES games(game_id)
                )
            ''')
            
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_player_stats_nick 
                ON player_stats(nick, server)
            ''')
            
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_player_stats_channel 
                ON player_stats(channel, server)
            ''')
            
            conn.commit()
    
    def start_game(self, channel: str, server: str, total_questions: int) -> int:
        """Start a new game and return game_id."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                'INSERT INTO games (channel, server, started_at, total_questions) VALUES (?, ?, ?, ?)',
                (channel, server, datetime.now(), total_questions)
            )
            conn.commit()
            return cursor.lastrowid
    
    def end_game(self, game_id: int, questions_answered: int):
        """Mark game as ended."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                'UPDATE games SET ended_at = ?, questions_answered = ? WHERE game_id = ?',
                (datetime.now(), questions_answered, game_id)
            )
            conn.commit()
    
    def record_answer(self, game_id: int, nick: str, server: str, channel: str,
                     question_text: str, answer_text: str, points: int, 
                     time_taken: float, streak: int):
        """Record a correct answer and update player stats."""
        with sqlite3.connect(self.db_path) as conn:
            # Record the answer
            conn.execute(
                '''
                INSERT INTO game_answers 
                (game_id, nick, question_text, answer_text, points, time_taken, streak, answered_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (game_id, nick, question_text, answer_text, points, time_taken, streak, datetime.now())
            )

            # Update or insert player stats. Do this in Python for clarity
            cursor = conn.execute(
                'SELECT total_points, total_answers, total_wins, fastest_time, longest_streak FROM player_stats '
                'WHERE nick = ? AND server = ? AND channel = ?',
                (nick, server, channel)
            )
            row = cursor.fetchone()
            now = datetime.now()
            if row:
                cur_points, cur_answers, cur_wins, cur_fastest, cur_longest = row
                new_points = (cur_points or 0) + points
                new_answers = (cur_answers or 0) + 1
                new_wins = (cur_wins or 0) + 1
                # Compute new fastest time (keep non-null minimum)
                if cur_fastest is None:
                    new_fastest = time_taken
                elif time_taken is None:
                    new_fastest = cur_fastest
                else:
                    new_fastest = min(cur_fastest, time_taken)
                new_longest = max(cur_longest or 0, streak or 0)

                conn.execute(
                    '''
                    UPDATE player_stats SET
                        total_points = ?,
                        total_answers = ?,
                        total_wins = ?,
                        fastest_time = ?,
                        longest_streak = ?,
                        last_played = ?
                    WHERE nick = ? AND server = ? AND channel = ?
                    ''', (
                        new_points, new_answers, new_wins, new_fastest, new_longest, now,
                        nick, server, channel
                    )
                )
            else:
                conn.execute(
                    '''
                    INSERT INTO player_stats
                    (nick, server, channel, total_points, total_answers, total_wins, fastest_time, longest_streak, last_played)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        nick, server, channel, points, 1, 1, time_taken, streak, now
                    )
                )

            conn.commit()
    
    def get_channel_stats(self, channel: str, server: str, limit: int = 10) -> List[Tuple]:
        """Get top players for a specific channel."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT nick, total_points, total_answers, total_wins, longest_streak, fastest_time
                FROM player_stats
                WHERE channel = ? AND server = ?
                ORDER BY total_points DESC, total_wins DESC
                LIMIT ?
            ''', (channel, server, limit))
            return cursor.fetchall()
    
    def get_server_stats(self, server: str, limit: int = 10) -> List[Tuple]:
        """Get top players across entire server."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT nick, SUM(total_points) as points, SUM(total_answers) as answers,
                       SUM(total_wins) as wins, MAX(longest_streak) as streak, MIN(fastest_time) as fastest
                FROM player_stats
                WHERE server = ?
                GROUP BY nick
                ORDER BY points DESC, wins DESC
                LIMIT ?
            ''', (server, limit))
            return cursor.fetchall()
    
    def get_player_stats(self, nick: str, server: str, channel: str = None) -> Optional[Dict]:
        """Get stats for a specific player."""
        with sqlite3.connect(self.db_path) as conn:
            if channel:
                cursor = conn.execute('''
                    SELECT total_points, total_answers, total_wins, longest_streak, fastest_time, last_played
                    FROM player_stats
                    WHERE nick = ? AND server = ? AND channel = ?
                ''', (nick, server, channel))
            else:
                cursor = conn.execute('''
                    SELECT SUM(total_points) as points, SUM(total_answers) as answers,
                           SUM(total_wins) as wins, MAX(longest_streak) as streak, 
                           MIN(fastest_time) as fastest, MAX(last_played) as last_played
                    FROM player_stats
                    WHERE nick = ? AND server = ?
                    GROUP BY nick
                ''', (nick, server))
            
            row = cursor.fetchone()
            if row:
                return {
                    'total_points': row[0] or 0,
                    'total_answers': row[1] or 0,
                    'total_wins': row[2] or 0,
                    'longest_streak': row[3] or 0,
                    'fastest_time': row[4],
                    'last_played': row[5]
                }
            return None
    
    def get_game_history(self, channel: str, server: str, limit: int = 5) -> List[Tuple]:
        """Get recent game history for a channel."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT game_id, started_at, ended_at, total_questions, questions_answered
                FROM games
                WHERE channel = ? AND server = ? AND ended_at IS NOT NULL
                ORDER BY ended_at DESC
                LIMIT ?
            ''', (channel, server, limit))
            return cursor.fetchall()


if __name__ == "__main__":
    # Quick test - disabled by default due to SFTP slowness
    # Uncomment to test database functionality
    pass
    '''
    print("Testing TriviaDB...")
    db = TriviaDB('test_trivia.db')
    
    game_id = db.start_game('#test', 'testserver', 10)
    print(f"Started game {game_id}")
    
    db.record_answer(game_id, 'TestUser', 'testserver', '#test', 
                     'What is 2+2?', '4', 3, 2.5, 1)
    print("Recorded answer")
    
    stats = db.get_player_stats('TestUser', 'testserver', '#test')
    print(f"Player stats: {stats}")
    
    db.end_game(game_id, 1)
    print("Ended game")
    
    print("✓ Database test complete!")
    os.remove('test_trivia.db')
    '''
