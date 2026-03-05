from __future__ import annotations

import os
import sqlite3
import threading
import time
from datetime import datetime, timezone

from sopel import plugin
from sopel.config.types import BooleanAttribute, FilenameAttribute, ListAttribute, StaticSection


class ChannelStatsSection(StaticSection):
	# Eligible channels the bot is in (the “40 channels” list)
	channels = ListAttribute("channels", default=[])
	# If True, admins can add channels to the eligible list at runtime via `.monitor on #channel`
	# (stored in the plugin DB so it persists across restarts)
	allow_admin_add = BooleanAttribute("allow_admin_add", default=False)
	# Stored next to the Sopel config file when relative
	db_path = FilenameAttribute("db_path", default="monitor.db")
	# If True, all eligible channels are monitored unless explicitly disabled
	default_enabled = BooleanAttribute("default_enabled", default=False)


_DB_LOCK = threading.Lock()


def setup(bot):
	bot.config.define_section("channelstats", ChannelStatsSection)
	_init_db(_get_db_path(bot))


def _get_db_path(bot) -> str:
	path = bot.config.channelstats.db_path
	if os.path.isabs(path):
		return path

	# Put the SQLite DB next to the bot's config file
	config_filename = getattr(bot.config, "filename", None)
	if config_filename:
		base_dir = os.path.dirname(os.path.abspath(config_filename))
	else:
		# Fallback if Sopel doesn't expose config path
		base_dir = os.getcwd()

	return os.path.join(base_dir, path)


def _connect(db_path: str) -> sqlite3.Connection:
	conn = sqlite3.connect(db_path, timeout=30)
	conn.execute("PRAGMA journal_mode=WAL;")
	conn.execute("PRAGMA synchronous=NORMAL;")
	return conn


def _init_db(db_path: str) -> None:
	with _DB_LOCK:
		conn = _connect(db_path)
		try:
			conn.execute(
				"""
				CREATE TABLE IF NOT EXISTS stats (
					channel TEXT NOT NULL,
					nick TEXT NOT NULL,
					messages INTEGER NOT NULL DEFAULT 0,
					first_seen INTEGER NOT NULL,
					last_seen INTEGER NOT NULL,
					PRIMARY KEY(channel, nick)
				)
				"""
			)
			conn.execute(
				"""
				CREATE TABLE IF NOT EXISTS enabled_channels (
					channel TEXT PRIMARY KEY,
					enabled INTEGER NOT NULL,
					updated_at INTEGER NOT NULL
				)
				"""
			)
			conn.execute(
				"CREATE INDEX IF NOT EXISTS idx_stats_channel_messages ON stats(channel, messages DESC)"
			)
			conn.execute(
				"""
				CREATE TABLE IF NOT EXISTS eligible_channels (
					channel TEXT PRIMARY KEY,
					added_by TEXT,
					updated_at INTEGER NOT NULL
				)
				"""
			)
			conn.commit()
		finally:
			conn.close()


def _db_eligible_channels(bot) -> set[str]:
	db_path = _get_db_path(bot)
	with _DB_LOCK:
		conn = _connect(db_path)
		try:
			rows = conn.execute("SELECT channel FROM eligible_channels").fetchall()
		finally:
			conn.close()
	return {r[0].strip().lower() for r in rows if r and r[0]}


def _add_db_eligible_channel(bot, channel: str, added_by: str | None = None) -> None:
	channel = channel.strip().lower()
	if not channel.startswith("#"):
		return
	ts = int(time.time())
	db_path = _get_db_path(bot)
	with _DB_LOCK:
		conn = _connect(db_path)
		try:
			conn.execute(
				"""
				INSERT INTO eligible_channels(channel, added_by, updated_at)
				VALUES(?, ?, ?)
				ON CONFLICT(channel) DO UPDATE SET
					added_by = excluded.added_by,
					updated_at = excluded.updated_at
				""",
				(channel, added_by, ts),
			)
			conn.commit()
		finally:
			conn.close()


def _eligible_channels(bot) -> set[str]:
	chans = list(bot.config.channelstats.channels or [])
	from_config = {c.strip().lower() for c in chans if c and c.strip().startswith("#")}
	# Merge in channels added at runtime (persisted in plugin DB)
	return from_config | _db_eligible_channels(bot)


def _is_enabled(bot, channel: str) -> bool:
	channel = channel.lower()
	default_enabled = bool(bot.config.channelstats.default_enabled)

	db_path = _get_db_path(bot)
	with _DB_LOCK:
		conn = _connect(db_path)
		try:
			row = conn.execute(
				"SELECT enabled FROM enabled_channels WHERE channel = ?",
				(channel,),
			).fetchone()
		finally:
			conn.close()

	if row is None:
		return default_enabled
	return bool(row[0])


def _set_enabled(bot, channel: str, enabled: bool) -> None:
	channel = channel.lower()
	ts = int(time.time())
	db_path = _get_db_path(bot)

	with _DB_LOCK:
		conn = _connect(db_path)
		try:
			conn.execute(
				"""
				INSERT INTO enabled_channels(channel, enabled, updated_at)
				VALUES(?, ?, ?)
				ON CONFLICT(channel) DO UPDATE SET
					enabled = excluded.enabled,
					updated_at = excluded.updated_at
				""",
				(channel, 1 if enabled else 0, ts),
			)
			conn.commit()
		finally:
			conn.close()


def _is_monitored(bot, channel: str) -> bool:
	channel = channel.lower()
	return channel in _eligible_channels(bot) and _is_enabled(bot, channel)


def _touch_message(bot, channel: str, nick: str, ts: int) -> None:
	db_path = _get_db_path(bot)
	with _DB_LOCK:
		conn = _connect(db_path)
		try:
			conn.execute(
				"""
				INSERT INTO stats(channel, nick, messages, first_seen, last_seen)
				VALUES(?, ?, 1, ?, ?)
				ON CONFLICT(channel, nick) DO UPDATE SET
					messages = messages + 1,
					last_seen = excluded.last_seen
				""",
				(channel.lower(), nick, ts, ts),
			)
			conn.commit()
		finally:
			conn.close()


@plugin.event("PRIVMSG")
@plugin.rule(".*")
@plugin.require_chanmsg
def track_messages(bot, trigger):
	channel = trigger.sender
	if not _is_monitored(bot, channel):
		return
	if trigger.nick == bot.nick:
		return

	_touch_message(bot, channel, trigger.nick, int(time.time()))


def _format_ts(ts: int) -> str:
	dt = datetime.fromtimestamp(ts, tz=timezone.utc)
	return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


@plugin.commands("monitor")
@plugin.require_privmsg
@plugin.require_admin
def monitor_control(bot, trigger):
	"""PM-only admin control.

	.monitor on #channel
	.monitor off #channel
	.monitor list
	"""

	args = (trigger.group(2) or "").strip().split()
	if not args:
		bot.reply("Usage: .monitor on|off #channel  OR  .monitor list")
		return

	sub = args[0].lower()
	eligible = _eligible_channels(bot)

	if sub == "list":
		enabled = sorted([c for c in eligible if _is_enabled(bot, c)])
		if not enabled:
			bot.reply("No channels enabled for monitoring.")
		else:
			bot.reply("Monitoring enabled in: " + ", ".join(enabled))
		return

	if sub not in {"on", "off"} or len(args) < 2:
		bot.reply("Usage: .monitor on|off #channel  OR  .monitor list")
		return

	channel = args[1].lower()
	if channel not in eligible:
		# Optional: allow admins to add channels at runtime without a bot restart
		if bool(getattr(bot.config.channelstats, "allow_admin_add", False)):
			if hasattr(bot, "channels"):
				current = {c.lower() for c in bot.channels.keys()}
				if channel not in current:
					bot.reply(f"I'm not currently in {channel}.")
					return
			_add_db_eligible_channel(bot, channel, added_by=trigger.nick)
			eligible = _eligible_channels(bot)
		else:
			current = ", ".join(sorted(eligible)) if eligible else "(none configured)"
			bot.reply(
				f"{channel} is not in the eligible channel list in config. "
				f"Eligible: {current}. Add it under [channelstats] channels."
			)
			return

	# Optional safety: ensure bot is actually in that channel
	if hasattr(bot, "channels"):
		current = {c.lower() for c in bot.channels.keys()}
		if channel not in current:
			bot.reply(f"I'm not currently in {channel}.")
			return

	_set_enabled(bot, channel, enabled=(sub == "on"))
	bot.reply(f"Monitoring {'ENABLED' if sub == 'on' else 'DISABLED'} for {channel}.")


@plugin.commands("channelstats")
@plugin.require_chanmsg
def channelstats(bot, trigger):
	channel = trigger.sender
	if not _is_monitored(bot, channel):
		bot.say("Monitoring is not enabled in this channel.")
		return

	def _say_list(label: str, parts: list[str], max_bytes: int = 350) -> None:
		# IRC messages have tight length limits; chunk long lists so we don't lose a line.
		if not parts:
			bot.say(f"{label}: (none)")
			return
		prefix = f"{label}: "
		line = prefix
		for part in parts:
			sep = "" if line == prefix else ", "
			candidate = line + sep + part
			if len(candidate.encode("utf-8", "replace")) > max_bytes and line != prefix:
				bot.say(line)
				line = prefix + part
			else:
				line = candidate
		bot.say(line)

	def _rating_per_hour(messages: int, first_seen: int, last_seen: int) -> float:
		active_seconds = max(0, int(last_seen) - int(first_seen))
		window_seconds = max(3600, active_seconds)  # clamp to 1h to avoid noisy spikes
		return float(messages) * 3600.0 / float(window_seconds)

	def _fmt_rate_per_hour(rate: float) -> str:
		# Short/clean output: at most 1 decimal.
		return f"{rate:.0f}/hr" if rate >= 10 else f"{rate:.1f}/hr"

	def _fmt_entry(rank: int, nick: str, messages: int, first_seen: int, last_seen: int) -> str:
		rate = _rating_per_hour(messages, first_seen, last_seen)
		# Keep it compact, but make the top 3 stand out.
		if rank == 1:
			return f"🥇{nick} {messages} ({_fmt_rate_per_hour(rate)})"
		if rank == 2:
			return f"🥈{nick} {messages} ({_fmt_rate_per_hour(rate)})"
		if rank == 3:
			return f"🥉{nick} {messages} ({_fmt_rate_per_hour(rate)})"
		return f"{rank}) {nick} {messages} ({_fmt_rate_per_hour(rate)})"

	db_path = _get_db_path(bot)
	with _DB_LOCK:
		conn = _connect(db_path)
		try:
			top = conn.execute(
				"""
				SELECT nick, messages, first_seen, last_seen
				FROM stats
				WHERE channel = ?
				ORDER BY messages DESC, nick ASC
				LIMIT 10
				""",
				(channel.lower(),),
			).fetchall()
		finally:
			conn.close()

	if not top:
		bot.say("No stats yet for this channel.")
		return

	top_parts = []
	for i, (n, c, first_seen, last_seen) in enumerate(top, start=1):
		top_parts.append(_fmt_entry(i, n, c, first_seen, last_seen))
	_say_list("Top 10", top_parts)


@plugin.commands("userstats")
@plugin.require_chanmsg
def userstats(bot, trigger):
	channel = trigger.sender
	if not _is_monitored(bot, channel):
		bot.say("Monitoring is not enabled in this channel.")
		return

	nick = (trigger.group(2) or "").strip() or trigger.nick

	db_path = _get_db_path(bot)
	with _DB_LOCK:
		conn = _connect(db_path)
		try:
			row = conn.execute(
				"""
				SELECT messages, first_seen, last_seen
				FROM stats
				WHERE channel = ? AND nick = ?
				""",
				(channel.lower(), nick),
			).fetchone()
		finally:
			conn.close()

	if not row:
		bot.say(f"No stats for {nick} in {channel} yet.")
		return

	messages, first_seen, last_seen = row
	active_seconds = max(0, int(last_seen) - int(first_seen))
	window_seconds = max(3600, active_seconds)  # clamp to 1h to avoid noisy spikes
	rating_per_hour = float(messages) * 3600.0 / float(window_seconds)
	bot.say(
		f"{nick} in {channel}: messages={messages}, rating={rating_per_hour:.2f} msg/hr, "
		f"time_active={active_seconds}s, first_seen={_format_ts(first_seen)}, last_seen={_format_ts(last_seen)}"
	)
