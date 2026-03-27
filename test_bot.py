"""
Auto-tester for the Hypixel AI bot.
Fires a set of questions at the live Railway endpoint and grades each response
against expected keywords / patterns.

Usage:
    python test_bot.py                  # test prod (Railway)
    python test_bot.py --local          # test localhost:5000
    python test_bot.py --verbose        # print full responses
    python test_bot.py --suite mining   # run only one suite
    python test_bot.py --fail-only      # only print failed tests
"""

import argparse
import json
import sys
import time
import urllib.request
import urllib.error

RAILWAY_BASE = "https://worker-production-f916.up.railway.app"
LOCAL_BASE   = "http://localhost:5000"
RAILWAY_URL  = RAILWAY_BASE + "/api/ask"
LOCAL_URL    = LOCAL_BASE + "/api/ask"

# Test license key — generated with 'unlimited' plan, no expiry
TEST_LICENSE_KEY = "SKYAI-E2692A451692D7101ABAEBCB"
_session_token = None

# ---------------------------------------------------------------------------
# Test cases
# required_any  — at least ONE of these must appear (case-insensitive)
# required_all  — ALL of these must appear
# bad_keywords  — NONE of these should appear (hallucination markers)
# ---------------------------------------------------------------------------
TESTS = [

    # ═══════════════════════════════════════════════════════════════════════
    # DIANA / MYTHOLOGICAL RITUAL
    # ═══════════════════════════════════════════════════════════════════════
    {
        "suite": "diana",
        "question": "How much profit can I make per hour doing Diana?",
        "required_any": ["70", "100m", "12m", "common", "legendary"],
        "required_all": [],
        "bad_keywords": ["1.5m", "2.5m", "1-2m", "2-3m", "1.5 million", "2 million per hour"],
    },
    {
        "suite": "diana",
        "question": "What is the drop rate for an Inquisitor from Diana?",
        "required_any": ["1/81", "1.23%", "1.2%", "81"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "diana",
        "question": "What mobs can spawn from Diana's mythological ritual?",
        "required_any": ["griffin", "minotaur", "minos", "inquisitor", "chimera"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "diana",
        "question": "What is a Minos Inquisitor and how rare is it?",
        "required_any": ["1/81", "1.23", "rare", "chimera", "daedalus"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "diana",
        "question": "What is the best pet for Diana?",
        "required_any": ["griffin", "legendary", "pet"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "diana",
        "question": "How do I start the Diana event?",
        "required_any": ["diana", "mayor", "medal", "spade", "shovel", "mythological"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "diana",
        "question": "What drops does the Minotaur give in Diana?",
        "required_any": ["minotaur", "labyrinth", "drop", "hair"],
        "required_all": [],
        "bad_keywords": [],
    },

    # ═══════════════════════════════════════════════════════════════════════
    # MINING & CRYSTAL HOLLOWS
    # ═══════════════════════════════════════════════════════════════════════
    {
        "suite": "mining",
        "question": "What mining speed do I need to 4-tick gray mithril?",
        "required_any": ["3334", "3,334", "3300", "3500"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "mining",
        "question": "What mining speed do I need to 4-tick blue mithril?",
        "required_any": ["10000", "10,000"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "mining",
        "question": "How do I get to the Crystal Hollows?",
        "required_any": ["hotm", "heart of the mountain", "mining 6", "dwarven", "deep cavern"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "mining",
        "question": "What is the best pickaxe for mining in SkyBlock?",
        "required_any": ["gemstone", "divan", "hyperion", "sorrow", "reaper", "pickaxe"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "mining",
        "question": "What does Mining Speed do?",
        "required_any": ["break", "faster", "tick", "speed", "block"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "mining",
        "question": "What is HOTM and how do I level it up?",
        "required_any": ["heart of the mountain", "hotm", "token", "perk"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "mining",
        "question": "What is Powder used for in mining?",
        "required_any": ["hotm", "perk", "mithril powder", "gemstone powder", "glacite"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "mining",
        "question": "What is the best way to get mithril in SkyBlock?",
        "required_any": ["dwarven", "hotm", "mithril", "mine"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "mining",
        "question": "How does Glacite Powder differ from Mithril Powder?",
        "required_any": ["glacite", "mithril", "powder", "hotm"],
        "required_all": [],
        "bad_keywords": [],
    },

    # ═══════════════════════════════════════════════════════════════════════
    # DUNGEONS
    # ═══════════════════════════════════════════════════════════════════════
    {
        "suite": "dungeons",
        "question": "What gear should I use as a cata 0 mage?",
        "required_any": ["zombie", "spider", "lapis", "wise dragon", "crystal", "mage"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "dungeons",
        "question": "Is the Rogue Sword good for dungeons?",
        "required_any": ["not", "low", "common", "upgrade", "better", "limited"],
        "required_all": [],
        "bad_keywords": ["yes", "great", "recommended", "best"],
    },
    {
        "suite": "dungeons",
        "question": "What is the best class for early dungeons?",
        "required_any": ["berserk", "healer", "mage", "archer", "tank", "class"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "dungeons",
        "question": "What floors are in The Catacombs?",
        "required_any": ["floor", "f1", "f2", "f3", "f4", "f5", "f6", "f7", "master"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "dungeons",
        "question": "What is Catacombs XP and how do I level it up?",
        "required_any": ["cata", "xp", "experience", "floor", "dungeon"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "dungeons",
        "question": "What is the best sword for dungeons?",
        "required_any": ["hyperion", "shadow fury", "livid", "florid", "sword"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "dungeons",
        "question": "How do I get the Livid Dagger?",
        "required_any": ["livid", "f5", "floor 5", "drop", "boss"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "dungeons",
        "question": "What is a S+ run and how do I get one?",
        "required_any": ["s+", "score", "300", "time", "secret", "puzzle"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "dungeons",
        "question": "What does Bonzo's Mask do?",
        "required_any": ["bonzo", "death", "revive", "survive", "one-shot"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "dungeons",
        "question": "What is the Master Mode in dungeons?",
        "required_any": ["master", "m1", "m2", "m3", "m4", "m5", "m6", "m7", "harder", "cata 20"],
        "required_all": [],
        "bad_keywords": [],
    },

    # ═══════════════════════════════════════════════════════════════════════
    # SLAYER
    # ═══════════════════════════════════════════════════════════════════════
    {
        "suite": "slayer",
        "question": "How do I unlock slayers?",
        "required_any": ["slayer", "tier", "combat", "boss", "slay"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "slayer",
        "question": "What is the best weapon for Revenant Horror slayer?",
        "required_any": ["revenant", "zombie", "sword", "reaper", "weapon"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "slayer",
        "question": "What gear do I need for T4 Sven slayer?",
        "required_any": ["sven", "wolf", "t4", "gear", "armor"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "slayer",
        "question": "What is the best pet for Enderman slayer?",
        "required_any": ["ender", "enderman", "pet", "voidwalker", "wither"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "slayer",
        "question": "What does the Voidgloom Seraph boss do?",
        "required_any": ["voidgloom", "enderman", "seraph", "beacon", "hits"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "slayer",
        "question": "How much coins does a T4 Revenant slayer cost?",
        "required_any": ["coins", "cost", "revenant", "t4", "4"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "slayer",
        "question": "What is Blaze slayer and how do I unlock it?",
        "required_any": ["blaze", "crimson", "isle", "inferno", "slayer"],
        "required_all": [],
        "bad_keywords": [],
    },

    # ═══════════════════════════════════════════════════════════════════════
    # COMBAT & GEAR
    # ═══════════════════════════════════════════════════════════════════════
    {
        "suite": "combat",
        "question": "What is the best early game sword in SkyBlock?",
        "required_any": ["aspect", "livid", "shadow fury", "dreadlord", "sword"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "combat",
        "question": "What is the best armor set for mid game?",
        "required_any": ["dragon", "storm", "shadow", "ferrite", "armor"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "combat",
        "question": "What is Crit Chance and Crit Damage?",
        "required_any": ["crit", "chance", "damage", "%", "critical"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "combat",
        "question": "How does True Defense work?",
        "required_any": ["true defense", "defense", "bypass", "reduce"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "combat",
        "question": "What is Ferocity in SkyBlock?",
        "required_any": ["ferocity", "hit", "extra", "attack", "double"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "combat",
        "question": "What is the best talisman/accessory for damage?",
        "required_any": ["talisman", "accessory", "reforge", "critical", "damage"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "combat",
        "question": "How do reforges work?",
        "required_any": ["reforge", "blacksmith", "attribute", "stat", "stone"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "combat",
        "question": "What is the Hyperion sword and how do I get it?",
        "required_any": ["hyperion", "necron", "wither", "dungeons", "blade"],
        "required_all": [],
        "bad_keywords": [],
    },

    # ═══════════════════════════════════════════════════════════════════════
    # FISHING
    # ═══════════════════════════════════════════════════════════════════════
    {
        "suite": "fishing",
        "question": "What is the best rod for fishing in SkyBlock?",
        "required_any": ["rod", "fishing", "attract", "orca", "grim"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "fishing",
        "question": "How do I unlock Thunder or Lord Jawbus sea creatures?",
        "required_any": ["thunder", "jawbus", "lightning", "fishing", "sea creature"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "fishing",
        "question": "What is the Fishing Festival event?",
        "required_any": ["fishing festival", "festival", "trophy", "bragging"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "fishing",
        "question": "What is the best bait for fishing?",
        "required_any": ["bait", "fish", "sea creature", "chance"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "fishing",
        "question": "What is the Blessed Bait?",
        "required_any": ["blessed", "bait", "fishing"],
        "required_all": [],
        "bad_keywords": [],
    },

    # ═══════════════════════════════════════════════════════════════════════
    # FARMING
    # ═══════════════════════════════════════════════════════════════════════
    {
        "suite": "farming",
        "question": "What is the best crop to farm for money?",
        "required_any": ["pumpkin", "melon", "cane", "sugar", "cactus", "wheat", "carrot", "potato", "mushroom", "nether wart"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "farming",
        "question": "How does Jacob's Farming Contest work?",
        "required_any": ["jacob", "contest", "crop", "bronze", "silver", "gold"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "farming",
        "question": "What is the best hoe for farming?",
        "required_any": ["hoe", "farm", "farming"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "farming",
        "question": "What is Farming Fortune?",
        "required_any": ["fortune", "farming", "crop", "yield", "extra"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "farming",
        "question": "How do I unlock the Wheat Island or Garden?",
        "required_any": ["garden", "plot", "island", "farm", "wheat"],
        "required_all": [],
        "bad_keywords": [],
    },

    # ═══════════════════════════════════════════════════════════════════════
    # FORAGING
    # ═══════════════════════════════════════════════════════════════════════
    {
        "suite": "foraging",
        "question": "What is the best axe for foraging?",
        "required_any": ["axe", "jungle", "treecapitator", "foraging"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "foraging",
        "question": "How does Foraging Fortune work?",
        "required_any": ["fortune", "foraging", "log", "wood", "extra"],
        "required_all": [],
        "bad_keywords": [],
    },

    # ═══════════════════════════════════════════════════════════════════════
    # PETS
    # ═══════════════════════════════════════════════════════════════════════
    {
        "suite": "pets",
        "question": "What is the best pet for combat?",
        "required_any": ["tiger", "lion", "golden dragon", "enderman", "pet"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "pets",
        "question": "What does the Legendary Golden Dragon pet do?",
        "required_any": ["golden dragon", "xp", "coins", "level 100", "dragon"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "pets",
        "question": "What is the best pet for mining?",
        "required_any": ["silverfish", "bal", "scatha", "pet", "mining"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "pets",
        "question": "How do I level up my pet?",
        "required_any": ["xp", "exp", "combat", "skill", "level", "pet"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "pets",
        "question": "What is a pet item and what does it do?",
        "required_any": ["pet item", "bonus", "stat", "equip"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "pets",
        "question": "What is the best pet for farming?",
        "required_any": ["elephant", "mooshroom", "rabbit", "bee", "pet", "farming"],
        "required_all": [],
        "bad_keywords": [],
    },

    # ═══════════════════════════════════════════════════════════════════════
    # SKYBLOCK TIME & EVENTS
    # ═══════════════════════════════════════════════════════════════════════
    {
        "suite": "time",
        "question": "What SkyBlock year is it right now?",
        "required_any": ["385", "386", "387", "388", "year"],
        "required_all": [],
        "bad_keywords": ["i don't know", "cannot determine", "i do not have"],
    },
    {
        "suite": "time",
        "question": "When is Jerry's Workshop open?",
        "required_any": ["late winter", "winter", "jerry"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "time",
        "question": "When is Shen's Auction?",
        "required_any": ["late spring", "spring", "shen"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "time",
        "question": "How long is a SkyBlock day in real time?",
        "required_any": ["20 minutes", "20", "1200 seconds", "real", "minute"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "time",
        "question": "When is the Spooky Festival?",
        "required_any": ["spooky", "late autumn", "autumn", "halloween", "october"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "time",
        "question": "When does the Dark Auction happen?",
        "required_any": ["dark auction", "3am", "3:00", "scorpius", "auction"],
        "required_all": [],
        "bad_keywords": [],
    },

    # ═══════════════════════════════════════════════════════════════════════
    # MAYORS
    # ═══════════════════════════════════════════════════════════════════════
    {
        "suite": "mayors",
        "question": "How many pelts per hour can I get with Finnegan as mayor?",
        "required_any": ["150", "200", "550", "pelt"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "mayors",
        "question": "What does the Scorpius mayor do?",
        "required_any": ["bribe", "corrupt", "dark auction"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "mayors",
        "question": "What does Paul mayor do?",
        "required_any": ["paul", "ezra", "couture", "perk", "mayor"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "mayors",
        "question": "What is the best mayor for combat?",
        "required_any": ["mayor", "diana", "paul", "combat", "perk"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "mayors",
        "question": "How does mayor voting work in SkyBlock?",
        "required_any": ["vote", "election", "mayor", "year", "perk"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "mayors",
        "question": "What does Jerry mayor do?",
        "required_any": ["jerry", "workshop", "random", "perk", "mayor"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "mayors",
        "question": "What is the best mayor for farming?",
        "required_any": ["mayor", "farming", "perk", "jacob", "crop"],
        "required_all": [],
        "bad_keywords": [],
    },

    # ═══════════════════════════════════════════════════════════════════════
    # ECONOMY & BAZAAR
    # ═══════════════════════════════════════════════════════════════════════
    {
        "suite": "economy",
        "question": "How does the Bazaar work in SkyBlock?",
        "required_any": ["bazaar", "buy order", "sell offer", "instasell", "instabuy"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "economy",
        "question": "What is flipping and how do I make money from it?",
        "required_any": ["flip", "buy", "sell", "profit", "auction", "bazaar"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "economy",
        "question": "What is the best way to make money as a new player?",
        "required_any": ["farm", "mine", "money", "coins", "profit"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "economy",
        "question": "How does the Auction House work?",
        "required_any": ["auction", "bid", "buy", "sell", "bin", "best offer"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "economy",
        "question": "What are NPC buy prices good for?",
        "required_any": ["npc", "price", "floor", "profit", "sell"],
        "required_all": [],
        "bad_keywords": [],
    },

    # ═══════════════════════════════════════════════════════════════════════
    # SKILLS & PROGRESSION
    # ═══════════════════════════════════════════════════════════════════════
    {
        "suite": "skills",
        "question": "What skill XP bonus does Pelts give?",
        "required_any": ["pelt", "skill", "xp", "trapper", "finnegan"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "skills",
        "question": "What is the fastest way to level combat skill?",
        "required_any": ["combat", "xp", "spider", "enderman", "ghast", "slayer", "dungeon"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "skills",
        "question": "What is the fastest way to level enchanting?",
        "required_any": ["enchant", "enchanting", "xp", "books", "table", "level"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "skills",
        "question": "What is the Skill Average and why does it matter?",
        "required_any": ["skill", "average", "stat", "bonus", "health", "strength"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "skills",
        "question": "What is Runecrafting skill?",
        "required_any": ["runecrafting", "rune", "cosmetic", "skill"],
        "required_all": [],
        "bad_keywords": [],
    },

    # ═══════════════════════════════════════════════════════════════════════
    # KUUDRA / NETHER
    # ═══════════════════════════════════════════════════════════════════════
    {
        "suite": "nether",
        "question": "What is Kuudra and how do I fight it?",
        "required_any": ["kuudra", "crimson", "isle", "boss", "nether"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "nether",
        "question": "What is the best armor for Crimson Isle?",
        "required_any": ["crimson", "ferrite", "aurora", "terror", "armor"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "nether",
        "question": "What are Kuudra tokens used for?",
        "required_any": ["token", "kuudra", "upgrade", "shop", "buy"],
        "required_all": [],
        "bad_keywords": [],
    },

    # ═══════════════════════════════════════════════════════════════════════
    # ACCESSORIES / TALISMAN BAG
    # ═══════════════════════════════════════════════════════════════════════
    {
        "suite": "accessories",
        "question": "What is the Talisman Bag?",
        "required_any": ["talisman", "accessory", "bag", "slot", "passive"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "accessories",
        "question": "What is the best accessory reforge for damage?",
        "required_any": ["reforge", "fierce", "itchy", "godly", "hurtful", "strong"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "accessories",
        "question": "What is the Hegemony Artifact?",
        "required_any": ["hegemony", "artifact", "extra", "accessory"],
        "required_all": [],
        "bad_keywords": [],
    },

    # ═══════════════════════════════════════════════════════════════════════
    # ISLANDS & LOCATIONS
    # ═══════════════════════════════════════════════════════════════════════
    {
        "suite": "locations",
        "question": "How do I get to the Spider's Den?",
        "required_any": ["spider", "den", "warp", "combat"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "locations",
        "question": "What is the End island good for?",
        "required_any": ["end", "ender", "enderman", "dragon", "voidwalker"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "locations",
        "question": "What is the best place to grind combat XP early game?",
        "required_any": ["spider", "zombie", "combat", "xp", "ghast", "enderman"],
        "required_all": [],
        "bad_keywords": [],
    },

    # ═══════════════════════════════════════════════════════════════════════
    # MISC / GENERAL
    # ═══════════════════════════════════════════════════════════════════════
    {
        "suite": "general",
        "question": "What is SkyBlock essence and how do I use it?",
        "required_any": ["essence", "upgrade", "dungeon", "star", "item"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "general",
        "question": "What are SkyBlock profiles?",
        "required_any": ["profile", "island", "coop", "bingo", "ironman"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "general",
        "question": "How does the Co-op system work?",
        "required_any": ["coop", "co-op", "profile", "share", "member"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "general",
        "question": "What is the best way to upgrade my gear?",
        "required_any": ["reforge", "enchant", "star", "essence", "upgrade"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "general",
        "question": "What is a Starred item in SkyBlock?",
        "required_any": ["star", "essence", "dungeons", "dungeon", "upgrade"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "general",
        "question": "What is the Fairy Soul and why do I need them?",
        "required_any": ["fairy soul", "health", "stat", "boost", "wanda"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "general",
        "question": "How do I unlock the Bazaar?",
        "required_any": ["bazaar", "hub", "trading", "unlock", "level"],
        "required_all": [],
        "bad_keywords": [],
    },
]


# ---------------------------------------------------------------------------

def ask(url: str, question: str) -> tuple[str, float]:
    payload = json.dumps({"question": question}).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read())
            elapsed = time.time() - t0
            return body.get("response") or body.get("answer") or str(body), elapsed
    except urllib.error.HTTPError as e:
        return f"HTTP {e.code}: {e.read().decode()[:200]}", time.time() - t0
    except Exception as ex:
        return f"ERROR: {ex}", time.time() - t0


def grade(response: str, test: dict) -> tuple[bool, str]:
    low = response.lower()
    for bad in test.get("bad_keywords", []):
        if bad.lower() in low:
            return False, f"HALLUCINATION: found '{bad}'"
    any_kw = test.get("required_any", [])
    if any_kw and not any(k.lower() in low for k in any_kw):
        return False, f"MISSING any of {any_kw}"
    for req in test.get("required_all", []):
        if req.lower() not in low:
            return False, f"MISSING required '{req}'"
    return True, "OK"


def run(url: str, suite_filter: str | None, verbose: bool, fail_only: bool):
    tests = TESTS
    if suite_filter:
        tests = [t for t in TESTS if t["suite"] == suite_filter]
        if not tests:
            print(f"No tests found for suite '{suite_filter}'")
            sys.exit(1)

    passed = failed = 0
    results = []

    total = len(tests)
    for i, t in enumerate(tests, 1):
        print(f"  [{i}/{total}] {t['suite']}: {t['question'][:60]}...", end="\r", flush=True)
        resp, elapsed = ask(url, t["question"])
        ok, reason = grade(resp, t)
        if ok:
            passed += 1
        else:
            failed += 1
        results.append((ok, t["suite"], t["question"], reason, resp, elapsed))

    print(" " * 80, end="\r")  # clear progress line

    # ── Print results ─────────────────────────────────────────────────────
    print(f"\n{'='*70}")
    print(f"  Hypixel AI Bot -- Auto Test Results")
    print(f"  URL: {url}")
    print(f"{'='*70}")

    current_suite = None
    for ok, suite, question, reason, resp, elapsed in results:
        if fail_only and ok:
            continue
        if suite != current_suite:
            current_suite = suite
            print(f"\n  [{suite.upper()}]")
        status = "PASS" if ok else "FAIL"
        icon = "+" if ok else "X"
        print(f"\n  [{icon}] {question}")
        print(f"       > {reason}  ({elapsed:.1f}s)")
        if verbose or not ok:
            clean = resp.replace("\n", " ").encode("ascii", "replace").decode()
            print(f"       Response: {clean[:400]}")

    # ── Summary by suite ──────────────────────────────────────────────────
    print(f"\n{'='*70}")
    suite_stats: dict[str, list[int]] = {}
    for ok, suite, *_ in results:
        suite_stats.setdefault(suite, [0, 0])
        if ok:
            suite_stats[suite][0] += 1
        else:
            suite_stats[suite][1] += 1

    for suite, (p, f) in suite_stats.items():
        bar = "#" * p + "." * f
        print(f"  {suite:<15} {p}/{p+f}  [{bar}]")

    total_n = passed + failed
    pct = int(passed / total_n * 100) if total_n else 0
    print(f"\n  TOTAL: {passed}/{total_n} passed  ({pct}%)")
    if failed:
        print(f"  FAILED: {failed} tests")
    print(f"{'='*70}\n")

    return failed == 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--local",     action="store_true", help="Test localhost:5000 instead of Railway")
    parser.add_argument("--verbose",   action="store_true", help="Print full responses for all tests")
    parser.add_argument("--fail-only", action="store_true", help="Only print failed tests")
    parser.add_argument("--suite",     type=str,            help="Run only this suite")
    args = parser.parse_args()

    url = LOCAL_URL if args.local else RAILWAY_URL
    success = run(url, args.suite, args.verbose, args.fail_only)
    sys.exit(0 if success else 1)
