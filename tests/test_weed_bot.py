import importlib.util
import os
import sys
import types
import random
import time

# Inject sopel stub like the other test does
sopel_stub = types.ModuleType('sopel')

class _module:
    @staticmethod
    def commands(*names):
        return lambda f: f

    @staticmethod
    def example(*args, **kwargs):
        return lambda f: f

    @staticmethod
    def rule(*args, **kwargs):
        return lambda f: f


class _ColorsMeta(type):
    def __getattr__(cls, name):
        return name


class _Colors(metaclass=_ColorsMeta):
    pass


class _formatting:
    colors = _Colors

    @staticmethod
    def color(text, color):
        return text

    @staticmethod
    def bold(text):
        return text


sopel_stub.module = _module
sopel_stub.formatting = _formatting
sys.modules['sopel'] = sopel_stub

# Load weed.py directly
TEST_DIR = os.path.dirname(__file__)
WEED_PATH = os.path.abspath(os.path.join(TEST_DIR, '..', 'weed.py'))
spec = importlib.util.spec_from_file_location('weed', WEED_PATH)
weed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(weed)


class DummyBot:
    def __init__(self):
        self.says = []
        self.actions = []
        self.notices = []
        self.channels = {
            '#chan': types.SimpleNamespace(users={'sender': {}, 'alice': {}, 'bob': {}, 'target': {}})
        }

    def say(self, text, target=None):
        self.says.append((text, target))

    def action(self, text):
        self.actions.append(text)

    def notice(self, text, nick):
        self.notices.append((text, nick))


class Trigger:
    def __init__(self, sender, nick, account=None, group1='weed', group2=None):
        self.sender = sender
        self.nick = nick
        self.account = account
        self._group1 = group1
        self._group2 = group2

    def group(self, n=0):
        if n == 1:
            return self._group1
        if n == 2:
            return self._group2
        if n == 0:
            return f"{self.nick}: ${self._group1} {self._group2 or ''}".strip()
        return None


def test_target_gift():
    random.seed(0)
    bot = DummyBot()
    trig = Trigger('#chan', 'sender', group1='weed', group2='target')
    # clear state
    weed.LAST_USED.clear()
    weed.PER_USER_LAST.clear()
    weed.weed_commands(bot, trig)
    assert len(bot.actions) == 1
    assert 'target' in bot.actions[0]


def test_jay_command():
    random.seed(0)
    bot = DummyBot()
    trig = Trigger('#chan', 'sender', group1='jay', group2='target')
    weed.LAST_USED.clear()
    weed.PER_USER_LAST.clear()
    weed.weed_commands(bot, trig)
    assert len(bot.actions) == 1
    assert 'target' in bot.actions[0]


def test_doobie_command():
    random.seed(0)
    bot = DummyBot()
    trig = Trigger('#chan', 'sender', group1='doobie', group2='target')
    weed.LAST_USED.clear()
    weed.PER_USER_LAST.clear()
    weed.weed_commands(bot, trig)
    assert len(bot.actions) == 1
    assert 'target' in bot.actions[0]
    assert 'doobie' in bot.actions[0]



def test_per_user_cooldown():
    bot = DummyBot()
    trig = Trigger('#chan', 'alice', group1='weed', group2='target')
    weed.LAST_USED.clear()
    weed.PER_USER_LAST.clear()

    # patch time to deterministic values
    orig_time = weed.time.time
    try:
        weed.time.time = lambda: 1000.0
        # first call should succeed
        weed.weed_commands(bot, trig)
        assert len(bot.actions) == 1
        # second call shortly after should get a notice
        weed.time.time = lambda: 1001.0
        weed.weed_commands(bot, trig)
        assert len(bot.notices) >= 1
    finally:
        weed.time.time = orig_time


def test_channel_cooldown_blocks_others():
    bot = DummyBot()
    t1 = Trigger('#chan', 'alice', group1='weed')
    t2 = Trigger('#chan', 'bob', group1='weed')
    weed.LAST_USED.clear()
    weed.PER_USER_LAST.clear()

    orig_time = weed.time.time
    try:
        weed.time.time = lambda: 2000.0
        weed.weed_commands(bot, t1)
        # different user soon after should be blocked by channel cooldown
        weed.time.time = lambda: 2001.0
        weed.weed_commands(bot, t2)
        assert any('on cooldown' in n[0] or 'wait' in n[0] for n in bot.notices)
    finally:
        weed.time.time = orig_time

