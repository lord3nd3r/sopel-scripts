ai-grok plugin
==============

Overview
--------
`ai-grok.py` is a Sopel plugin that provides an AI-powered assistant (Grok) in
channels and via private messages (PMs). It preserves per-conversation history
so replies feel contextual.

Private message (PM) behavior
-----------------------------
- Any non-banned user may PM the bot (e.g. `/msg BotName hey, how's it going?`).
- PMs are treated as implicit mentions: the bot replies in the same PM.
- Each user's PM conversation is isolated and stored under a per-user key
  so contexts do not mix between users.
- Users can clear their private conversation with:

  $grokreset

  (Run in a PM; this clears only the requesting user's PM history.)

Banning users
-------------
You can prevent specific nicks from using PMs with the `banned_nicks` option
in the `[grok]` config section (comma-separated list), for example:

[grok]
api_key = your_api_key_here
model = grok-4-1-fast-reasoning
blocked_channels = #ops,#secret
banned_nicks = baduser,spammer

At runtime you can also set `bot.memory['grok_banned']` to a list of lowercased
nicks to block them immediately.

Resetting channel history
-------------------------
- In channels, the `$grokreset` command clears the channel's Grok history.
- Channel resets are allowed for the bot owner and channel operators (+o).
- In PMs, `$grokreset` is available to any user to clear their own PM history.

Intent detection
----------------
- The plugin supports a lightweight intent-detection setting to reduce false
  triggers when your nick is mentioned incidentally. The option is
  `intent_check` in the `[grok]` config and accepts `heuristic` (default),
  `off`, or `model` (reserved for a future model-based check).
- When `heuristic` is enabled, the bot applies simple rules (vocative at the
  start/end, presence of question marks, short direct mentions, quoted/code
  exclusions) before deciding to respond. This reduces accidental replies in
  busy channels.

Notes and safety
----------------
- Existing rate-limits, sanitization, and review-mode behavior still apply.
- PM history keys are stored as `('PM', nicklower)` in `bot.memory['grok_history']`.
- The plugin checks both config `banned_nicks` and `bot.memory['grok_banned']`.

Files
-----
- `ai-grok.py` — plugin implementation (installed in `scripts/`).
- `README.md` — this file.

Questions or changes
--------------------
If you want the README expanded (examples of Sopel config formats, more
runtime controls, or a troubleshooting section), tell me which parts to add.
