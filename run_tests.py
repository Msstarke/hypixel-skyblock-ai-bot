"""
Test runner — calls AIHandler.get_response() directly, no Discord needed.
Run: python run_tests.py
"""
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

from ai_handler import AIHandler

TESTS = [
    # Hypermax
    ("H1", "what would be the price for a hypermax divans helmet without hot potato and fuming potato books"),
    ("H2", "hypermax divans helmet"),
    ("H3", "hypermax divans helmet without jaded"),
    ("H4", "hypermax necron chestplate for mage"),
    ("H5", "hypermax hyperion"),
    ("H7", "hypermax glacite helmet"),
    # Prices
    ("P1", "what is the price of a hot potato book"),
    ("P2", "how much is a perfect ruby gem"),
    ("P3", "what is the cheapest hyperion on ah"),
    ("P4", "how much is 1000 enchanted melon"),
    ("P5", "whats the price of a divan helmet"),
    # Budget / Gear
    ("B1", "whats a good early game dungeons armor set im cata 0 with a 50mil budget"),
    ("B2", "best mining armor for under 20 million"),
    ("B3", "best mage armor for 200m budget cata 15"),
    ("B4", "best berserk setup for 50m"),
    # Knowledge base
    ("K1", "whats the best mining setup"),
    ("K2", "whats the best mining pet"),
    ("K3", "best dungeon weapon for berserk"),
    ("K4", "whats the best reforge for divans armor"),
    ("K5", "what is the armor of divan"),
    # Recipes
    ("C1", "recipe for divans helmet"),
    ("C2", "how do i get hyperion"),
    ("C3", "how to craft strong dragon helmet"),
    ("C4", "how to get necron armor"),
    # Edge cases
    ("E1", "whats the best pizza topping"),
    ("E2", "what is the dragon claw"),
    ("E3", "hypermax fake item that doesnt exist"),
    ("E4", "what is the best armor"),
    # Wither sets
    ("W1", "what are the 4 wither armor sets from f7"),
]

PASS = "\033[92m✅\033[0m"
FAIL = "\033[91m❌\033[0m"
SEP  = "─" * 70

async def main():
    handler = AIHandler()
    print(f"\n{'='*70}")
    print("  HYPIXEL BOT TEST RUNNER")
    print(f"{'='*70}\n")

    for test_id, question in TESTS:
        print(f"{SEP}")
        print(f"[{test_id}] {question}")
        print(SEP)
        try:
            result = await handler.get_response(question)
            print(result)
        except Exception as e:
            print(f"{FAIL} EXCEPTION: {e}")
        print()

    await handler.hypixel._session_close() if hasattr(handler.hypixel, '_session_close') else None

asyncio.run(main())
