"""
Sopel Bartender Module - Your friendly virtual bartender!
Serves up random beers, shots, whiskeys, cocktails, and pizza.
"""
import random
import json
import os
import time
import fcntl
from datetime import datetime, timedelta
from sopel import module
import re


# Tip system data file
TIP_DATA_FILE = os.path.expanduser('~/.sopel/bartender_tips.json')


def load_tip_data():
    """Load tip data from file with file locking"""
    if os.path.exists(TIP_DATA_FILE):
        with open(TIP_DATA_FILE, 'r') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)  # Shared lock for reading
            try:
                return json.load(f)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    return {'balances': {}, 'last_credit': {}, 'tips_received': {}}


def _user_key(user):
    """Normalize user identifier for storage (use lowercase strings)."""
    return str(user).lower()


def save_tip_data(data):
    """Save tip data to file with file locking"""
    try:
        os.makedirs(os.path.dirname(TIP_DATA_FILE), exist_ok=True)
        with open(TIP_DATA_FILE, 'w') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)  # Exclusive lock for writing
            try:
                json.dump(data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())  # Force write to disk
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except Exception as e:
        print(f"ERROR saving tip data: {e}")
        raise


def check_and_credit_user(user):
    """Check if user needs daily credit and give it if needed"""
    data = load_tip_data()
    current_time = time.time()
    key = _user_key(user)

    # Initialize user if they don't exist
    if key not in data['balances']:
        data['balances'][key] = 100
        data['last_credit'][key] = current_time
        data['tips_received'][key] = 0
        save_tip_data(data)
        return data['balances'][key], True

    # Check if 24 hours have passed
    last_credit = data['last_credit'].get(key, 0)
    if current_time - last_credit >= 86400:  # 24 hours in seconds
        data['balances'][key] += 100
        data['last_credit'][key] = current_time
        save_tip_data(data)
        return data['balances'][key], True

    return data['balances'][key], False


# Prices for items
PRICES = {
    'beer': 5,
    'shot': 7,
    'whiskey': 12,
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


def deduct_price(user, item_type):
    """Deduct price from user's balance and return new balance, or None if insufficient funds"""
    user = _user_key(user)
    price = PRICES.get(item_type, 0)
    
    # Load data once and do all operations
    data = load_tip_data()
    current_time = time.time()
    
    credited = False
    
    # Initialize user if they don't exist
    if user not in data['balances']:
        data['balances'][user] = 100
        data['last_credit'][user] = current_time
        data['tips_received'][user] = 0
        save_tip_data(data)
        # Don't set credited=True for initialization, it's not a daily credit
    else:
        # Check if 24 hours have passed for credit
        last_credit = data['last_credit'].get(user, 0)
        if current_time - last_credit >= 86400:  # 24 hours in seconds
            data['balances'][user] += 100
            data['last_credit'][user] = current_time
            credited = True
    
    balance = data['balances'][user]
    
    # If it's free, just return
    if price == 0:
        save_tip_data(data)
        return balance, credited, price
    
    # Check if user has enough
    if balance < price:
        return None, credited, price
    
    # Deduct the price
    data['balances'][user] -= price
    save_tip_data(data)
    
    return data['balances'][user], credited, price




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
    
    # Use sender's nick if no user specified
    if not trigger.group(2):
        target_user = trigger.nick
    else:
        target_user = trigger.group(2).strip()
    
    # Deduct price from sender's balance (use account or nick as stable ID)
    sender = trigger.account or trigger.nick
    new_balance, credited, price = deduct_price(sender, 'beer')
    
    if new_balance is None:
        bot.say(f"{trigger.nick}: You don't have enough money! A beer costs ${price}. Use $barcash to check your funds.")
        return
    
    # Select random beer and message
    chosen_drink = random.choice(BEERS)
    giving_message = random.choice(BEER_MESSAGES)
    
    # Format the message
    message = giving_message.format(drink=chosen_drink, user=target_user)
    
    # Send it!
    bot.action(message)
    if credited:
        bot.notice(f"Daily $100 credited! Paid ${price} - Balance: ${new_balance}", trigger.nick)
    else:
        bot.notice(f"Paid ${price} - Balance: ${new_balance}", trigger.nick)

@module.commands('shot')
@module.example('$shot username', 'Give a user a random shot')
def shot(bot, trigger):
    """Give someone a shot! 🥃"""
    
    # Use sender's nick if no user specified
    if not trigger.group(2):
        target_user = trigger.nick
    else:
        target_user = trigger.group(2).strip()
    
    # Deduct price from sender's balance
    sender = trigger.account or trigger.nick
    new_balance, credited, price = deduct_price(sender, 'shot')
    
    if new_balance is None:
        bot.say(f"{trigger.nick}: You don't have enough money! A shot costs ${price}. Use $barcash to check your funds.")
        return
    
    # Select random shot and message
    chosen_drink = random.choice(SHOTS)
    giving_message = random.choice(SHOT_MESSAGES)
    
    # Format the message
    message = giving_message.format(drink=chosen_drink, user=target_user)
    
    # Send it!
    bot.action(message)
    if credited:
        bot.notice(f"Daily $100 credited! Paid ${price} - Balance: ${new_balance}", trigger.nick)
    else:
        bot.notice(f"Paid ${price} - Balance: ${new_balance}", trigger.nick)


@module.commands('magners')
@module.example('$magners username', 'Give a user a random Magners cider')
def magners(bot, trigger):
    """Give someone a refreshing Magners! 🍎🍺"""
    
    # Use sender's nick if no user specified
    if not trigger.group(2):
        target_user = trigger.nick
    else:
        target_user = trigger.group(2).strip()
    
    # Deduct price from sender's balance
    sender = trigger.account or trigger.nick
    new_balance, credited, price = deduct_price(sender, 'magners')
    
    if new_balance is None:
        bot.say(f"{trigger.nick}: You don't have enough money! Magners costs ${price}. Use $barcash to check your funds.")
        return
    
    # Select random Magners and message
    chosen_drink = random.choice(MAGNERS)
    giving_message = random.choice(BEER_MESSAGES)
    
    # Format the message
    message = giving_message.format(drink=chosen_drink, user=target_user)
    
    # Send it!
    bot.action(message)
    if credited:
        bot.notice(f"Daily $100 credited! Paid ${price} - Balance: ${new_balance}", trigger.nick)
    else:
        bot.notice(f"Paid ${price} - Balance: ${new_balance}", trigger.nick)


@module.commands('whiskey', 'whisky')
@module.example('$whiskey username', 'Give a user a random whiskey')
def whiskey(bot, trigger):
    """Give someone a fine whiskey! 🥃"""
    
    # Use sender's nick if no user specified
    if not trigger.group(2):
        target_user = trigger.nick
    else:
        target_user = trigger.group(2).strip()
    
    # Deduct price from sender's balance
    sender = trigger.account or trigger.nick
    new_balance, credited, price = deduct_price(sender, 'whiskey')
    
    if new_balance is None:
        bot.say(f"{trigger.nick}: You don't have enough money! Whiskey costs ${price}. Use $barcash to check your funds.")
        return
    
    # Select random whiskey and message
    chosen_drink = random.choice(WHISKEYS)
    giving_message = random.choice(WHISKEY_MESSAGES)
    
    # Format the message
    message = giving_message.format(drink=chosen_drink, user=target_user)
    
    # Send it!
    bot.action(message)
    if credited:
        bot.notice(f"Daily $100 credited! Paid ${price} - Balance: ${new_balance}", trigger.nick)
    else:
        bot.notice(f"Paid ${price} - Balance: ${new_balance}", trigger.nick)


@module.commands('pizza')
@module.example('$pizza', 'Give yourself a random pizza')
@module.example('$pizza username', 'Give a user a random pizza')
def pizza(bot, trigger):
    """Give someone a delicious pizza! 🍕"""
    
    # Use sender's nick if no user specified
    if not trigger.group(2):
        target_user = trigger.nick
    else:
        target_user = trigger.group(2).strip()
    
    # Deduct price from sender's balance
    sender = trigger.account or trigger.nick
    new_balance, credited, price = deduct_price(sender, 'pizza')
    
    if new_balance is None:
        bot.say(f"{trigger.nick}: You don't have enough money! Pizza costs ${price}. Use $barcash to check your funds.")
        return
    
    # Select random pizza and message
    chosen_pizza = random.choice(PIZZAS)
    giving_message = random.choice(PIZZA_MESSAGES)
    
    # Format the message
    message = giving_message.format(food=chosen_pizza, user=target_user)
    
    # Send it!
    bot.action(message)
    if credited:
        bot.notice(f"Daily $100 credited! Paid ${price} - Balance: ${new_balance}", trigger.nick)
    else:
        bot.notice(f"Paid ${price} - Balance: ${new_balance}", trigger.nick)


@module.commands('drink')
@module.example('$drink', 'Give yourself a random mixed drink')
@module.example('$drink username', 'Give a user a random mixed drink')
def drink(bot, trigger):
    """Give someone a delicious mixed drink! 🍹"""
    
    # Use sender's nick if no user specified
    if not trigger.group(2):
        target_user = trigger.nick
    else:
        target_user = trigger.group(2).strip()
    
    # Deduct price from sender's balance
    sender = trigger.account or trigger.nick
    new_balance, credited, price = deduct_price(sender, 'mixed_drink')
    
    if new_balance is None:
        bot.say(f"{trigger.nick}: You don't have enough money! A mixed drink costs ${price}. Use $barcash to check your funds.")
        return
    
    # Select random cocktail and message
    chosen_drink = random.choice(MIXED_DRINKS)
    giving_message = random.choice(COCKTAIL_MESSAGES)
    
    # Format the message
    message = giving_message.format(drink=chosen_drink, user=target_user)
    
    # Send it!
    bot.action(message)
    if credited:
        bot.notice(f"Daily $100 credited! Paid ${price} - Balance: ${new_balance}", trigger.nick)
    else:
        bot.notice(f"Paid ${price} - Balance: ${new_balance}", trigger.nick)


@module.commands('wine')
@module.example('$wine', 'Give yourself a random wine')
@module.example('$wine username', 'Give a user a random wine')
def wine(bot, trigger):
    """Give someone a fine wine! 🍷"""
    
    # Use sender's nick if no user specified
    if not trigger.group(2):
        target_user = trigger.nick
    else:
        target_user = trigger.group(2).strip()
    
    # Deduct price from sender's balance
    sender = trigger.account or trigger.nick
    new_balance, credited, price = deduct_price(sender, 'wine')
    
    if new_balance is None:
        bot.say(f"{trigger.nick}: You don't have enough money! Wine costs ${price}. Use $barcash to check your funds.")
        return
    
    # Select random wine and message
    chosen_drink = random.choice(WINES)
    giving_message = random.choice(WINE_MESSAGES)
    
    # Format the message
    message = giving_message.format(drink=chosen_drink, user=target_user)
    
    # Send it!
    bot.action(message)
    if credited:
        bot.notice(f"Daily $100 credited! Paid ${price} - Balance: ${new_balance}", trigger.nick)
    else:
        bot.notice(f"Paid ${price} - Balance: ${new_balance}", trigger.nick)


@module.commands('mocktail', 'virgin')
@module.example('$mocktail', 'Give yourself a random non-alcoholic drink')
@module.example('$mocktail username', 'Give a user a random non-alcoholic drink')
def mocktail(bot, trigger):
    """Give someone a refreshing mocktail! 🍹"""
    
    # Use sender's nick if no user specified
    if not trigger.group(2):
        target_user = trigger.nick
    else:
        target_user = trigger.group(2).strip()
    
    # Deduct price from sender's balance
    sender = trigger.account or trigger.nick
    new_balance, credited, price = deduct_price(sender, 'mocktail')
    
    if new_balance is None:
        bot.say(f"{trigger.nick}: You don't have enough money! A mocktail costs ${price}. Use $barcash to check your funds.")
        return
    
    # Select random mocktail and message
    chosen_drink = random.choice(MOCKTAILS)
    giving_message = random.choice(COCKTAIL_MESSAGES)
    
    # Format the message
    message = giving_message.format(drink=chosen_drink, user=target_user)
    
    # Send it!
    bot.action(message)
    if credited:
        bot.notice(f"Daily $100 credited! Paid ${price} - Balance: ${new_balance}", trigger.nick)
    else:
        bot.notice(f"Paid ${price} - Balance: ${new_balance}", trigger.nick)


@module.commands('coffee', 'caffeine')
@module.example('$coffee', 'Give yourself a random coffee')
@module.example('$coffee username', 'Give a user a random coffee')
def coffee(bot, trigger):
    """Give someone a energizing coffee! ☕"""
    
    # Use sender's nick if no user specified
    if not trigger.group(2):
        target_user = trigger.nick
    else:
        target_user = trigger.group(2).strip()
    
    # Deduct price from sender's balance
    sender = trigger.account or trigger.nick
    new_balance, credited, price = deduct_price(sender, 'coffee')
    
    if new_balance is None:
        bot.say(f"{trigger.nick}: You don't have enough money! Coffee costs ${price}. Use $barcash to check your funds.")
        return
    
    # Select random coffee and message
    chosen_drink = random.choice(COFFEES)
    giving_message = random.choice(COFFEE_MESSAGES)
    
    # Format the message
    message = giving_message.format(drink=chosen_drink, user=target_user)
    
    # Send it!
    bot.action(message)
    if credited:
        bot.notice(f"Daily $100 credited! Paid ${price} - Balance: ${new_balance}", trigger.nick)
    else:
        bot.notice(f"Paid ${price} - Balance: ${new_balance}", trigger.nick)


@module.commands('tea', 'cuppa')
@module.example('$tea', 'Give yourself a random tea')
@module.example('$tea username', 'Give a user a random tea')
def tea(bot, trigger):
    """Give someone a soothing tea! 🍵"""

    # Use sender's nick if no user specified
    if not trigger.group(2):
        target_user = trigger.nick
    else:
        target_user = trigger.group(2).strip()

    # Deduct price from sender's balance
    sender = trigger.account or trigger.nick
    new_balance, credited, price = deduct_price(sender, 'tea')

    if new_balance is None:
        bot.say(f"{trigger.nick}: You don't have enough money! Tea costs ${price}. Use $barcash to check your funds.")
        return

    # Select random tea and message
    chosen_drink = random.choice(TEAS)
    giving_message = random.choice(TEA_MESSAGES)

    # Format the message
    message = giving_message.format(drink=chosen_drink, user=target_user)

    # Send it!
    bot.action(message)
    if credited:
        bot.notice(f"Daily $100 credited! Paid ${price} - Balance: ${new_balance}", trigger.nick)
    else:
        bot.notice(f"Paid ${price} - Balance: ${new_balance}", trigger.nick)


@module.commands('water', 'hydrate')
@module.example('$water', 'Give yourself water')
@module.example('$water username', 'Give a user water - stay hydrated!')
def water(bot, trigger):
    """Give someone water! Stay hydrated! 💧"""
    
    # Use sender's nick if no user specified
    if not trigger.group(2):
        target_user = trigger.nick
    else:
        target_user = trigger.group(2).strip()
    
    # Water is free! But still check for daily credit
    sender = trigger.account or trigger.nick
    new_balance, credited, price = deduct_price(sender, 'water')
    
    # Select random water and message
    chosen_drink = random.choice(WATERS)
    giving_message = random.choice(WATER_MESSAGES)
    
    # Format the message
    message = giving_message.format(drink=chosen_drink, user=target_user)
    
    # Send it!
    bot.action(message)
    if credited:
        bot.notice(f"Daily $100 credited! Water is FREE! Balance: ${new_balance}", trigger.nick)
    else:
        bot.notice(f"Water is FREE! 💧", trigger.nick)


@module.commands('appetizer', 'snack', 'food')
@module.example('$appetizer', 'Give yourself a random appetizer')
@module.example('$appetizer username', 'Give a user a random appetizer')
def appetizer(bot, trigger):
    """Give someone a tasty appetizer! 🍽️"""
    
    # Use sender's nick if no user specified
    if not trigger.group(2):
        target_user = trigger.nick
    else:
        target_user = trigger.group(2).strip()
    
    # Deduct price from sender's balance
    sender = trigger.account or trigger.nick
    new_balance, credited, price = deduct_price(sender, 'appetizer')
    
    if new_balance is None:
        bot.say(f"{trigger.nick}: You don't have enough money! An appetizer costs ${price}. Use $barcash to check your funds.")
        return
    
    # Select random appetizer and message
    chosen_food = random.choice(APPETIZERS)
    giving_message = random.choice(FOOD_MESSAGES)
    
    # Format the message
    message = giving_message.format(food=chosen_food, user=target_user)
    
    # Send it!
    bot.action(message)
    if credited:
        bot.notice(f"Daily $100 credited! Paid ${price} - Balance: ${new_balance}", trigger.nick)
    else:
        bot.notice(f"Paid ${price} - Balance: ${new_balance}", trigger.nick)


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
    all_drinks = BEERS + SHOTS + MAGNERS + WHISKEYS + MIXED_DRINKS + WINES + MOCKTAILS + COFFEES + TEAS + WATERS
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
    data = load_tip_data()

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

    save_tip_data(data)

    bot.say(f"{tipper_display} tips {recipient} ${amount}! 💰✨")
    bot.notice(f"New balance: ${data['balances'][tipper_key]}", tipper_display)


@module.commands('barcash', 'balance')
@module.example('$barcash', 'Check your current balance')
def barcash(bot, trigger):
    """Check your current tip balance! 💵"""
    
    user = str(trigger.account or trigger.nick)
    user_display = trigger.nick
    
    data = load_tip_data()
    current_time = time.time()
    user_key = _user_key(user)

    if user_key not in data['balances']:
        data['balances'][user_key] = 100
        data['last_credit'][user_key] = current_time
        data['tips_received'][user_key] = 0
        save_tip_data(data)
        bot.notice(f"You received your daily $100! Current balance: $100 💵", user_display)
        return

    last_credit = data['last_credit'].get(user_key, 0)
    if current_time - last_credit >= 86400:
        data['balances'][user_key] += 100
        data['last_credit'][user_key] = current_time
        save_tip_data(data)
        bot.notice(f"You received your daily $100! Current balance: ${data['balances'][user_key]} 💵", user_display)
    else:
        bot.notice(f"Your balance is ${data['balances'][user_key]} 💵", user_display)


@module.commands('toptip')
@module.example('$toptip', 'See the top 5 most tipped users')
def toptip(bot, trigger):
    """See the top 5 most tipped bartenders! 🏆"""
    
    data = load_tip_data()
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

    data = load_tip_data()
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
    save_tip_data(data)

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

    data = load_tip_data()

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

        save_tip_data(data)
        bot.reply('All balances reset to $100 and all tips cleared.')
        return

    # Single user reset
    nick = target
    nick_key = _user_key(nick)
    if nick_key not in data.get('balances', {}):
        data['balances'][nick_key] = 100
        data['last_credit'][nick_key] = time.time()
        data['tips_received'][nick_key] = 0
        save_tip_data(data)
        bot.reply(f"{nick} did not have an account; initialized to $100.")
        return

    data['balances'][nick_key] = 100
    data['last_credit'][nick_key] = time.time()
    data['tips_received'][nick_key] = 0
    save_tip_data(data)
    bot.reply(f"Reset {nick}'s balance to $100 and cleared tips.")

