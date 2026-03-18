"""
Diagnostic: check what each price source returns for key items.
Run: python diag_prices.py
"""
import asyncio
import os
import aiohttp
from dotenv import load_dotenv
load_dotenv()

ITEMS = ["ARMOR_OF_DIVAN_HELMET", "NECRONS_CHESTPLATE", "STORM_CHESTPLATE",
         "HYPERION", "GLACITE_HELMET", "PERFECT_RUBY_GEM"]

LOWEST_BIN_URL       = "https://moulberry.codes/lowestbin.json"
AUCTION_AVG_URL      = "https://moulberry.codes/auction_averages_lbin.json"
AUCTION_AVG_ALT_URL  = "https://moulberry.codes/auction_averages.json"
COFLNET_URL          = "https://sky.coflnet.com/api/item/price/{}/current"

async def fetch(session, url):
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as r:
            return r.status, await r.json() if r.status == 200 else await r.text()
    except Exception as e:
        return None, str(e)

async def main():
    async with aiohttp.ClientSession() as session:
        print("=== Fetching price sources ===\n")

        # 1. lowestbin
        status, lbin = await fetch(session, LOWEST_BIN_URL)
        print(f"lowestbin.json: HTTP {status}, {len(lbin) if isinstance(lbin, dict) else 'ERROR'} items")
        if isinstance(lbin, dict):
            for item in ITEMS:
                v = lbin.get(item)
                print(f"  {item}: {v:,.0f}" if v else f"  {item}: NOT FOUND")
        print()

        # 2. auction_averages_lbin.json
        status, avg = await fetch(session, AUCTION_AVG_URL)
        print(f"auction_averages_lbin.json: HTTP {status}, {len(avg) if isinstance(avg, dict) else repr(avg)[:80]}")
        if isinstance(avg, dict):
            for item in ITEMS:
                v = avg.get(item)
                print(f"  {item}: {v:,.0f}" if v else f"  {item}: NOT FOUND")
        print()

        # 3. auction_averages.json
        status, avg2 = await fetch(session, AUCTION_AVG_ALT_URL)
        print(f"auction_averages.json: HTTP {status}, {len(avg2) if isinstance(avg2, dict) else repr(avg2)[:80]}")
        if isinstance(avg2, dict):
            for item in ITEMS:
                v = avg2.get(item)
                print(f"  {item}: {v:,.0f}" if v else f"  {item}: NOT FOUND")
        print()

        # 4. coflnet /current
        print("coflnet /api/item/price/{id}/current:")
        for item in ITEMS:
            status, data = await fetch(session, COFLNET_URL.format(item))
            if isinstance(data, dict):
                print(f"  {item}: HTTP {status} → {data}")
            else:
                print(f"  {item}: HTTP {status} → {repr(data)[:80]}")
        print()

asyncio.run(main())
