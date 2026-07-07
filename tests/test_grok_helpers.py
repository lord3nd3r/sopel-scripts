import importlib.util
import os
import sys
import types

# Create minimal sopel stub modules
sopel_stub = types.ModuleType('sopel')
plugin = types.SimpleNamespace()
# dummy decorators
plugin.event = lambda *a, **k: (lambda f: f)
plugin.rule = lambda *a, **k: (lambda f: f)
plugin.priority = lambda *a, **k: (lambda f: f)
plugin.command = lambda *a, **k: (lambda f: f)

sopel_stub.plugin = plugin

# config.types stub
config_mod = types.ModuleType('sopel.config')
types_mod = types.ModuleType('sopel.config.types')
class StaticSection:
    pass
class SimpleAttr:
    def __init__(self, name, **kwargs):
        self.name = name
class SecretAttribute(SimpleAttr):
    pass
class ChoiceAttribute(SimpleAttr):
    def __init__(self, name, choices=None, default=None):
        super().__init__(name)
class ValidatedAttribute(SimpleAttr):
    def __init__(self, name, default=None):
        super().__init__(name)
class ListAttribute(SimpleAttr):
    def __init__(self, name, default=None):
        super().__init__(name)

types_mod.StaticSection = StaticSection
types_mod.SecretAttribute = SecretAttribute
types_mod.ChoiceAttribute = ChoiceAttribute
types_mod.ValidatedAttribute = ValidatedAttribute
types_mod.ListAttribute = ListAttribute

config_mod.types = types_mod
sopel_stub.config = config_mod

sys.modules['sopel'] = sopel_stub
sys.modules['sopel.config'] = config_mod
sys.modules['sopel.config.types'] = types_mod

# Load ai-grok.py by path
TEST_DIR = os.path.dirname(__file__)
FILE_PATH = os.path.abspath(os.path.join(TEST_DIR, '..', 'ai-grok.py'))
spec = importlib.util.spec_from_file_location('ai_grok', FILE_PATH)
ai_grok = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ai_grok)


def test_heuristic_positive():
    class T: pass
    t = T()
    t.nick = 'm0n'
    line = 'glitchy: do this please'
    assert ai_grok._heuristic_intent_check(None, t, line, 'glitchy') is True


def test_heuristic_negative():
    class T: pass
    t = T()
    t.nick = 'm0n'
    line = "my code is glitchy and slow"
    assert ai_grok._heuristic_intent_check(None, t, line, 'glitchy') is False


def test_sanitize_reply():
    class Bot: 
        def __init__(self):
            self.memory = {}
        def logger(self):
            return None
    class Trigger:
        nick = 'm0n'
    bot = Bot()
    trig = Trigger()
    reply = "Here's code:\n```print('hi')``` and ping @everyone and art:\n╔═╗\n║ ║\n╚═╝\n" + "x"*1500
    out = ai_grok.sanitize_reply(bot, trig, reply)
    assert 'code removed' in out or 'I was gonna draw' in out or '@everyone' not in out
    assert len(out) <= 1405


