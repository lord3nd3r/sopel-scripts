"""
Sopel Bartender Module - Your friendly virtual bartender!
Serves up random beers, shots, whiskeys, cocktails, and pizza.
Uses unified bot.db for persistence (same as mug.py).
Deducts from mug game coins instead of maintaining separate balance.
"""
import random
import time
import logging
import atexit
import unicodedata
from sopel import module
import re


LOG = logging.getLogger(__name__)
PLUGIN_NAME = 'beer'
MUG_GAME_PLUGIN = 'mug_game'
NEW_USER_STARTING_COINS = 1000  # Starting coins for users on first drink purchase
DAILY_BONUS_COINS = 100  # Bonus coins given once per 24 hours

# IRC format/control regex patterns (from mug.py)
_MIRC_COLOR_RE = re.compile(r'\x03(?:\d{1,2})?(?:,\d{1,2})?')
_IRC_FORMAT_RE = re.compile(r'[\x02\x1d\x1f\x11\x16]')
_IRC_CTRL_RE = re.compile(r'[\x00-\x08\x0b-\x0c\x0e-\x1a]')


def _normalize_nick(nick: str) -> str:
    """Normalize nickname following mug.py standards."""
    if not nick:
        return ""
    s = str(nick)
    s = unicodedata.normalize('NFKC', s)
    s = _MIRC_COLOR_RE.sub('', s)
    s = _IRC_FORMAT_RE.sub('', s)
    s = _IRC_CTRL_RE.sub('', s)
    return s.strip()


def _user_key(user):
    """Normalize user identifier for storage (use lowercase strings)."""
    return _normalize_nick(user).lower()



def _load_mug_data(bot):
    """Load mug game data from bot.db."""
    try:
        data = bot.db.get_plugin_value(MUG_GAME_PLUGIN, 'data')
        if isinstance(data, dict):
            return data
    except (AttributeError, KeyError, TypeError) as e:
        LOG.warning(f"Failed to load mug game data: {e}")
    return {'users': {}}


def _save_mug_data(bot, data):
    """Save mug game data to bot.db atomically."""
    try:
        bot.db.set_plugin_value(MUG_GAME_PLUGIN, 'data', data)
    except (AttributeError, TypeError, ValueError) as e:
        LOG.error(f"ERROR saving mug game data: {e}")
        return False
    return True


def _load_tip_data(bot):
    """Load tip data from bot.db with fallback to empty structure."""
    try:
        data = bot.db.get_plugin_value(PLUGIN_NAME, 'tips')
        if data and isinstance(data, dict):
            return data
    except (AttributeError, KeyError, TypeError) as e:
        LOG.warning(f"Failed to load tip data: {e}")
    return {'balances': {}, 'last_credit': {}, 'tips_received': {}}


def _save_tip_data(bot, data):
    """Save tip data to bot.db atomically."""
    try:
        bot.db.set_plugin_value(PLUGIN_NAME, 'tips', data)
    except (AttributeError, TypeError, ValueError) as e:
        LOG.error(f"ERROR saving tip data: {e}")
        return False
    return True


def _get_user_coins(bot, user):
    """Get user's current mug game coin balance."""
    data = _load_mug_data(bot)
    users = data.get('users', {})
    user_key = _user_key(user)
    
    if user_key in users and isinstance(users[user_key], dict):
        return int(users[user_key].get('money', 0))
    return 0


def _deduct_mug_coins(bot, user, amount):
    """Deduct coins from user's mug game balance.
    Returns (new_balance, success, was_new_user, got_daily_bonus) where:
    - new_balance: resulting balance or None if insufficient
    - success: True if deduction succeeded
    - was_new_user: True if this was their first time (got starting coins)
    - got_daily_bonus: True if they received daily bonus coins
    """
    if amount <= 0:
        balance = _get_user_coins(bot, user)
        return balance, True, False, False
    
    data = _load_mug_data(bot)
    users = data.get('users', {})
    user_key = _user_key(user)
    current_time = time.time()
    
    was_new = False
    got_daily = False
    
    # Get or initialize user record
    if user_key not in users or not isinstance(users[user_key], dict):
        # New user: give them starting coins
        users[user_key] = {
            'nick': user,
            'money': NEW_USER_STARTING_COINS,
            'inv': {},
            'last_bar_credit': current_time
        }
        was_new = True
        LOG.debug(f"New user {user_key} initialized with {NEW_USER_STARTING_COINS} starting coins")
    
    user_rec = users[user_key]
    current_balance = int(user_rec.get('money', 0))
    
    # Check for daily bonus (24 hour cooldown)
    last_credit = user_rec.get('last_bar_credit', 0)
    if current_time - last_credit >= 86400:  # 24 hours in seconds
        current_balance += DAILY_BONUS_COINS
        user_rec['money'] = current_balance
        user_rec['last_bar_credit'] = current_time
        got_daily = True
        LOG.debug(f"User {user_key} received daily bonus of {DAILY_BONUS_COINS} coins")
    
    # Check if user has enough
    if current_balance < amount:
        # Save any daily bonus that was just added
        if got_daily:
            _save_mug_data(bot, data)
        return None, False, was_new, got_daily  # Insufficient funds
    
    # Deduct the amount
    new_balance = current_balance - amount
    user_rec['money'] = new_balance
    
    # Save back to bot.db
    if _save_mug_data(bot, data):
        LOG.debug(f"Deducted {amount} coins from {user_key}: {current_balance} -> {new_balance}")
        return new_balance, True, was_new, got_daily
    
    LOG.error(f"Failed to save mug data after deducting {amount} from {user_key}")
    return None, False, was_new, got_daily

# Prices for items

PRICES = {
    'beer': 5,
    'shot': 7,
    'whiskey': 12,
    'vodka': 10,
    'rum': 10,
    'tequila': 10,
    'gin': 10,
    'brandy': 12,
    'mixed_drink': 10,
    'wine': 8,
    'magners': 6,
    'mocktail': 4,
    'coffee': 3,
    'tea': 3,
    'water': 0,  # Water is free!
    'pizza': 15,
    'appetizer': 8,
}


def deduct_price(bot, user, item_type):
    """Deduct price from user's mug game coins.
    Returns (new_balance, price, was_new_user, got_daily_bonus)
    """
    price = PRICES.get(item_type, 0)
    
    # Free items don't require deduction
    if price <= 0:
        balance = _get_user_coins(bot, user)
        return balance, price, False, False
    
    # Deduct from mug game coins
    new_balance, success, was_new, got_daily = _deduct_mug_coins(bot, user, price)
    
    if not success:
        return None, price, was_new, got_daily
    
    return new_balance, price, was_new, got_daily


# Item lookup: maps item type to (item_list, message_template_list, placeholder_key)
DRINK_REGISTRY = {}


def _serve_item(bot, trigger, item_type, item_list, message_list, placeholder_key='drink'):
    """Generic handler for serving any drink or food item.
    
    Args:
        bot: Sopel bot
        trigger: IRC trigger
        item_type: Key in PRICES dict
        item_list: List of drink/food options
        message_list: List of message templates
        placeholder_key: 'drink' or 'food' for message formatting
    """
    try:
        # Parse target user (may be empty)
        if not trigger.group(2):
            target_user = trigger.nick
        else:
            target_user = trigger.group(2).strip()
        
        # Deduct price
        sender = trigger.account or trigger.nick
        new_balance, price, was_new_user, got_daily_bonus = deduct_price(bot, sender, item_type)
        
        if new_balance is None:
            current_balance = _get_user_coins(bot, sender)
            bot.say(f"{trigger.nick}: You don't have enough coins! {item_type.capitalize()} costs {price} coins. You have {current_balance} coins.")
            return
        
        # Select random item and message
        chosen_item = random.choice(item_list)
        giving_message = random.choice(message_list)
        
        # Format and send message
        message = giving_message.format(**{placeholder_key: chosen_item, 'user': target_user})
        bot.action(message)
        
        # Send balance update via PM
        if price > 0:
            if was_new_user:
                bot.notice(f"Welcome to the bar! 🍺 You received {NEW_USER_STARTING_COINS} starting coins.\nPaid {price} coins - Remaining balance: {new_balance} coins 🪙", trigger.nick)
            elif got_daily_bonus:
                bot.notice(f"Daily bonus! +{DAILY_BONUS_COINS} coins 💰\nPaid {price} coins - Remaining balance: {new_balance} coins 🪙", trigger.nick)
            else:
                bot.notice(f"Paid {price} coins - Remaining balance: {new_balance} coins 🪙", trigger.nick)
    
    except Exception as e:
        LOG.error(f"Error in _serve_item for {item_type}: {e}")
        try:
            bot.say(f"{trigger.nick}: An error occurred. Sorry!")
        except Exception:
            pass

# List of fun beers to give out
BEERS = [
    "a frosty Guinness 🍺",
    "an ice-cold Heineken 🍻",
    "a refreshing Corona with lime 🍋🍺",
    "a crisp Pilsner Urquell 🍺",
    "a hoppy IPA 🌿🍺",
    "a smooth Stella Artois 🍺",
    "a Belgian Trappist ale 🍺✨",
    "a fruity Lambic 🍓🍺",
    "a dark porter 🖤🍺",
    "a craft wheat beer 🌾🍺",
    "a chilled Budweiser 🧊🍺",
    "a golden lager 💛🍺",
    "a tasty amber ale 🍺",
    "a strong Belgian triple 💪🍺",
    "a refreshing pale ale 🍺",
    "a German weissbier 🇩🇪🍺",
    "a Japanese Asahi Super Dry 🇯🇵🍺",
    "a Mexican Modelo Especial 🇲🇽🍺",
    "a smooth stout 🍺",
    "a citrusy session IPA 🍊🍺",
]

# List of fun shots to give out
SHOTS = [
    "a shot of Jägermeister 🦌🥃",
    "a tequila shot with salt & lime 🧂🍋🥃",
    "a flaming Sambuca 🔥🥃",
    "a smooth vodka shot 🧊🥃",
    "a shot of Fireball 🔥🌶️🥃",
    "a B-52 shooter 💣🥃",
    "a kamikaze shot ✈️🥃",
    "a lemon drop shot 🍋✨🥃",
    "a buttery nipple 🧈🥃",
    "a mind eraser 🧠💥🥃",
    "a Vegas bomb 🎰💣🥃",
    "a shot of Patrón Silver 💎🥃",
    "a pickle back 🥒🥃",
    "a Jägerbomb 🦌💣🥃",
    "a Washington apple shot 🍎🥃",
    "a pineapple upside down shot 🍍🥃",
    "a royal flush shot 👑🥃",
    "a brain hemorrhage 🧠🩸🥃",
    "a liquid cocaine shot ⚡🥃",
    "a prairie fire 🔥🥃",
]

# List of Magners ciders to give out
MAGNERS = [
    "a crisp Magners Original Irish Cider 🍎🍺",
    "an ice-cold Magners Original over ice 🧊🍎",
    "a refreshing Magners Pear Cider 🍐✨",
    "a chilled Magners Berry Cider 🫐🍓🍺",
    "a frosty Magners Dark Fruit 🖤🍒🍺",
    "a smooth Magners Rosé Cider 🌹🍎",
    "a golden Magners on the rocks 🧊🍎🍺",
    "a crisp Magners straight from the tap 🍺🍎",
    "a perfectly chilled Magners 🌡️🍎",
    "a sweet Magners with extra ice 🧊🧊🍎",
]

# List of whiskeys to give out
WHISKEYS = [
    "a glass of smooth Jameson 🇮🇪🥃",
    "a dram of Glenfiddich 🏴🥃",
    "a pour of Jack Daniel's 🇺🇸🥃",
    "a shot of Maker's Mark 🔴🥃",
    "a glass of peaty Laphroaig 🏴💨🥃",
    "a tumbler of Bulleit Bourbon 🤠🥃",
    "a measure of Talisker 🌊🥃",
    "a dram of Macallan 12 Year 💎🥃",
    "a glass of Wild Turkey 🦃🥃",
    "a pour of Bushmills 🇮🇪🥃",
    "a shot of Crown Royal 👑🥃",
    "a glass of Johnnie Walker Black ⚫🥃",
    "a dram of Highland Park 🏔️🥃",
    "a measure of Ardbeg 🏴💚🥃",
    "a pour of Four Roses 🌹🥃",
    "a tumbler of Knob Creek 🌽🥃",
    "a glass of Redbreast 12 🇮🇪🔴🥃",
    "a shot of Woodford Reserve 🐴🥃",
    "a dram of Oban 14 🏴🥃",
    "a pour of Buffalo Trace 🦬🥃",
]

# List of vodkas to give out
VODKAS = [
    "a chilled Belvedere on the rocks 🇵🇱🧊🥃",
    "an ice-cold Grey Goose 🪿🧊🥃",
    "a smooth Ketel One 🇳🇱🥃",
    "a crisp Stolichnaya 🇷🇺🥃",
    "a premium Ciroc 🍇🥃",
    "a clean Absolut 🇸🇪🥃",
    "a silky Chopin 🎹🥃",
    "a refined Beluga Noble 🐋🥃",
    "a classic Smirnoff 🧊🥃",
    "a Polish Żubrówka Bison Grass 🦬🌿🥃",
    "a French Cîroc Pineapple 🍍🥃",
    "a crystal-clear Reyka from Iceland 🇮🇸🧊🥃",
    "a handcrafted Tito's 🇺🇸🥃",
    "a velvety Russian Standard 🇷🇺🥃",
    "a botanical Hangar 1 🌿🥃",
    "a crisp Finlandia 🇫🇮🥃",
    "a smooth Skyy 🔵🥃",
    "a premium Purity 34 🇸🇪✨🥃",
    "a fiery Absolut Peppar 🌶️🥃",
    "a sweet Absolut Vanilia 🍦🥃",
]

# List of rums to give out
RUMS = [
    "a smooth Diplomático Reserva Exclusiva 🇻🇪🥃",
    "a dark Kraken Black Spiced 🐙🏴🥃",
    "a golden Appleton Estate 🇯🇲🥃",
    "a classic Bacardi Superior 🇨🇺🥃",
    "a rich Ron Zacapa 23 🇬🇹🥃",
    "a spiced Captain Morgan 🏴‍☠️🥃",
    "a sipping Mount Gay Eclipse 🇧🇧🥃",
    "an aged Flor de Caña 18 🇳🇮🥃",
    "a smooth Havana Club 7 🇨🇺🥃",
    "a premium Plantation XO 🌴🥃",
    "a funky Smith & Cross 🇯🇲💪🥃",
    "a velvety El Dorado 15 🇬🇾✨🥃",
    "a coconut Malibu 🥥🌴🥃",
    "a dark Myers's Original 🇯🇲🖤🥃",
    "a cask-aged Pusser's 🏴‍☠️🥃",
    "a sipping Doorly's 12 🇧🇧🥃",
    "a crisp Banks 5 Island 🏝️🥃",
    "a bold Gosling's Black Seal 🇧🇲🥃",
    "a tropical Rhum J.M VSOP 🇲🇶🥃",
    "an overproof Wray & Nephew 🇯🇲🔥🥃",
]

# List of tequilas to give out
TEQUILAS = [
    "a smooth Patrón Silver 💎🥃",
    "a premium Don Julio 1942 🇲🇽👑🥃",
    "a crisp Casamigos Blanco 🇲🇽🥃",
    "a golden Herradura Reposado 🐴🥃",
    "a rich Clase Azul Reposado 🇲🇽🏺🥃",
    "a smoky Fortaleza Añejo 🔥🥃",
    "a classic Jose Cuervo Reserva 🇲🇽🥃",
    "a sipping El Tesoro Añejo 🏺🥃",
    "a fiery Espolòn Blanco 🐓🥃",
    "a velvety Ocho Reposado 🇲🇽✨🥃",
    "a top-shelf Casa Noble Crystal 💎🥃",
    "a bold Tapatio 110 🇲🇽💪🥃",
    "a smooth Avión Silver 🇲🇽✈️🥃",
    "a premium Tears of Llorona Extra Añejo 💧👑🥃",
    "a crisp Olmeca Altos Plata 🌵🥃",
    "a aged Gran Centenario Añejo 🇲🇽🥃",
    "a crystalline Código 1530 Rosa 🌹🥃",
    "a artisanal Siete Leguas Blanco 🇲🇽🌿🥃",
    "a smoky mezcal Del Maguey Vida 🔥🌵🥃",
    "a legendary Mezcal Vago Elote 🌽🔥🥃",
]

# List of gins to give out
GINS = [
    "a classic Tanqueray 🌿🥃",
    "a floral Hendrick's 🥒🌸🥃",
    "a crisp Bombay Sapphire 💎🔵🥃",
    "a bold Beefeater 🇬🇧🥃",
    "a smooth Monkey 47 🐒🌿🥃",
    "a refined Sipsmith London Dry 🇬🇧🥃",
    "a aromatic The Botanist 🏴󠁧󠁢󠁳󠁣󠁴󠁿🌿🥃",
    "a premium Aviation 🇺🇸✈️🥃",
    "a juniper-forward Plymouth 🌲🥃",
    "a citrusy Malfy Con Limone 🇮🇹🍋🥃",
    "a Spanish Gin Mare 🇪🇸🫒🥃",
    "a Japanese Roku 🇯🇵🌸🥃",
    "a pink Gordon's Pink 🩷🥃",
    "a barrel-aged Few 🇺🇸🪵🥃",
    "a summery Whitley Neill Rhubarb & Ginger 🫚🥃",
    "a classic Bols Genever 🇳🇱🥃",
    "a herbaceous St. George Terroir 🌿🏔️🥃",
    "a elegant No. 3 London Dry 🇬🇧👑🥃",
    "a tropical Tarquin's Cornish Gin 🇬🇧🌊🥃",
    "a floral Empress 1908 💜🥃",
]

# List of brandies/cognacs to give out
BRANDIES = [
    "a luxurious Hennessy XO 🇫🇷👑🥃",
    "a smooth Rémy Martin VSOP 🇫🇷🥃",
    "a refined Courvoisier VS 🇫🇷🥃",
    "a premium Martell Cordon Bleu 🇫🇷💙🥃",
    "a aged Hine Rare VSOP 🇫🇷🥃",
    "a elegant Pierre Ferrand 1840 🇫🇷✨🥃",
    "a velvety Camus XO 🇫🇷🥃",
    "a classic Torres 10 🇪🇸🥃",
    "a German Asbach Uralt 🇩🇪🥃",
    "a smooth Metaxa 7 Star 🇬🇷⭐🥃",
    "a fruity calvados Père Magloire VSOP 🍎🇫🇷🥃",
    "a rich Delamain XO 🇫🇷👑🥃",
    "a sipping Hardy VSOP 🇫🇷🥃",
    "a South African KWV 10 🇿🇦🥃",
    "a Peruvian Pisco Portón 🇵🇪🥃",
    "a Armenian Ararat 10 Year 🇦🇲🥃",
    "a Georgian Sarajishvili VS 🇬🇪🥃",
    "a Italian Vecchia Romagna 🇮🇹🥃",
    "a warming Brandy de Jerez Solera 🇪🇸🥃",
    "a exquisite Louis XIII 🇫🇷💎👑🥃",
]

# List of fun pizzas to give out
PIZZAS = [
    "a classic Margherita pizza 🍕",
    "a pepperoni pizza with extra cheese 🧀🍕",
    "a spicy Diavola pizza 🌶️🍕",
    "a veggie supreme pizza 🥦🍅🍕",
    "a Hawaiian pizza with pineapple 🍍🍕",
    "a four cheese Quattro Formaggi pizza 🧀🧀🧀🧀🍕",
    "a BBQ chicken pizza 🍗🍕",
    "a meat lover's pizza 🥩🍕",
    "a mushroom and truffle pizza 🍄🍕",
    "a white pizza with ricotta and spinach 🌱🍕",
    "a New York-style slice 🍕🗽",
    "a Chicago deep dish pizza 🧀🍅🍕",
    "a Mediterranean pizza with olives and feta 🫒🍕",
    "a buffalo chicken pizza 🐔🌶️🍕",
    "a vegan pizza with cashew cheese 🌱🧀🍕",
    "a calzone bursting with fillings 🥟🍕",
    "a prosciutto and arugula pizza 🥓🌿🍕",
    "a breakfast pizza with egg and bacon 🍳🥓🍕",
    "a seafood pizza with shrimp and calamari 🦐🦑🍕",
    "a dessert Nutella pizza 🍫🍕",
    "a Detroit-style square pizza 🟥🍕",
    "a Sicilian thick crust pizza 🍕🇮🇹",
    "a Neapolitan wood-fired pizza 🔥🍕",
    "a stuffed crust pizza overflowing with cheese 🧀🍕",
    "a Greek pizza with gyro meat and tzatziki 🥙🍕",
    "a taco pizza with salsa and sour cream 🌮🍕",
    "a pesto chicken pizza 🌿🍗🍕",
    "a Philly cheesesteak pizza 🥩🧀🍕",
    "a jalapeño popper pizza 🌶️🧀🍕",
    "a bacon cheeseburger pizza 🍔🥓🍕",
    "a French onion pizza with caramelized onions 🧅🍕",
    "a fig and prosciutto pizza 🍈🥓🍕",
    "a artichoke and sun-dried tomato pizza 🌿🍅🍕",
    "a pulled pork pizza with BBQ sauce 🐷🍕",
    "a kimchi and Korean BBQ pizza 🌶️🍕",
    "a tandoori chicken pizza 🍗🇮🇳🍕",
    "a carbonara pizza with pancetta 🥓🍕",
    "a BLT pizza with mayo drizzle 🥓🥬🍅🍕",
    "a mac and cheese pizza 🧀🍝🍕",
    "a garlic knots stuffed pizza 🧄🍕",
]

# List of popular mixed drinks to give out
MIXED_DRINKS = [
    "a classic Margarita with salt rim 🍹🧂",
    "a refreshing Mojito with fresh mint 🌿🍹",
    "an Old Fashioned with a twist 🍊🥃",
    "a sophisticated Manhattan 🍒🥃",
    "a dry Martini - shaken, not stirred 🍸",
    "a pink Cosmopolitan 🍸💕",
    "a tropical Mai Tai 🍹🌺",
    "a creamy Piña Colada 🍍🥥🍹",
    "a potent Long Island Iced Tea 🍹💪",
    "a Moscow Mule in a copper mug 🍹",
    "a spicy Bloody Mary with celery 🍅🌶️🍹",
    "a tangy Whiskey Sour 🍋🥃",
    "a fizzy Tom Collins 🍋🍹",
    "a bitter Negroni 🍊🍹",
    "a classic Daiquiri 🍹",
    "a minty Mint Julep 🌿🥃",
    "a simple Gin and Tonic 🍋🍹",
    "a Rum and Coke with lime 🥃🥤",
    "a fruity Sex on the Beach 🍑🍹",
    "a smooth White Russian ☕🥃",
    "a bold Espresso Martini ☕🍸",
    "an Aperol Spritz with prosecco 🍊🥂",
    "a warm Irish Coffee ☕🥃🇮🇪",
    "a tropical Blue Hawaiian 🍹💙",
    "a sweet Amaretto Sour 🍋🥃",
]

# List of wines to give out
WINES = [
    "a bold Cabernet Sauvignon 🍷",
    "a smooth Merlot 🍷",
    "a rich Pinot Noir 🍷❤️",
    "a full-bodied Malbec 🍷🇦🇷",
    "a elegant Syrah/Shiraz 🍷",
    "a crisp Sauvignon Blanc 🥂",
    "a buttery Chardonnay 🥂",
    "a refreshing Pinot Grigio 🥂",
    "a zesty Riesling 🥂🍋",
    "a aromatic Moscato 🥂✨",
    "a delicate Rosé 🌹🍷",
    "a sparkling Champagne 🍾✨",
    "a bubbly Prosecco 🍾🇮🇹",
    "a festive Cava 🍾🇪🇸",
    "a sweet Dessert Wine 🍷🍯",
    "a fortified Port 🍷🇵🇹",
    "a nutty Sherry 🍷🥜",
    "a complex Chianti 🍷🇮🇹",
    "a smooth Rioja 🍷🇪🇸",
    "a premium Barolo 🍷👑",
]

# List of mocktails (non-alcoholic)
MOCKTAILS = [
    "a virgin Piña Colada 🍍🥥",
    "a refreshing Virgin Mojito 🌿💚",
    "a fruity Shirley Temple 🍒✨",
    "a zesty Virgin Mary 🍅",
    "a tropical Roy Rogers 🥤🍒",
    "a sparkling Arnold Palmer 🍋⛳",
    "a minty Cucumber Cooler 🥒🌿",
    "a sweet Strawberry Lemonade 🍓🍋",
    "a fizzy Italian Soda 🍓🥤",
    "a creamy Virgin Mudslide 🍫☕",
    "a tangy Citrus Punch 🍊🍋",
    "a exotic Mango Lassi 🥭🥛",
    "a refreshing Watermelon Agua Fresca 🍉💧",
    "a spiced Ginger Beer Float 🥤✨",
    "a fruity Paradise Punch 🍹🌴",
    "a berry Blueberry Lemonade 🫐🍋",
    "a tropical Passion Fruit Spritzer 💛🥤",
    "a fancy Mock Champagne 🍾✨",
    "a cool Mint Lime Cooler 🌿🍋",
    "a sweet Peach Iced Tea 🍑🧊",
]

# List of coffee drinks to give out
COFFEES = [
    # Classic Espresso Drinks
    "a strong Espresso ☕💪",
    "a smooth Americano ☕",
    "a creamy Cappuccino ☕🥛",
    "a frothy Latte ☕✨",
    "a sweet Mocha ☕🍫",
    "a caramel Macchiato ☕🍯",
    "a bold Cortado ☕",
    "a Flat White ☕🇦🇺",
    "a fancy Affogato ☕🍨",
    "a classic Café au Lait ☕🥛",
    "a rich Ristretto ☕💎",
    "a smooth Lungo ☕",
    "a layered Latte Macchiato ☕🥛",
    "a traditional Espresso Con Panna ☕🍦",
    "a double-shot Doppio ☕☕",
    
    # Iced Coffee Varieties
    "an iced Cold Brew ☕🧊",
    "a frothy Nitro Cold Brew ☕💨",
    "a Vietnamese Iced Coffee ☕🥛🇻🇳",
    "an Iced Americano ☕🧊",
    "an Iced Latte ☕🧊🥛",
    "an Iced Mocha ☕🧊🍫",
    "an Iced Caramel Macchiato ☕🧊🍯",
    "a refreshing Iced Coffee ☕🧊",
    "a Japanese Iced Coffee ☕🇯🇵🧊",
    "a Freddo Espresso ☕🇬🇷🧊",
    "a Freddo Cappuccino ☕🇬🇷🧊🥛",
    "a smooth Cold Foam Cold Brew ☕🧊☁️",
    "a Sweet Cream Cold Brew ☕🧊🥛",
    
    # Flavored Lattes & Mochas
    "a sweet Vanilla Latte ☕🌼",
    "a nutty Hazelnut Latte ☕🌰",
    "a sweet Cinnamon Dolce Latte ☕✨",
    "a smooth White Chocolate Mocha ☕🤍🍫",
    "a minty Peppermint Mocha ☕🌿🍫",
    "a festive Pumpkin Spice Latte 🎃☕",
    "a Gingerbread Latte ☕🍪",
    "a Salted Caramel Mocha ☕🧂🍫",
    "a Toffee Nut Latte ☕🍬",
    "a Coconut Milk Latte ☕🥥",
    "a Lavender Latte ☕💜",
    "a Rose Latte ☕🌹",
    "a Honey Vanilla Latte ☕🍯",
    "a Brown Sugar Oat Milk Latte ☕🌾",
    "a Maple Cinnamon Latte ☕🍁",
    "a Pistachio Latte ☕💚",
    "a Toasted Marshmallow Latte ☕🍭",
    "a Cookie Butter Latte ☕🍪",
    "an Almond Joy Latte ☕🥥🍫",
    "a Snickerdoodle Latte ☕🍪",
    
    # International Coffee Styles
    "a rich Turkish Coffee ☕🇹🇷",
    "a strong Greek Coffee ☕🇬🇷",
    "a traditional Cuban Coffee ☕🇨🇺",
    "a creamy Italian Coffee ☕🇮🇹",
    "a spiced Arabic Coffee ☕🌶️",
    "a sweet Thai Iced Coffee ☕🇹🇭🧊",
    "a Spanish Café Bombón ☕🇪🇸",
    "a Brazilian Cafezinho ☕🇧🇷",
    "a Mexican Café de Olla ☕🇲🇽",
    "an Ethiopian Coffee ☕🇪🇹",
    "a Portuguese Galão ☕🇵🇹",
    "an Australian Magic ☕🇦🇺✨",
    "a New Zealand Long Black ☕🇳🇿",
    "a Hong Kong Yuanyang ☕🇭🇰",
    "a Malaysian Kopi ☕🇲🇾",
    "an Indian Filter Coffee ☕🇮🇳",
    
    # Specialty Teas & Tea Lattes
    "a spiced Chai Latte ☕🌶️",
    "a London Fog ☕🇬🇧☁️",
    "a Matcha Latte ☕🍵💚",
    "a Dirty Chai ☕🌶️💪",
    "a Turmeric Latte ☕💛",
    "a Beetroot Latte ☕💗",
    "a Blue Butterfly Pea Latte ☕💙",
    
    # Coffee with Alcohol
    "a warm Irish Coffee ☕🥃🇮🇪",
    "a Spanish Carajillo ☕🥃🇪🇸",
    "an Italian Caffè Corretto ☕🥃🇮🇹",
    "a French Café Royale ☕🥃🇫🇷",
    "a Baileys Coffee ☕🍫🥃",
    "a Rum Coffee ☕🥃",
    "an Amaretto Coffee ☕🥃🌰",
    
    # Specialty Brewing Methods
    "a Pour Over Coffee ☕💧",
    "a French Press Coffee ☕🇫🇷",
    "a Chemex Coffee ☕⚗️",
    "an AeroPress Coffee ☕✈️",
    "a Siphon Coffee ☕🔬",
    "a Moka Pot Coffee ☕🇮🇹",
    "a Percolated Coffee ☕",
    "a Cowboy Coffee ☕🤠",
    
    # Modern & Designer Coffees
    "an Espresso Martini ☕🍸",
    "a Dalgona Coffee ☕☁️",
    "a Whipped Coffee ☕☁️",
    "a Coffee Frappuccino ☕🧊🥤",
    "a Protein Coffee ☕💪",
    "a Bulletproof Coffee ☕🧈",
    "a Mushroom Coffee ☕🍄",
    "a CBD Coffee ☕🌿",
    "a Collagen Coffee ☕✨",
    "a Charcoal Latte ☕🖤",
    "a Unicorn Latte ☕🦄",
    "a Galaxy Latte ☕🌌",
    "a Cloud Macchiato ☕☁️",
    "a Cascara Latte ☕🍒",
    
    # Decaf & Alternative Options
    "a Decaf Latte ☕😴",
    "a Decaf Americano ☕💤",
    "a Half-Caf Coffee ☕½",
    "a Chicory Coffee ☕🌿",
    "a Barley Coffee ☕🌾",
    "a Dandelion Coffee ☕🌼",
]

# List of teas to give out
TEAS = [
    # Classic Black Teas
    "a proper English Breakfast tea 🫖🇬🇧",
    "a bold Assam tea 🫖🌿",
    "a fragrant Earl Grey 🫖💜",
    "a delicate Darjeeling 🫖🏔️",
    "a smoky Lapsang Souchong 🫖💨",
    "a rich Ceylon tea 🫖🇱🇰",
    "a classic Lady Grey 🫖✨",
    "a malty Irish Breakfast tea 🫖🇮🇪",

    # Green Teas
    "a serene Japanese Sencha 🍵🇯🇵",
    "a ceremonial Matcha 🍵💚",
    "a fresh Gyokuro 🍵✨",
    "a toasty Genmaicha 🍵🌾",
    "a floral Jasmine Green tea 🍵🌸",
    "a sweet Chinese Dragon Well 🍵🐉",
    "a grassy Biluochun 🍵🌿",
    "a smoky Gunpowder tea 🍵💣",

    # White & Oolong Teas
    "a delicate Silver Needle white tea 🍵🌙",
    "a light White Peony tea 🍵🌸",
    "a complex Oolong 🍵🔀",
    "a roasted Tieguanyin 🍵🏵️",
    "a floral Oriental Beauty Oolong 🍵🦋",

    # Herbal & Tisanes
    "a soothing Chamomile tea 🌼🫖",
    "a refreshing Peppermint tea 🌿🫖",
    "a calming Lavender tea 💜🫖",
    "a tart Hibiscus tea 🌺🫖",
    "a warming Ginger tea 🫚🫖",
    "a gentle Lemon Balm tea 🍋🫖",
    "a spiced Rooibos 🍂🫖🇿🇦",
    "a woody Yerba Maté 🧉🇦🇷",
    "a floral Rose hip tea 🌹🫖",
    "a earthy Nettle tea 🌿🫖",
    "a tropical Hibiscus Lemonade tea 🌺🍋",
    "a warming Turmeric Ginger tea 💛🫖",
    "a soothing Valerian Root tea 🌸😴",
    "a tangy Lemon Verbena tea 🍋🌿",

    # Chai & Spiced Teas
    "a spiced Masala Chai 🌶️🫖🇮🇳",
    "a creamy Chai Latte 🫖✨",
    "a warming Kashmiri Pink Chai 🌸🫖",
    "a bold Adrak Chai (Ginger Chai) 🫚🫖",
    "a festive Mulled Tea 🍊🌿🫖",

    # Iced & Cold Teas
    "a refreshing Iced Black Tea 🧊🫖",
    "a classic Sweet Tea 🍋🧊🫖",
    "a fruity Iced Peach Tea 🍑🧊",
    "a tropical Iced Mango Tea 🥭🧊",
    "a zesty Iced Lemon Tea 🍋🧊",
    "a sparkling Iced Green Tea 🍵🧊✨",
    "a refreshing Arnold Palmer 🍋⛳🧊",
    "a smooth Taiwanese Milk Tea 🥛🫖🇹🇼",
    "a classic Bubble Tea 🧋🟤",
    "a taro Bubble Tea 🟣🧋",
    "a strawberry Bubble Tea 🍓🧋",
    "a matcha Bubble Tea 💚🧋",

    # International & Specialty Teas
    "a traditional Moroccan Mint Tea 🌿🇲🇦",
    "a sweet Hong Kong Milk Tea 🥛☕🇭🇰",
    "a rich Teh Tarik 🇲🇾☕",
    "a ceremonial Japanese Hojicha 🍵🔥🇯🇵",
    "a tangy Kombucha 🍵🦠✨",
    "a light Korean Barley Tea 🌾🫖🇰🇷",
    "a refreshing Tibetan Butter Tea 🧈🫖",
    "a warming Russian Zavarka 🫖🇷🇺",
]

# List of hydration options (fun!)
WATERS = [
    "a crystal clear glass of water 💧",
    "a fancy sparkling water 💧✨",
    "a refreshing ice water 🧊💧",
    "a healthy coconut water 🥥💧",
    "a trendy alkaline water 💧⚗️",
    "a bougie Fiji water 💧🏝️",
    "a hydrating electrolyte water 💧⚡",
    "a cucumber infused water 🥒💧",
    "a lemon water 🍋💧",
    "a responsible glass of H2O 💧😇",
    "a bubbly Perrier 💧🇫🇷",
    "a classy San Pellegrino 💧🇮🇹",
    "a smart choice - water 💧🧠",
    "a mint infused water 🌿💧",
    "a strawberry water 🍓💧",
]

# List of appetizers/snacks
APPETIZERS = [
    "some crispy Buffalo Wings 🍗🔥",
    "a plate of loaded Nachos 🧀🌶️",
    "some golden Mozzarella Sticks 🧀✨",
    "a basket of seasoned Fries 🍟",
    "some crunchy Onion Rings 🧅⭕",
    "a platter of Chicken Tenders 🍗",
    "some spicy Jalapeño Poppers 🌶️🧀",
    "a bowl of Chips and Salsa 🌮🍅",
    "some cheesy Quesadillas 🧀🌮",
    "a plate of Sliders 🍔",
    "some crispy Calamari 🦑",
    "a serving of Spinach Artichoke Dip 🌿🧀",
    "some loaded Potato Skins 🥔🧀🥓",
    "a basket of Pretzel Bites 🥨",
    "some BBQ Ribs 🍖🔥",
    "a plate of Poutine 🍟🧀🇨🇦",
    "some Garlic Bread 🧄🍞",
    "a charcuterie board 🧀🥖🍇",
    "some Boneless Wings 🍗",
    "a bowl of Guacamole with chips 🥑🌮",
    "some Fried Pickles 🥒",
    "a plate of Bruschetta 🍅🍞🇮🇹",
    "some Tater Tots 🥔",
    "a serving of Hummus and Pita 🫓",
    "some Mac and Cheese Bites 🧀🍝",
]

# Beer/Cider giving messages (can crack open, chill, etc)
BEER_MESSAGES = [
    "slides {drink} across the bar to {user} ✨",
    "cracks open {drink} for {user} *pssshhht* 💨",
    "tosses {drink} to {user} *CATCH!* 🎯",
    "serves {user} {drink} - enjoy! 🍻",
    "conjures {drink} out of thin air for {user} ✨🎩",
    "pours {drink} into a frosty glass for {user} 🍺",
    "rolls {drink} down the bar to {user} 🎳",
    "ceremoniously presents {user} with {drink} 🎊",
    "teleports {drink} directly into {user}'s hand 🚀✨",
    "pulls {drink} from the cooler and hands it to {user} 🧊",
]

# Whiskey/Spirit giving messages (pour, serve neat or on rocks)
WHISKEY_MESSAGES = [
    "slides {drink} across the bar to {user} ✨",
    "pours {drink} and hands it to {user} with a smile 😊",
    "serves {user} {drink} - enjoy! 🥃",
    "conjures {drink} out of thin air for {user} ✨🎩",
    "pours {drink} neat for {user} 🥃",
    "pours {drink} on the rocks for {user} 🧊🥃",
    "ceremoniously presents {user} with {drink} 🎊",
    "teleports {drink} directly into {user}'s hand 🚀✨",
    "carefully measures out {drink} for {user} 🥃",
    "pours a generous serving of {drink} for {user} 🥃",
]

# Vodka giving messages
VODKA_MESSAGES = [
    "slides {drink} across the bar to {user} ✨",
    "pours {drink} ice-cold for {user} 🧊🥃",
    "serves {user} {drink} - na zdorovie! 🥃",
    "conjures {drink} out of thin air for {user} ✨🎩",
    "chills {drink} to perfection and hands it to {user} 🧊",
    "ceremoniously presents {user} with {drink} 🎊",
    "teleports {drink} directly into {user}'s hand 🚀✨",
    "pours a crisp {drink} for {user} 🥃",
    "pulls {drink} from the freezer for {user} 🧊🥃",
    "serves {user} {drink} chilled to perfection 🥶🥃",
]

# Rum giving messages
RUM_MESSAGES = [
    "slides {drink} across the bar to {user} ✨",
    "pours {drink} and hands it to {user} 🏴‍☠️🥃",
    "serves {user} {drink} - yo ho ho! 🏴‍☠️",
    "conjures {drink} out of thin air for {user} ✨🎩",
    "pours {drink} neat for {user} 🥃",
    "ceremoniously presents {user} with {drink} 🎊",
    "teleports {drink} directly into {user}'s hand 🚀✨",
    "pours a generous measure of {drink} for {user} 🥃",
    "serves {user} {drink} island style 🌴🥃",
    "sets sail with {drink} for {user} ⛵🥃",
]

# Tequila giving messages
TEQUILA_MESSAGES = [
    "slides {drink} across the bar to {user} ✨",
    "pours {drink} and hands it to {user} - ¡salud! 🇲🇽🥃",
    "serves {user} {drink} with salt & lime 🧂🍋🥃",
    "conjures {drink} out of thin air for {user} ✨🎩",
    "pours {drink} smooth for {user} 🥃",
    "ceremoniously presents {user} with {drink} 🎊",
    "teleports {drink} directly into {user}'s hand 🚀✨",
    "lines up {drink} for {user} - arriba! 🥃🎉",
    "carefully pours {drink} for {user} to sip 🥃",
    "delivers {drink} to {user} - one tequila, two tequila... 🥃🥃",
]

# Gin giving messages
GIN_MESSAGES = [
    "slides {drink} across the bar to {user} ✨",
    "pours {drink} and hands it to {user} 🌿🥃",
    "serves {user} {drink} - cheers! 🥃",
    "conjures {drink} out of thin air for {user} ✨🎩",
    "pours {drink} with a flourish for {user} 🥃",
    "ceremoniously presents {user} with {drink} 🎊",
    "teleports {drink} directly into {user}'s hand 🚀✨",
    "carefully measures {drink} for {user} 🥃",
    "serves {user} {drink} botanically blessed 🌿✨",
    "garnishes {drink} and passes it to {user} 🥒🥃",
]

# Brandy/Cognac giving messages
BRANDY_MESSAGES = [
    "slides {drink} across the bar to {user} ✨",
    "pours {drink} into a snifter for {user} 🥃",
    "serves {user} {drink} - santé! 🥃",
    "conjures {drink} out of thin air for {user} ✨🎩",
    "warms {drink} gently and hands it to {user} 🥃🔥",
    "ceremoniously presents {user} with {drink} 🎊",
    "teleports {drink} directly into {user}'s hand 🚀✨",
    "pours a generous snifter of {drink} for {user} 🥃",
    "serves {user} {drink} in fine style 🎩🥃",
    "presents {drink} to {user} with a knowing nod 🥃😌",
]

# Shot giving messages (quick, energetic)
SHOT_MESSAGES = [
    "slides {drink} across the bar to {user} ✨",
    "lines up {drink} for {user} 🥃",
    "serves {user} {drink} - bottoms up! 🥃",
    "conjures {drink} out of thin air for {user} ✨🎩",
    "pours {drink} and hands it to {user} 🥃",
    "ceremoniously presents {user} with {drink} 🎊",
    "teleports {drink} directly into {user}'s hand 🚀✨",
    "sets down {drink} in front of {user} 🥃",
    "prepares {drink} for {user} 🥃",
    "quickly pours {drink} for {user} - cheers! 🥃",
]

# Cocktail/Mixed drink giving messages (mix, shake, stir)
COCKTAIL_MESSAGES = [
    "slides {drink} across the bar to {user} ✨",
    "shakes up {drink} and serves it to {user} 🍸",
    "mixes {drink} and hands it to {user} with a smile 😊",
    "serves {user} {drink} - enjoy! 🍹",
    "conjures {drink} out of thin air for {user} ✨🎩",
    "carefully crafts {drink} for {user} 🍸",
    "stirs {drink} and passes it to {user} 🥄",
    "ceremoniously presents {user} with {drink} 🎊",
    "teleports {drink} directly into {user}'s hand 🚀✨",
    "muddles and mixes {drink} for {user} 🍹",
]

# Wine giving messages (pour, swirl, serve)
WINE_MESSAGES = [
    "slides {drink} across the bar to {user} ✨",
    "pours {drink} and hands it to {user} 🍷",
    "serves {user} {drink} - cheers! 🍷",
    "conjures {drink} out of thin air for {user} ✨🎩",
    "uncorks and pours {drink} for {user} 🍷",
    "ceremoniously presents {user} with {drink} 🎊",
    "teleports {drink} directly into {user}'s hand 🚀✨",
    "pours a glass of {drink} for {user} 🍷",
    "decants {drink} and serves it to {user} 🍷",
    "swirls and serves {drink} to {user} 🍷✨",
]

# Coffee giving messages
COFFEE_MESSAGES = [
    "slides {drink} across the counter to {user} ✨",
    "brews {drink} fresh for {user} ☕",
    "serves {user} {drink} - enjoy! ☕",
    "conjures {drink} out of thin air for {user} ✨🎩",
    "steams and pours {drink} for {user} ☕",
    "ceremoniously presents {user} with {drink} 🎊",
    "teleports {drink} directly into {user}'s hand 🚀✨",
    "carefully crafts {drink} for {user} ☕✨",
    "froths {drink} and hands it to {user} ☕🥛",
    "pulls a perfect shot for {drink} and gives it to {user} ☕",
]

# Tea giving messages
TEA_MESSAGES = [
    "slides {drink} across the counter to {user} ✨",
    "steeps {drink} to perfection for {user} 🫖",
    "serves {user} {drink} - enjoy! 🍵",
    "conjures {drink} out of thin air for {user} ✨🎩",
    "carefully pours {drink} for {user} 🫖",
    "ceremoniously presents {user} with {drink} 🎊",
    "teleports {drink} directly into {user}'s hand 🚀✨",
    "brews a perfect cup of {drink} for {user} 🫖✨",
    "hands {user} a warm cup of {drink} 🍵",
    "sets {drink} down in front of {user} with a smile 🫖😊",
]

# Water giving messages (responsible hydration!)
WATER_MESSAGES = [
    "slides {drink} across the bar to {user} ✨",
    "hands {drink} to {user} - stay hydrated! 💧",
    "serves {user} {drink} - good choice! 💧👍",
    "conjures {drink} out of thin air for {user} ✨🎩",
    "pours {drink} and passes it to {user} 💧",
    "teleports {drink} directly into {user}'s hand 🚀✨",
    "responsibly serves {user} {drink} 💧😇",
    "fills a glass with {drink} for {user} 💧",
    "cracks open {drink} for {user} 💧",
    "reminds {user} to hydrate and hands them {drink} 💧❤️",
]

# Food giving messages
FOOD_MESSAGES = [
    "slides {food} across the counter to {user} ✨",
    "serves {user} {food} - enjoy! 🍽️",
    "brings {food} fresh from the kitchen to {user} 🔥",
    "conjures {food} out of thin air for {user} ✨🎩",
    "plates up {food} and hands it to {user} 🍽️",
    "ceremoniously presents {user} with {food} 🎊",
    "teleports {food} directly to {user} 🚀✨",
    "tosses {food} to {user} *CATCH!* 🎯",
    "delivers {food} hot and ready to {user} 🔥",
    "sets down {food} in front of {user} 🍽️",
]

# Pizza-specific giving messages
PIZZA_MESSAGES = [
    "slides {food} across the counter to {user} ✨",
    "hands {food} to {user} with a smile 😊",
    "tosses {food} to {user} *CATCH!* 🎯",
    "serves {user} {food} - enjoy! 🍕",
    "conjures {food} out of thin air for {user} ✨🎩",
    "passes {food} to {user} 🍕",
    "delivers {food} hot and fresh to {user} 🔥",
    "rolls {food} down the counter to {user} 🎳",
    "ceremoniously presents {user} with {food} 🎊",
    "teleports {food} directly into {user}'s hand 🚀✨",
    "boxes up {food} and hands it to {user} 📦",
    "brings {user} a fresh {food} straight from the oven 🔥",
]


@module.commands('beer')
@module.example('$beer username', 'Give a user a random beer')
def beer(bot, trigger):
    """Give someone a refreshing beer! 🍺"""
    _serve_item(bot, trigger, 'beer', BEERS, BEER_MESSAGES)


@module.commands('shot')
@module.example('$shot username', 'Give a user a random shot')
def shot(bot, trigger):
    """Give someone a shot! 🥃"""
    _serve_item(bot, trigger, 'shot', SHOTS, SHOT_MESSAGES)


@module.commands('magners')
@module.example('$magners username', 'Give a user a random Magners cider')
def magners(bot, trigger):
    """Give someone a refreshing Magners! 🍎🍺"""
    _serve_item(bot, trigger, 'magners', MAGNERS, BEER_MESSAGES)


@module.commands('whiskey', 'whisky')
@module.example('$whiskey username', 'Give a user a random whiskey')
def whiskey(bot, trigger):
    """Give someone a fine whiskey! 🥃"""
    _serve_item(bot, trigger, 'whiskey', WHISKEYS, WHISKEY_MESSAGES)


@module.commands('vodka')
@module.example('$vodka username', 'Give a user a random vodka')
def vodka(bot, trigger):
    """Give someone a fine vodka! 🥃"""
    _serve_item(bot, trigger, 'vodka', VODKAS, VODKA_MESSAGES)


@module.commands('rum')
@module.example('$rum username', 'Give a user a random rum')
def rum(bot, trigger):
    """Give someone a fine rum! 🏴‍☠️🥃"""
    _serve_item(bot, trigger, 'rum', RUMS, RUM_MESSAGES)


@module.commands('tequila')
@module.example('$tequila username', 'Give a user a random tequila')
def tequila(bot, trigger):
    """Give someone a fine tequila! 🇲🇽🥃"""
    _serve_item(bot, trigger, 'tequila', TEQUILAS, TEQUILA_MESSAGES)


@module.commands('gin')
@module.example('$gin username', 'Give a user a random gin')
def gin(bot, trigger):
    """Give someone a fine gin! 🌿🥃"""
    _serve_item(bot, trigger, 'gin', GINS, GIN_MESSAGES)


@module.commands('brandy', 'cognac')
@module.example('$brandy username', 'Give a user a random brandy/cognac')
def brandy(bot, trigger):
    """Give someone a fine brandy or cognac! 🥃"""
    _serve_item(bot, trigger, 'brandy', BRANDIES, BRANDY_MESSAGES)


@module.commands('pizza')
@module.example('$pizza', 'Give yourself a random pizza')
@module.example('$pizza username', 'Give a user a random pizza')
def pizza(bot, trigger):
    """Give someone a delicious pizza! 🍕"""
    _serve_item(bot, trigger, 'pizza', PIZZAS, PIZZA_MESSAGES, placeholder_key='food')


@module.commands('drink')
@module.example('$drink', 'Give yourself a random mixed drink')
@module.example('$drink username', 'Give a user a random mixed drink')
def drink(bot, trigger):
    """Give someone a delicious mixed drink! 🍹"""
    _serve_item(bot, trigger, 'mixed_drink', MIXED_DRINKS, COCKTAIL_MESSAGES)


@module.commands('wine')
@module.example('$wine', 'Give yourself a random wine')
@module.example('$wine username', 'Give a user a random wine')
def wine(bot, trigger):
    """Give someone a fine wine! 🍷"""
    _serve_item(bot, trigger, 'wine', WINES, WINE_MESSAGES)


@module.commands('mocktail', 'virgin')
@module.example('$mocktail', 'Give yourself a random non-alcoholic drink')
@module.example('$mocktail username', 'Give a user a random non-alcoholic drink')
def mocktail(bot, trigger):
    """Give someone a refreshing mocktail! 🍹"""
    _serve_item(bot, trigger, 'mocktail', MOCKTAILS, COCKTAIL_MESSAGES)


@module.commands('coffee', 'caffeine')
@module.example('$coffee', 'Give yourself a random coffee')
@module.example('$coffee username', 'Give a user a random coffee')
def coffee(bot, trigger):
    """Give someone a energizing coffee! ☕"""
    _serve_item(bot, trigger, 'coffee', COFFEES, COFFEE_MESSAGES)


@module.commands('tea', 'cuppa')
@module.example('$tea', 'Give yourself a random tea')
@module.example('$tea username', 'Give a user a random tea')
def tea(bot, trigger):
    """Give someone a soothing tea! 🍵"""
    _serve_item(bot, trigger, 'tea', TEAS, TEA_MESSAGES)


@module.commands('water', 'hydrate')
@module.example('$water', 'Give yourself water')
@module.example('$water username', 'Give a user water - stay hydrated!')
def water(bot, trigger):
    """Give someone water! Stay hydrated! 💧"""
    _serve_item(bot, trigger, 'water', WATERS, WATER_MESSAGES)


@module.commands('appetizer', 'snack', 'food')
@module.example('$appetizer', 'Give yourself a random appetizer')
@module.example('$appetizer username', 'Give a user a random appetizer')
def appetizer(bot, trigger):
    """Give someone a tasty appetizer! 🍽️"""
    _serve_item(bot, trigger, 'appetizer', APPETIZERS, FOOD_MESSAGES, placeholder_key='food')


@module.commands('surprise', 'random')
@module.example('$surprise', 'Give yourself something random from the entire menu!')
@module.example('$surprise username', 'Give a user something random')
def surprise(bot, trigger):
    """Give someone a random surprise from everything available! 🎉"""
    
    # Use sender's nick if no user specified
    if not trigger.group(2):
        target_user = trigger.nick
    else:
        target_user = trigger.group(2).strip()
    
    # Combine all drink lists
    all_drinks = BEERS + SHOTS + MAGNERS + WHISKEYS + VODKAS + RUMS + TEQUILAS + GINS + BRANDIES + MIXED_DRINKS + WINES + MOCKTAILS + COFFEES + TEAS + WATERS
    all_foods = PIZZAS + APPETIZERS
    
    # Randomly decide if it's a drink or food
    if random.choice([True, False]):
        # It's a drink
        chosen_item = random.choice(all_drinks)
        # Pick appropriate message based on item characteristics
        if any(word in chosen_item.lower() for word in ['wine', 'champagne', 'prosecco', 'cava']):
            giving_message = random.choice(WINE_MESSAGES)
        elif any(word in chosen_item.lower() for word in ['coffee', 'espresso', 'latte', 'cappuccino']):
            giving_message = random.choice(COFFEE_MESSAGES)
        elif any(word in chosen_item.lower() for word in ['tea', 'chai', 'matcha', 'herbal', 'tisane', 'rooibos', 'chamomile', 'bubble']):
            giving_message = random.choice(TEA_MESSAGES)
        elif any(word in chosen_item.lower() for word in ['water', 'h2o']):
            giving_message = random.choice(WATER_MESSAGES)
        elif any(word in chosen_item.lower() for word in ['shot', 'bomber']):
            giving_message = random.choice(SHOT_MESSAGES)
        elif any(word in chosen_item.lower() for word in ['beer', 'lager', 'ale', 'stout', 'ipa', 'magners', 'cider']):
            giving_message = random.choice(BEER_MESSAGES)
        elif any(word in chosen_item.lower() for word in ['whiskey', 'whisky', 'bourbon']):
            giving_message = random.choice(WHISKEY_MESSAGES)
        elif any(word in chosen_item.lower() for word in ['vodka', 'belvedere', 'grey goose', 'ketel', 'absolut', 'smirnoff', 'stolichnaya']):
            giving_message = random.choice(VODKA_MESSAGES)
        elif any(word in chosen_item.lower() for word in ['rum', 'bacardi', 'captain morgan', 'malibu', 'kraken']):
            giving_message = random.choice(RUM_MESSAGES)
        elif any(word in chosen_item.lower() for word in ['tequila', 'mezcal', 'patrón', 'don julio']):
            giving_message = random.choice(TEQUILA_MESSAGES)
        elif any(word in chosen_item.lower() for word in ['gin', 'tanqueray', 'hendrick', 'bombay', 'beefeater']):
            giving_message = random.choice(GIN_MESSAGES)
        elif any(word in chosen_item.lower() for word in ['brandy', 'cognac', 'hennessy', 'rémy', 'courvoisier', 'calvados', 'pisco']):
            giving_message = random.choice(BRANDY_MESSAGES)
        else:
            giving_message = random.choice(COCKTAIL_MESSAGES)
        
        message = giving_message.format(drink=chosen_item, user=target_user)
    else:
        # It's food
        chosen_item = random.choice(all_foods)
        if 'pizza' in chosen_item.lower():
            giving_message = random.choice(PIZZA_MESSAGES)
        else:
            giving_message = random.choice(FOOD_MESSAGES)
        
        message = giving_message.format(food=chosen_item, user=target_user)
    
    # Send it!
    bot.action(message)


@module.commands('barhelp')
@module.example('$barhelp', 'Get a list of all bartender commands')
def barhelp(bot, trigger):
    """Get help for all bartender commands! 📋"""
    
    user = trigger.nick
    
    # Notify in channel
    bot.say(f"{user}: Check your PM for the bartender menu! 📬")
    
    # Send detailed help via PM
    help_messages = [
        "🍺 BARTENDER MENU 🍺",
        "=" * 40,
        "ECONOMY:",
        "  • You receive a $100 credit every 24 hours (starts on first order)",
        "  • Credits stack with your current balance",
        "  • Credits are applied when you run a bar command or $barcash; $tip does not trigger credits",
        "  • All items cost money (deducted from your balance)",
        "  • Water is always FREE!",
        "",
        "DRINKS:",

        "  $beer [user] ............ $5",
        "  $shot [user] ............ $7",
        "  $whiskey [user] ......... $12",
        "  $vodka [user] ........... $10",
        "  $rum [user] ............. $10",
        "  $tequila [user] ......... $10",
        "  $gin [user] ............. $10",
        "  $brandy [user] .......... $12",
        "  $drink [user] ........... $10",
        "  $wine [user] ............ $8",
        "  $magners [user] ......... $6",
        "",
        "NON-ALCOHOLIC:",
        "  $mocktail [user] ........ $4",
        "  $coffee [user] .......... $3",
        "  $tea [user] ............. $3",
        "  $water [user] ........... FREE",
        "",
        "FOOD:",
        "  $pizza [user] ........... $15",
        "  $appetizer [user] ....... $8",
        "",
        "SPECIAL:",
        "  $surprise [user] ........ (Random Price)",
        "",
        "COMMANDS:",
        "  $tip <user> <amount> - Tip another user",
        "  $barcash - Check your current balance (alias: $balance)",
        "  $toptip - See the top 5 most tipped users",
        "  $barhelp - Show this menu",
        "  $adjbal <nick> <+amount|-amount|amount> - Admin PM only: adjust a user's balance",
        "  $barreset <nick> | all confirm - Admin PM only: reset a user's balance or all balances (requires confirm)",
        "",
        "🍻 Enjoy responsibly! 🍻"
    ]
    
    # Send each line as a separate PM
    for line in help_messages:
        bot.say(line, user)


@module.commands('tip')
@module.example('$tip username 50', 'Tip a user $50')
def tip_user(bot, trigger):
    """Tip another user for great service! 💰"""
    
    tipper = str(trigger.account or trigger.nick)
    tipper_display = trigger.nick
    
    # Check if user specified who to tip and amount
    if not trigger.group(2):
        bot.say(f"{tipper_display}: Usage: $tip <user> <amount>")
        return
    
    args = trigger.group(2).strip().split()
    if len(args) < 2:
        bot.say(f"{tipper_display}: Usage: $tip <user> <amount>")
        return
    
    recipient = args[0]
    try:
        amount = int(args[1])
    except ValueError:
        bot.say(f"{tipper_display}: Amount must be a number!")
        return
    
    # Can't tip yourself
    if tipper.lower() == recipient.lower() or tipper_display.lower() == recipient.lower():
        bot.say(f"{tipper_display}: You can't tip yourself! 🙄")
        return
    
    # Amount must be positive
    if amount <= 0:
        bot.say(f"{tipper_display}: Tip amount must be positive!")
        return
    
    # Load data and check balance
    data = _load_tip_data(bot)

    tipper_key = _user_key(tipper)
    recipient_key = _user_key(recipient)

    # Check if tipper exists and has balance
    if tipper_key not in data['balances']:
        bot.say(f"{tipper_display}: You need to buy something from the bar first to get your $100 starting balance!")
        return

    balance = data['balances'][tipper_key]

    # Check if tipper has enough balance
    if balance < amount:
        bot.notice(f"You don't have enough! Balance: ${balance}", tipper_display)
        return

    # Initialize recipient if needed
    if recipient_key not in data['tips_received']:
        data['tips_received'][recipient_key] = 0
    if recipient_key not in data['balances']:
        data['balances'][recipient_key] = 100
        data['last_credit'][recipient_key] = time.time()

    # Transfer the money
    data['balances'][tipper_key] -= amount
    data['balances'][recipient_key] += amount
    data['tips_received'][recipient_key] += amount

    _save_tip_data(bot, data)

    bot.say(f"{tipper_display} tips {recipient} ${amount}! 💰✨")
    bot.notice(f"New balance: ${data['balances'][tipper_key]}", tipper_display)


@module.commands('barcash', 'balance')
@module.example('$barcash', 'Check your current balance')
def barcash(bot, trigger):
    """Check your current tip balance! 💵"""
    
    user = str(trigger.account or trigger.nick)
    user_display = trigger.nick
    
    data = _load_tip_data(bot)
    current_time = time.time()
    user_key = _user_key(user)

    if user_key not in data['balances']:
        data['balances'][user_key] = 100
        data['last_credit'][user_key] = current_time
        data['tips_received'][user_key] = 0
        _save_tip_data(bot, data)
        bot.notice(f"You received your daily $100! Current balance: $100 💵", user_display)
        return

    last_credit = data['last_credit'].get(user_key, 0)
    if current_time - last_credit >= 86400:
        data['balances'][user_key] += 100
        data['last_credit'][user_key] = current_time
        _save_tip_data(bot, data)
        bot.notice(f"You received your daily $100! Current balance: ${data['balances'][user_key]} 💵", user_display)
    else:
        bot.notice(f"Your balance is ${data['balances'][user_key]} 💵", user_display)


@module.commands('toptip')
@module.example('$toptip', 'See the top 5 most tipped users')
def toptip(bot, trigger):
    """See the top 5 most tipped bartenders! 🏆"""
    
    data = _load_tip_data(bot)
    tips = data.get('tips_received', {})
    
    if not tips:
        bot.say("No tips have been given yet! Be the first to tip someone! 💰")
        return
    
    # Sort by tips received
    sorted_tips = sorted(tips.items(), key=lambda x: x[1], reverse=True)[:5]
    
    bot.say("🏆 TOP 5 BARTENDERS 🏆")
    for i, (user, amount) in enumerate(sorted_tips, 1):
        medal = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"][i-1]
        bot.say(f"{medal} {user}: ${amount} in tips")


@module.commands('adjbal')
@module.example('$adjbal username +100', 'Adjust a user\'s balance by +100 (admin PM only)')
def adjbal(bot, trigger):
    """Admin-only PM command to adjust a user's balance.

    Usage (PM to bot): $adjbal <nick> <+amount| -amount | amount>
    Example: $adjbal m0n +100  (adds $100)
             $adjbal m0n -50   (subtracts $50)
    """
    # Require PM
    try:
        is_pm = getattr(trigger, 'is_privmsg', False) or (not trigger.sender.startswith('#'))
    except Exception:
        is_pm = getattr(trigger, 'is_privmsg', False)

    if not is_pm:
        try:
            bot.reply('Please PM me this admin command.')
        except Exception:
            pass
        return

    # Authorization: Sopel may set trigger.admin/owner for privileged users
    if not (getattr(trigger, 'admin', False) or getattr(trigger, 'owner', False)):
        # Also allow configured core admins if present
        try:
            cfg_admins = getattr(bot.config.core, 'admins', None)
            allowed = False
            if isinstance(cfg_admins, (list, tuple, set)):
                allowed = trigger.nick.lower() in {a.lower() for a in cfg_admins}
            elif isinstance(cfg_admins, str) and cfg_admins.strip():
                allowed = trigger.nick.lower() in {a.strip().lower() for a in re.split(r'[,\s]+', cfg_admins) if a.strip()}
            if not allowed:
                bot.reply('You are not authorized to use this command.')
                return
        except Exception:
            bot.reply('You are not authorized to use this command.')
            return

    if not trigger.group(2):
        bot.reply('Usage: $adjbal <nick> <+amount|-amount|amount>')
        return

    parts = trigger.group(2).strip().split()
    if len(parts) < 2:
        bot.reply('Usage: $adjbal <nick> <+amount|-amount|amount>')
        return

    nick = parts[0]
    amt_s = parts[1]
    # Allow +100, -50, or plain number
    try:
        if amt_s.startswith('+') or amt_s.startswith('-'):
            amt = int(amt_s)
        else:
            amt = int(amt_s)
    except ValueError:
        bot.reply('Amount must be an integer like +100 or -50.')
        return

    data = _load_tip_data(bot)
    # Normalize target nick/account
    nick_key = _user_key(nick)
    # Initialize user if missing
    if nick_key not in data['balances']:
        data['balances'][nick_key] = 100
        data['last_credit'][nick_key] = time.time()
        data['tips_received'][nick_key] = 0

    old = data['balances'].get(nick_key, 0)
    new = old + amt
    if new < 0:
        bot.reply(f'Operation would make {nick}\'s balance negative ({new}). Operation cancelled.')
        return

    data['balances'][nick_key] = new
    _save_tip_data(bot, data)

    bot.reply(f"Adjusted {nick}'s balance: ${old} -> ${new}")



@module.commands('barreset')
@module.example('$barreset username', "Reset a user's balance to $100 (admin PM only)")
@module.example('$barreset all confirm', 'Reset all balances to $100 and clear tips (admin PM only, requires confirm)')
def barreset(bot, trigger):
    """Admin-only PM command to reset balances.

    Usage (PM to bot):
      $barreset <nick>            # reset a single user's balance to $100 and clear tips
      $barreset all confirm      # reset ALL balances to $100 and clear all tips (requires confirm)
    """
    # Require PM
    try:
        is_pm = getattr(trigger, 'is_privmsg', False) or (not trigger.sender.startswith('#'))
    except Exception:
        is_pm = getattr(trigger, 'is_privmsg', False)

    if not is_pm:
        try:
            bot.reply('Please PM me this admin command.')
        except Exception:
            pass
        return

    # Authorization: same checks as adjbal
    if not (getattr(trigger, 'admin', False) or getattr(trigger, 'owner', False)):
        try:
            cfg_admins = getattr(bot.config.core, 'admins', None)
            allowed = False
            if isinstance(cfg_admins, (list, tuple, set)):
                allowed = trigger.nick.lower() in {a.lower() for a in cfg_admins}
            elif isinstance(cfg_admins, str) and cfg_admins.strip():
                allowed = trigger.nick.lower() in {a.strip().lower() for a in re.split(r'[,\s]+', cfg_admins) if a.strip()}
            if not allowed:
                bot.reply('You are not authorized to use this command.')
                return
        except Exception:
            bot.reply('You are not authorized to use this command.')
            return

    if not trigger.group(2):
        bot.reply('Usage: $barreset <nick> OR $barreset all confirm')
        return

    parts = trigger.group(2).strip().split()
    target = parts[0]

    data = _load_tip_data(bot)

    if target.lower() == 'all':
        # require explicit confirmation to prevent accidents
        if len(parts) < 2 or parts[1].lower() != 'confirm':
            bot.reply('To reset ALL balances, PM me: $barreset all confirm')
            return

        # Reset everything
        now = time.time()
        for k in list(data.get('balances', {}).keys()):
            data['balances'][k] = 100
        for k in list(data.get('last_credit', {}).keys()):
            data['last_credit'][k] = now
        for k in list(data.get('tips_received', {}).keys()):
            data['tips_received'][k] = 0

        _save_tip_data(bot, data)
        bot.reply('All balances reset to $100 and all tips cleared.')
        return

    # Single user reset
    nick = target
    nick_key = _user_key(nick)
    if nick_key not in data.get('balances', {}):
        data['balances'][nick_key] = 100
        data['last_credit'][nick_key] = time.time()
        data['tips_received'][nick_key] = 0
        _save_tip_data(bot, data)
        bot.reply(f"{nick} did not have an account; initialized to $100.")
        return

    data['balances'][nick_key] = 100
    data['last_credit'][nick_key] = time.time()
    data['tips_received'][nick_key] = 0
    _save_tip_data(bot, data)
    bot.reply(f"Reset {nick}'s balance to $100 and cleared tips.")


def _cleanup():
    """Cleanup on shutdown (empty for bot.db approach)."""
    pass


atexit.register(_cleanup)
