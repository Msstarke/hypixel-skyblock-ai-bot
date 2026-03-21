# Fishing Skill

Fishing is one of the core player Skills in Hypixel SkyBlock. It is leveled up by catching items, treasure, and by killing Sea Creatures.

## Leveling Rewards

Leveling up Fishing grants:
- Health (HP) per level
- Treasure Chance per level
- Increased maximum coin treasures from fishing (formula: MaxCoins = BaseMaxCoins * (1 + FishingLevel / Multiplier), where Multiplier is 2.5 for water and 5 for lava)
- Ability to catch tougher and more valuable Sea Creatures
- Access to better fishing gear (rods, armor)
- One-time coin rewards for level-ups

Cumulative rewards at Fishing 25:
- +2.5 Treasure Chance
- +67 HP
- 30,475 Coins
- 200 SkyBlock XP

Cumulative rewards at Fishing 50:
- +5 Treasure Chance
- +192 HP
- 1,406,475 Coins
- 700 SkyBlock XP

The highest Fishing level required to unlock all content is Fishing 45. Excluding the Crimson Isle, the highest required is Fishing 35.

---

# Fishing Mechanics

## How Fishing Works

The player fishes by casting a Fishing Rod into Water or Lava. After a period of time, they catch an item, treasure (coins), or a Sea Creature. The player can also fish on Dirt using a Dirt Rod (gimmick only, not meaningful for progression).

## Fishing Speed

Fishing Speed determines how quickly the player catches something. The formula for ticks until a catch:

Ticks = (random number between 400 and (400 - 10 * LureEnchantmentTier)) * FishingSpeedMultiplier

Seconds = Ticks / 20 (at default 20 ticks per second)

### Fishing Speed Multipliers by Source

| Source | Multiplier |
|--------|-----------|
| Fishing Rods | 0.25-0.9 (depends on rod) |
| Minnow Bait | 0.85 |
| Fish Bait | 0.7 |
| Whale Bait | 0.8 |
| Spooky Bait | 0.85 |
| Fish Affinity Talisman | 0.95 |
| Dolphin Pet | Varies |
| Ammonite Pet | Varies |
| Flying Fish Pet | Varies |

Lower multiplier = faster fishing.

## Sea Creature Chance (SCC)

Sea Creature Chance determines the probability of catching a Sea Creature instead of an item/treasure. The player's SCC percentage equals their chance to catch a Sea Creature. SCC is reduced on Private Islands. Sea creatures caught on Private Islands do not give Fishing XP.

## Double Hook Chance (DHC)

Double Hook Chance determines the chance of fishing two Sea Creatures at once.

## Treasure Chance

When no Sea Creature is caught, there is:
- 89% base chance for a GOOD CATCH
- 10% base chance for a GREAT CATCH
- 1% base chance for an OUTSTANDING CATCH

Great and Outstanding chances can be increased with Blessed Bait, the Blessing enchantment, and Rare+ Hermit Crab Pet.

## Fishing Fortune

Fishing Fortune increases the amount of items obtained from fishing drops, similar to how Mining Fortune works for mining.

## Coin Treasures

- Base water fishing coin range: 1,000-21,000
- Base lava fishing coin range: 500-10,500
- Coins scale with fishing level using the formula above
- Chance to get coins from treasures: approximately 31.8%

## Location-Based Drops

In certain fishing locations, there is a 25% chance for drops to come from a location-unique loot pool.

---

# Fishing Rods

## Water Fishing Rods

| Rod Name | Fishing Speed | SCC | Bonus Effect | Fishing Level Required | How to Obtain |
|----------|--------------|-----|--------------|----------------------|---------------|
| Fishing Rod | - | - | - | - | Vanilla recipe |
| Challenging Rod | +75 | +2% | - | 10 | - |
| Rod of Champions | +90 | +4% | 1 Gemstone slot | 15 | Lily Pad VII Collection |
| Winter Rod | +75 | - | +5% SCC while on Jerry's Workshop; 1 Gemstone slot | 10 | Sold by Sherry NPC |
| Rod of Legends | +105 | +6% | 2 Gemstone slots | 20 | Lily Pad IX Collection |
| Rod of the Sea | +110 | +7% | 2 Gemstone slots | 24 | Crafted (Rod of Legends + Great White Shark Teeth) |
| Giant Fishing Rod | +20 | - | 50% chance to fish a sea creature twice; 1 Gemstone slot | - | Shen's Auction |

## Lava Fishing Rods

| Rod Name | Fishing Speed | SCC | Bonus Effect | Fishing Level Required | How to Obtain | Medium |
|----------|--------------|-----|--------------|----------------------|---------------|--------|
| Starter Lava Rod | +8 | - | - | 10 | Odger NPC | Lava |
| Magma Rod | +40 | +6% | +10% Trophy Fish chance; 1 Gemstone slot | 27 | Magmafish IV Collection | Lava |
| Inferno Rod | +60 | +10% | +15% Trophy Fish chance; 2 Gemstone slots | 30 | Magmafish VIII Collection | Lava |
| Hellfire Rod | +180 | +14% | +20% Trophy Fish chance; 2 Gemstone slots | 35 | Magmafish XII Collection | Lava |
| Topaz Rod | +50 | +2% | - | - | The Forge | Lava |
| Dirt Rod | +15 | - | Allows fishing on Dirt | - | Shen's Auction | Dirt |

## Rod Parts

Rod Parts come in three variants: Hooks, Lines, and Sinkers.

### Hooks (increase chance to catch certain items/creatures)

| Name | Effect | Fishing Level Required | Source |
|------|--------|----------------------|--------|
| Common Hook | +25% chance to catch Common Sea Creatures | 5 | Crafting |
| Hotspot Hook | +100% chance to catch Hotspot Sea Creatures | 20 | Crafting |
| Phantom Hook | +100% chance to catch Spooky Sea Creatures | 21 | 1% drop from Phantom Fisher |
| Treasure Hook | Only allows catching items and Treasure (no Sea Creatures) | 25 | Purchased from Junker Joel |

### Lines (grant global stat bonuses)

| Name | Effect | Fishing Level Required | Source |
|------|--------|----------------------|--------|
| Speedy Line | +10 Fishing Speed to Fishing Rods | 5 | Purchase from Junker Joel |
| Shredded Line | +250 Damage, +50 Ferocity to Fishing Rods | 20 | 2% drop from The Loch Emperor |
| Titan Line | +2 Double Hook Chance to Fishing Rods | 35 | Crafting |

### Sinkers (miscellaneous special abilities)

| Name | Effect | Fishing Level Required | Source |
|------|--------|----------------------|--------|
| Junk Sinker | +10 Treasure Chance in Backwater Bayou; replaces all Treasures with Junk | 5 | Junker Joel (10k coins) |
| Prismarine Sinker | Materializes Prismarine Shards or Crystals when catching something | 5 | Crafting |
| Sponge Sinker | Materializes Sponges when catching something | 5 | Crafting |
| Chum Sinker | Materializes Chum when catching something | 5 | Purchase from Moby |
| Festive Sinker | 5% chance to materialize Gifts when catching something | 5 | Purchase from Sherry (50k coins) |
| Icy Sinker | +200% chance to catch Winter Sea Creatures | 5 | 4% drop from Frozen Steve |
| Stingy Sinker | 10% chance to not consume Bait | 5 | Purchase from Junker Joel |
| Hotspot Sinker | +100% bonuses from Fishing Hotspots | 20 | Crafting |

---

# Fishing Baits

Baits provide bonus effects while fishing. They are consumed when a Fishing Rod is cast into a fishing source. Baits work from the Fishing Bag or inventory.

| Bait | Rarity | Effect |
|------|--------|--------|
| Minnow Bait | Common | +25 Fishing Speed |
| Fish Bait | Common | +45 Fishing Speed |
| Light Bait | Common | Increases chance to catch rare Sea Creatures during the day (+25% weight to rare sea creatures) |
| Dark Bait | Common | Increases chance to catch rare Sea Creatures during the night (+25% weight to rare sea creatures) |
| Spiked Bait | Common | +6 Sea Creature Chance |
| Spooky Bait | Common | +25 Fishing Speed, +15% chance to catch Spooky Sea Creatures |
| Carrot Bait | Common | Chance of fishing up Carrot King |
| Corrupted Bait | Common | -50% Fishing Speed, but lures special Obfuscated Trophy Fish in the Crimson Isle |
| Blessed Bait | Uncommon | 15% chance to get double drops from fishing |
| Ice Bait | Uncommon | +20% chance to catch Winter Sea Creatures during Season of Jerry |
| Shark Bait | Uncommon | +20% chance to catch Sharks during Fishing Festival |
| Glowy Chum Bait | Uncommon | +25 Fishing Speed, +3 SCC, +2 Chum dropped from Sea Creatures |
| Hot Bait | Uncommon | +5% chance to catch Trophy Fish |
| Worm Bait | Uncommon | +60 Fishing Speed but only Worms will bite (Crystal Hollows only) |
| Golden Bait | Uncommon | +4 Treasure Chance |
| Treasure Bait | Rare | +10 Fishing Speed, +2 Treasure Chance |
| Frozen Bait | Rare | +35% chance to catch Winter Sea Creatures during Season of Jerry |
| Whale Bait | Rare | +30 Fishing Speed, +10% chance for double drops, increases rare Sea Creature catch chance (+25% weight) |
| Wooden Bait | Uncommon | Next GOOD CATCH hooks a Rare Fishing Shard (not consumed if none available) |

---

# Fishing Armor and Gear

## Fishing Armor Sets

| Armor Set | Fishing Level Required | SCC Per Piece | Special Effects |
|-----------|----------------------|---------------|-----------------|
| Angler Armor | - | +1% | Full Set: -30% damage from Sea Creatures; Deepness Within: +10 HP per Fishing Level |
| Salmon Armor | 13 | +1.5% | Water Burst: Burst underwater by sneaking |
| Sponge Armor | 17 | +1.8% | Full Set: Doubles Defense while in water |
| Diver's Armor | 20 | +2% | Full Set: Move incredibly fast and breathe permanently while touching water |
| Shark Scale Armor | 24 | +2.5% | Full Set: Defense doubled while touching/near water; Reflect 15% damage back to attacker |
| Nutcracker Armor | 28 | +1.5% | Stats doubled while on Jerry's Workshop |
| Thunder Armor | 36 | +4% | -10% damage from Lava Sea Creatures, 1.2x damage dealt to them |
| Magma Lord Armor | 45 | +4.5% | -15% damage from Lava Sea Creatures, 1.3x damage dealt to them |

### Lava Fishing Armor Pieces (Mixed Set)

| Piece | Fishing Level Required | SCC | Effect |
|-------|----------------------|-----|--------|
| Slug Boots | 27 | +3% | -5% damage from Lava Sea Creatures, 1.1x damage dealt |
| Moogma Leggings | 28 | +3% | -5% damage from Lava Sea Creatures, 1.1x damage dealt |
| Flaming Chestplate | 33 | +3% | -5% damage from Lava Sea Creatures, 1.1x damage dealt |
| Taurus Helmet | 35 | +3% | -5% damage from Lava Sea Creatures, 1.1x damage dealt |

### Trophy Hunter Armor Sets

| Armor Set | Requirement | Effect |
|-----------|------------|--------|
| Bronze Hunter Armor | Novice Trophy Fisher (15 Bronze+ Trophy Fish) | +5 Trophy Fish Chance |
| Silver Hunter Armor | Adept Trophy Fisher (Silver+ of all Trophy Fish) | +10 Trophy Fish Chance |
| Gold Hunter Armor | Expert Trophy Fisher (Gold+ of all Trophy Fish) | +20 Trophy Fish Chance |
| Diamond Hunter Armor | Master Trophy Fisher (all tiers of all Trophy Fish) | +30 Trophy Fish Chance |

## Fishing Accessories

| Accessory | Effect |
|-----------|--------|
| Fish Affinity Talisman | +10 Fishing Speed |
| Bait Ring | 5% chance not to consume Bait |
| Spiked Atrocity | 10% chance not to consume Bait |
| Sea Creature Talisman/Ring/Artifact | -5/10/15% damage from Sea Creatures |
| Squid Hat | Extra chance to fish up Squids (+100% weight) |
| Water Hydra Head | +1.8% SCC |
| Squid Boots | +1% SCC |
| Delirium Necklace | +1% SCC (increases fire damage taken by 8% per 1 Strength) |
| Odger's Bronze Tooth | +0.5% SCC, +1% Trophy Fish Chance (Novice Trophy Fisher) |
| Odger's Silver Tooth | +1% SCC, +2% Trophy Fish Chance (Adept Trophy Fisher) |
| Odger's Gold Tooth | +1.5% SCC, +3% Trophy Fish Chance (Expert Trophy Fisher) |
| Odger's Diamond Tooth | +2% SCC, +4% Trophy Fish Chance (Master Trophy Fisher) |
| Shark Tooth Necklaces | +2-10 Strength, +5-25% Shark Tooth drop chance (5 tiers) |

## Fishing Pets

| Pet | Key Abilities |
|-----|--------------|
| Dolphin Pet | Increases Fishing Speed and SCC; stuns Sea Creatures after fishing them up |
| Flying Fish Pet | Increases Fishing Speed; boosts Diver's Armor stats; gives Strength and Defense near water |
| Ammonite Pet | Increases Fishing Speed based on Mining level; SCC based on Heart of the Mountain level |
| Squid Pet | Chance for double drops from Squids; Fishing XP Boost |
| Megalodon Pet | Increases Shark Scale Armor stats; gives Strength, Damage, and Magic Find bonus |
| Baby Yeti Pet | Dropped from Yeti sea creature (Epic 3%, Legendary 1.5%) |

---

# Sea Creatures

Sea Creatures are mobs caught while fishing. The type depends on the player's Fishing level, location, and fishing medium (Water or Lava). Sea Creatures drop loot and Fishing XP when killed.

## Sea Creature Mechanics

- SCC determines the chance to catch a Sea Creature (percentage equals chance)
- Sea Creatures take 2x damage from Fishing Rods and Fishing Weapons
- Sea Creatures cannot be damaged by arrows (except Prismarine Bow)
- Sea Creature cap: 60 per server; 20 per player in Crystal Hollows; 5 per player in Crimson Isle
- Sea Creatures despawn if not killed within 6 minutes or if their fisher leaves the server
- The /scg command opens the Sea Creature Guide in-game

## Sea Creature Weight System

Sea creature weight determines catch probability. Higher weight = more common catch.

Catch Rate = (Sea Creature Weight / Combined Weight of All Available Sea Creatures) * 100%

### Weight Modifiers

| Item | Effect |
|------|--------|
| Squid Hat | +100% weight of Squids and Night Squids |
| Icy Sinker | +200% weight of Winter Sea Creatures |
| Spooky Bait | +15% weight of Spooky Sea Creatures |
| Ice Bait | +20% weight of Winter Sea Creatures |
| Frozen Bait | +35% weight of Winter Sea Creatures |
| Shark Bait | +20% weight of Sharks |
| Light Bait | +25% weight of rare Sea Creatures (daytime) |
| Dark Bait | +25% weight of rare Sea Creatures (nighttime) |
| Whale Bait | +25% weight of rare Sea Creatures |
| Bat Pet | +25% weight of Spooky Sea Creatures |
| Megalodon Pet (Legendary) | +20% weight of Sharks |
| Enderman Slayer IX | +15% weight of Elusive Sea Creatures |
| Drake Piper perk (Essence Shop) | +10% weight of Reindrake |
| Doug - Icy Hook perk | +2-10% weight of Winter Sea Creatures |
| Doug - Spooky Hook perk | +2-10% weight of Spooky Sea Creatures |
| Doug - Shark Sonar perk | +2-10% weight of Sharks |

## Water Sea Creatures (Normal)

| Sea Creature | Combat Lvl | HP | Damage | Fishing Lvl Required | Base Weight | Fishing XP | Notable Drops |
|-------------|-----------|-----|--------|---------------------|-------------|------------|---------------|
| Squid | 1 | 50 | 0 | 1 | 1,200 | 75 | Ink Sack, Lily Pad |
| Sea Walker | 4 | 100 | 10 | 1 | 800 | 150 | Rotten Flesh, Raw Fish |
| Night Squid | 6 | 4,000 | 0 | 3 (needs Dark Bait + nighttime) | 1,100 | 270 | Ink Sack, Squid Boots (8%) |
| Sea Guardian | 10 | 5,000 | 150 | 5 | 600 | 250 | Prismarine Crystals, Prismarine Shards |
| Sea Witch | 15 | 6,000 | 150 | 7 | 700 | 400 | Fairy Armor (5%), Clownfish (20%) |
| Sea Archer | 15 | 7,000 | 140 | 9 | 550 | 169 | Bones, Enchanted Bone (1%) |
| Rider of the Deep | 20 | 20,000 | 225 | 11 | 400 | 338 | Enchanted Feather, Sponge (20%) |
| Catfish | 23 | 26,000 | 250 | 13 | 250 | 405 | Raw Salmon, Pufferfish, Clownfish |
| Carrot King | 25 | 32,000 | 275 | 14 (needs Carrot Bait) | 300 | 810 | Lucky Clover Core (0.66%), Rabbit Hat (25%) |
| Agarimoo | 35 | 55,000 | 500 | 15 (needs Empty Chumcap Bucket) | 950 | 80 | Red Mushrooms, Agarimoo Tongue |
| Sea Leech | 30 | 60,000 | 300 | 16 | 160 | 675 | Sponge (40%), Fishing Exp Boost books |
| Guardian Defender | 45 | 76,000 | 250 | 17 | 130 | 1,013 | Enchanted Prismarine Crystals/Shards |
| Deep Sea Protector | 60 | 150,000 | 300 | 18 | 88 | 1,350 | Enchanted Iron |
| Water Hydra | 100 | 500,000 | 400 | 19 | 18 | 2,025 | Water Hydra Head (14%), Fish Affinity Talisman (30%) |

## Oasis Sea Creatures (Mushroom Desert)

| Sea Creature | Combat Lvl | HP | Fishing Lvl | Base Weight | Fishing XP | Notable Drops |
|-------------|-----------|-----|------------|-------------|------------|---------------|
| Oasis Rabbit | 10 | 6,000 | 10 | 300 | 350 | Rabbit's Foot (70%), Raw Rabbit |
| Oasis Sheep | 10 | 6,000 | 10 | 700 | 350 | Mutton, Wool |

## Crystal Hollows Sea Creatures (Water)

| Sea Creature | Combat Lvl | HP | Damage | Fishing Lvl | Location | Base Weight | Fishing XP | Notable Drops |
|-------------|-----------|-----|--------|------------|----------|-------------|------------|---------------|
| Water Worm | 20 | 50,000 | 300 | 15 | Goblin Holdout | 300 | 240 | Rough Amber Gemstone, Worm Membrane (15%) |
| Poisoned Water Worm | 25 | 75,000 | 400 | 17 | Goblin Holdout | 300 | 270 | Rough Amber Gemstone, Worm Membrane (20%) |
| Abyssal Miner | 150 | 2,000,000 | 1,300 | 24 | Mithril Deposits/Precursor Remnants/Jungle | 90 | 568 | Rough Gemstones, Flawed Gemstones (20%) |

## Crystal Hollows Sea Creatures (Lava)

| Sea Creature | Combat Lvl | HP | Damage | Fishing Lvl | Location | Base Weight | Fishing XP | Notable Drops |
|-------------|-----------|-----|--------|------------|----------|-------------|------------|---------------|
| Flaming Worm | 50 | 100,000 | 500 | 19 | Precursor Remnants | 180 | 240 | Rough Sapphire, Worm Membrane (25%), Eternal Flame Ring (0.5%) |
| Lava Blaze | 100 | 400,000 | 600 | 20 | Magma Fields | 36 | 548 | Rough Topaz, Magma Core (0.5%), Blazen Sphere (1%) |
| Lava Pigman | 100 | 450,000 | 700 | 22 | Magma Fields | 36 | 568 | Rough Topaz, Magma Core (0.5%) |

## Spooky Sea Creatures (during Spooky Festival)

| Sea Creature | Combat Lvl | HP | Damage | Fishing Lvl | Base Weight | Fishing XP | Notable Drops |
|-------------|-----------|-----|--------|------------|-------------|------------|---------------|
| Scarecrow | 9 | 4,500 | 150 | 9 | 1,000 | 420 | Green Candy, Purple Candy (25%) |
| Nightmare | 24 | 35,000 | 600 | 14 | 550 | 820 | Enchanted Rotten Flesh, Purple Candy (20%), Lucky Hoof (1%) |
| Werewolf | 50 | 50,000 | 250 | 17 | 250 | 1,235 | Purple Candy, Werewolf Skin, Deep Sea Orb (0.1%) |
| Phantom Fisher | 160 | 1,000,000 | 1,000 | 21 | 90 | 2,525 | Purple Candy, Phantom Hook (1%), Deep Sea Orb (1%) |
| Grim Reaper | 190 | 3,000,000 | 2,100 | 26 | 25 | 3,950 | Soul Fragment, Vampire Fang (10%), Bobbin' Scriptures (1.85%), Deep Sea Orb (1%) |

Spooky fishing mobs can be caught whenever the Fear Mongerer is in the hub, not just during the Spooky Festival.

## Winter Sea Creatures (Jerry's Workshop)

| Sea Creature | Combat Lvl | HP | Damage | Fishing Lvl | Base Weight | Fishing XP | Notable Drops |
|-------------|-----------|-----|--------|------------|-------------|------------|---------------|
| Frozen Steve | 7 | 1,500 | 80 | 5 | 1,100 | 101 | Ice, Hunk of Ice, Icy Sinker (4%) |
| Frosty | 13 | 5,000 | 90 | 6 | 800 | 203 | Snow Blocks, Hunk of Ice, Ice Essence |
| Grinch | 21 | 10 (1 dmg/hit) | 1 | 13 | 50 | 405 | White/Green/Red Gifts, Ice Essence |
| Nutcracker | 50 | 4,000,000 | 4,000 | 28 | 60 | 950 | Lily Pad, Enchanted Lily Pad, Red Gifts, Walnuts |
| Yeti | 175 | 2,000,000 | 1,000 | 25 | 30 | 4,050 | Enchanted Packed Ice, Hunk of Blue Ice, Baby Yeti Pet (Epic 3% / Legendary 1.5%), Hilt of True Ice (1.5%), Bobbin' Scriptures (1.8%) |
| Reindrake | 100 | 2,500 (1 hp/hit) | - | 35 | 6 | 0 | White/Green/Red Gifts per hit, Enchanted Book (Prosperity I) |

## Fishing Festival Sea Creatures (Sharks)

| Shark | Combat Lvl | HP | Damage | Fishing Lvl | Base Weight | Fishing XP | Notable Drops |
|-------|-----------|-----|--------|------------|-------------|------------|---------------|
| Nurse Shark | 6 | 2,500 | 80 | 5 | 1,100 | 405 | 2 Shark Fin, Nurse Shark Tooth (10%), Carnival Ticket (0.1%) |
| Blue Shark | 20 | 25,000 | 150 | 10 | 550 | 810 | 4 Shark Fin, Blue Shark Tooth (10%), Carnival Ticket (0.15%) |
| Tiger Shark | 50 | 250,000 | 300 | 18 | 300 | 1,013 | 8 Shark Fin, Tiger Shark Tooth (10%), Epic Megalodon Pet (1%), Carnival Ticket (0.25%) |
| Great White Shark | 180 | 1,500,000 | 750 | 24 | 150 | 2,025 | 16 Shark Fin, Great White Shark Tooth (10%), Legendary Megalodon Pet (1%), Carnival Ticket (0.5%) |

## Crimson Isle Sea Creatures (Lava)

| Sea Creature | Combat Lvl | HP | Damage | Fishing Lvl | Base Weight | Fishing XP | Notable Drops |
|-------------|-----------|-----|--------|------------|-------------|------------|---------------|
| Magma Slug | 200 | 500,000 | 6,000 | 27 | 1,600 | 730 | 5 Magmafish, Lump of Magma, Slug Boots (2%) |
| Moogma | 210 | 750,000 | 7,000 | 28 | 1,200 | 950 | 8 Magmafish, Moogma Pelt, Moogma Leggings (2%) |
| Lava Leech | 220 | 1,000,000 | 8,000 | 30 | 600 | 1,400 | 20 Magmafish, Cup of Blood, Blade of the Volcano (5%), Pitchin' Koi (0.4%) |
| Pyroclastic Worm | 240 | 1,200,000 | 8,000 | 31 | 400 | 1,100 | 10 Magmafish, Pyroclastic Scale, Charm I book (1%) |
| Lava Flame | 230 | 1,000,000 | 9,000 | 33 | 360 | 2,100 | 40 Magmafish, Flaming Heart, Flaming Chestplate (2%) |
| Fire Eel | 240 | 2,000,000 | 9,500 | 34 | 280 | 2,200 | 50 Magmafish, Orb of Energy, Staff of the Volcano (5%) |
| Taurus | 250 | 3,000,000 | 11,000 | 35 | 160 | 4,300 | Silver Magmafish, Horn of Taurus, Taurus Helmet (2%) |
| Thunder | 400 | 35,000,000 | 5,000 | 36 (Novice Trophy Fisher) | 40 | 12,000 | 10 Silver Magmafish, Thunder Shards, Attribute Shard (2%), Flash I book (1.5%) |
| Lord Jawbus | 600 | 100,000,000 | 15,000 | 45 (Adept Trophy Fisher) | 8 | 40,000 | 25 Silver Magmafish, Magma Lord Fragment, Attribute Shard (2%), Bobbin' Scriptures (4%), Radioactive Vial (0.5%) |
| Plhlegblast | 300 | 500,000,000 | 0 | 36 (Plhlegblast Pool) | 0.1% to replace any sea creature | 5,000 | Ink Sac, Enchanted Lily Pad |

## Backwater Bayou Sea Creatures

| Sea Creature | Combat Lvl | HP | Damage | Fishing Lvl | Base Weight | Fishing XP | Notable Drops |
|-------------|-----------|-----|--------|------------|-------------|------------|---------------|
| Trash Gobbler | 8 | 2,000 | 50 | 5 | 750 | 175 | Clay, Can of Worms (20%) |
| Dumpster Diver | 15 | 2,500 | 75 | 5 | 500 | 250 | Clay, Overflowing Trash Can (2%), Bronze Bowl (4.5%) |
| Banshee | 10 | 17,500 | 300 | 10 | 300 | 1,000 | Clay, Enchanted Clay (4.5%), Torn Cloth (4.5%), Calcified Heart (1%) |
| Bayou Sludge | 25 | 20,000 | 200 | 15 | 100 | 1,000 | Slimeball, Poison Sample (1%), Respite I book (1%) |
| Alligator | 120 | 600,000 | 600 | 20 | 50 | 1,250 | Lily Pad, Alligator Skin, Enchanted Rabbit Foot |
| Titanoboa | 240 | 45,000,000 | 6,500 | 30 | 10 | 10,000 | Enchanted Clay, Enchanted Clay Block (0.5%), Titanoboa Shed (0.2%) |

## Galatea Sea Creatures

| Sea Creature | Combat Lvl | HP | Damage | Fishing Lvl | Base Weight | Fishing XP | Notable Drops |
|-------------|-----------|-----|--------|------------|-------------|------------|---------------|
| Bogged | 10 | 3,000 | 100 | 5 | 5,000 | 225 (Combat) | Sea Lumies, Mangrove Log |
| Wetwing | 18 | 8,000 | 300 | 7 | 2,875 | 650 | Sea Lumies, Mangrove Log, Wet Water (2.5%) |
| Tadgang | 8 | 5,000 | 100 | 9 | 1,500 | 150 (Combat) | Sea Lumies, Mangrove Log, Gill Membrane (20%) |
| Ent | 14 | 25,000 | 275 | 12 | 500 | 270 (Combat) | Sea Lumies, Enchanted Mangrove Log, Mangcore (0.5%) |
| The Loch Emperor | 150 | 800,000 | 100 | 20 | 100 | 3,375 | Sea Lumies, Emperor's Skull, Flying Fish Pet (Rare 4%, Epic 2%, Legendary 0.5%), Mangcore (1%), Shredded Line (2%) |

---

# Trophy Fishing

Trophy Fish are a type of fishing loot caught while lava fishing in the Crimson Isle. They can be filleted by the NPC Odger for Magmafish. Collecting Trophy Fish increases the player's Trophy Fishing level, unlocking rewards and access to stronger lava Sea Creatures.

## Trophy Fish Tiers

Each Trophy Fish has four tiers:
- Bronze: 100% (guaranteed if no higher tier rolls)
- Silver: 25% chance (27.5% with Charm V)
- Gold: 2% chance (2.2% with Charm V)
- Diamond: 0.2% chance (0.22% with Charm V)

Overall actual tier distribution:
- Bronze: 73.353% (70.749% with Charm V)
- Silver: 24.451% (26.836% with Charm V)
- Gold: 1.996% (2.195% with Charm V)
- Diamond: 0.2% (0.22% with Charm V)

### Pity System
- 100th catch of a unique fish: guaranteed Gold (if not already caught Gold)
- 600th catch of a unique fish: guaranteed Diamond (if not already caught Diamond)

### Tier Bonuses
- Midas Lure Perk: +2-20% increase in catching Gold Trophy Fish
- Radiant Fisher Perk: +2-20% increase in catching Diamond Trophy Fish
- Gold Trophy Fish yield 15 Bits (affected by Bits Multiplier)
- Diamond Trophy Fish yield 30 Bits (affected by Bits Multiplier)

## Trophy Fish Chance (TFC) Stat

The Trophy Fish Chance stat increases the probability of catching any Trophy Fish. Sources include: Hunter Armor sets, Odger's Tooth accessories, and various other items.

## List of Trophy Fish

| Trophy Fish | Rarity | Requirement | Catch Chance |
|------------|--------|-------------|-------------|
| Blobfish | Common | No requirement | 25% |
| Sulphur Skitter | Common | Within 4 blocks of Sulphur Ore | 30% |
| Steaming-Hot Flounder | Common | Bobber within 2 blocks of a Geyser (Blazing Volcano) | 20% |
| Gusher | Common | 7-16 minutes after a Volcano eruption | 20% |
| Obfuscated-1 | Common | Caught with Corrupted Bait (also drops from corrupted Sea Creatures) | 25% |
| Slugfish | Uncommon | At least 20 seconds between cast and reel (10 sec with Slug Pet) | 15% |
| Flyfish | Uncommon | Bobber in Blazing Volcano, at least 8 blocks below player | 8% |
| Obfuscated-2 | Uncommon | Caught using Obfuscated-1 as bait | 20% |
| Lavahorse | Rare | No requirement | 4% |
| Mana Ray | Rare | Player must have at least 1,200 Mana | Mana / 1000 (e.g., 1.2% at 1,200 Mana) |
| Vanille | Rare | Must use a Starter Lava Rod with no enchantments (Rod Parts, Reforges, Gemstones, Wet Books allowed) | 8% |
| Volcanic Stonefish | Rare | Bobber in Blazing Volcano | 3% |
| Obfuscated-3 | Rare | Caught using Obfuscated-2 as bait | 10% |
| Karate Fish | Epic | Bobber in the Dojo | 2% |
| Moldfin | Epic | Bobber in Mystic Marsh or Scarleton | 2% |
| Skeleton Fish | Epic | Bobber in Burning Desert or Dragontail | 2% |
| Soul Fish | Epic | Bobber in the Stronghold | 2% |
| Golden Fish | Legendary | Appears after 8-12 minutes of fishing. Must hook it, wait for "looks weakened" message, hook repeatedly until "is weak!" message, then reel in. Timer resets after catch. | Special (scales linearly from 0% at 8 min to 100% at 12 min) |

## Trophy Fisher Ranks

| Rank | Requirement |
|------|------------|
| Novice Trophy Fisher | Catch 15 Bronze (or above) tier Trophy Fish |
| Adept Trophy Fisher | Catch Silver (or above) of all Trophy Fish |
| Expert Trophy Fisher | Catch Gold (or above) of all Trophy Fish |
| Master Trophy Fisher | Catch all tiers (including Diamond) of all Trophy Fish |

## Filleting

Trophy Fish can be filleted by Odger NPC to convert them into Magmafish, which are used in collections for lava fishing rod upgrades.

---

# Fishing Festival

The Fishing Festival is an event that occurs when Marina is elected as Mayor with the Fishing Festival perk. A Bonus Fishing Festival also occurs when Foxy is elected with the Extra Event perk, or when Mayor Jerry's Perkpocalypse rotates to Marina's perks.

## Timing

- Occurs 12 times during Marina's term, starting on the 1st of each SkyBlock month from Early Summer Year onward
- Each event lasts 3 SkyBlock days = 1 real-life hour
- Interval between festivals: 28 SkyBlock days = 9 hours 20 minutes real time
- Foxy's Bonus Fishing Festival: 22nd-24th of Late Summer
- Event starts at 6AM in-game time (XX:30 UTC)

## Shark Types

| Shark | Fishing Level | HP | Drops |
|-------|-------------|-----|-------|
| Nurse Shark | 5 | 2,500 | 2-4 Shark Fin, Nurse Shark Tooth (rare), Carnival Ticket (0.1%) |
| Blue Shark | 10 | 25,000 | 4-8 Shark Fin, Blue Shark Tooth (rare), Carnival Ticket (0.15%) |
| Tiger Shark | 18 | 250,000 | 8-16 Shark Fin, Tiger Shark Tooth (rare), Epic Megalodon Pet (rare), Carnival Ticket (0.25%) |
| Great White Shark | 24 | 1,500,000 | 16-32 Shark Fin, Great White Shark Tooth (rare), Legendary Megalodon Pet (rare), Carnival Ticket (0.5%) |

## Event Items

| Item | Use |
|------|-----|
| Shark Fin (Rare) | Crafting: Raggedy Shark Tooth Necklace, Shark Bait, Enchanted Shark Fin |
| Shark Bait (Uncommon) | +20% chance to catch Sharks |
| Nurse Shark Tooth (Uncommon) | Crafting Raggedy/Dull Shark Tooth Necklaces |
| Blue Shark Tooth (Rare) | Crafting Honed Shark Tooth Necklace |
| Tiger Shark Tooth (Epic) | Crafting Sharp Shark Tooth Necklace |
| Great White Shark Tooth (Legendary) | Crafting Razor-sharp Shark Tooth Necklace, Rod of the Sea, Great White Tooth Meal |
| Megalodon Pet (Epic/Legendary) | Fishing pet from Tiger/Great White Shark |
| Shark Scale Armor (Legendary) | Crafted from Enchanted Shark Fin + Sponge Armor |
| Rod of the Sea (Legendary) | Best water fishing rod; crafted from Rod of Legends + Great White Shark Teeth |

## Shark Tooth Necklaces

| Necklace | Rarity | Strength | Shark Tooth Drop Chance |
|----------|--------|----------|----------------------|
| Raggedy Shark Tooth Necklace | Common | +2 | +5% |
| Dull Shark Tooth Necklace | Uncommon | +4 | +10% |
| Honed Shark Tooth Necklace | Rare | +6 | +15% |
| Sharp Shark Tooth Necklace | Epic | +8 | +20% |
| Razor-sharp Shark Tooth Necklace | Legendary | +10 | +25% |

---

# Fishing Locations

## Key Fishing Spots

| Location | Zone | Unique Features |
|----------|------|----------------|
| Fairy Pond (Wilderness) | Hub | Fairy Armor drops (25% of location pool) |
| Fishing Outpost | Hub | Higher Clay Ball drop rate |
| Mountain Lake | Hub | Carnival appears here during Foxy's Chivalrous Carnival perk |
| Oasis | Mushroom Desert | Oasis Sheep, Oasis Rabbit sea creatures |
| The Park | Hub | Can buy rain from Vanessa (5k/min) for Squid spawns and Night Squids without Dark Bait |
| Jerry Pond | Jerry's Workshop | Winter Sea Creatures (Late Winter only). Baby Yeti Pet, Hunk of Blue Ice drops |
| Treasure Hoarder's Cave | Dwarven Mines / Upper Mines | Treasurite drops |
| Magma Fields | Crystal Hollows | Flaming Worm, Lava Blaze, Lava Pigman (lava fishing) |
| Goblin Holdout | Crystal Hollows | Water Worm, Poisoned Water Worm |
| Mithril Deposits / Precursor Remnants / Jungle | Crystal Hollows | Abyssal Miner |
| Fairy Grotto | Crystal Hollows | Fishing Fairy Souls |
| Crimson Isle | Crimson Isle | All lava sea creatures, Trophy Fish |
| Backwater Bayou | Backwater Bayou | Junk fishing, unique sea creatures (Trash Gobbler through Titanoboa) |
| Galatea | Galatea | Mangrove-themed sea creatures, Loch Emperor, Flying Fish Pet drops |
| Private Island | Private Island | Prismarine drops with Fishing Crystal; lower SCC; no fishing XP from sea creatures |

## Lava Fishing

Lava fishing is done in Lava sources (primarily Crystal Hollows and Crimson Isle). Lava fishing has:
- Separate coin treasure formula (MaxCoins multiplier is 5 instead of 2.5)
- Different drop tables
- Access to Trophy Fish (Crimson Isle only)
- Unique sea creatures requiring lava fishing rods

---

# Fishing Progression Guide

## Rod Progression (Water)

| Fishing Level | Recommended Rod |
|--------------|----------------|
| 0-4 | Prismarine Rod |
| 5-9 | Chum Rod |
| 10-14 | Challenging Rod |
| 15-19 | Rod of Champions |
| 20-23 | Rod of Legends |
| 24-50 | Rod of the Sea |

## Rod Progression (Lava)

| Fishing Level | Recommended Rod |
|--------------|----------------|
| 27-29 | Magma Rod |
| 30-34 | Inferno Rod |
| 35-50 | Hellfire Rod |

## Armor Progression

| Fishing Level | Recommended Armor |
|--------------|-------------------|
| 0-12 | 3/4 Angler Armor + Water Hydra Head |
| 13-16 | 3/4 Salmon Armor + Water Hydra Head |
| 17-19 | Sponge Armor |
| 20-23 | Diver's Armor |
| 24-26 | Shark Scale Armor |
| 27 | 3/4 Shark Scale Armor + Slug Boots |
| 28-32 | 2/4 Shark Scale Armor + Moogma Leggings + Slug Boots |
| 33-34 | Shark Scale Helmet + Flaming Chestplate + Moogma Leggings + Slug Boots |
| 35 | Lava Sea Creature Armor |
| 36-44 | Thunder Armor |
| 45-50 | Magma Lord Armor |

## General Tips

- Maximize Fishing Speed and SCC at all times
- For XP fishing: prioritize Fishing Wisdom
- For valuable drops: prioritize Magic Find
- Best bait overall: Whale Bait (if too expensive, use Glowy Chum Bait or Fish Bait)
- Daytime: 6:00 AM - 7:00 PM; Nighttime: 7:00 PM - 6:00 AM (indicated by sun/moon in sidebar)
- XP from Sea Creatures based on Zombies (Sea Walker, Monster of the Deep, Water Hydra) counts for Zombie Slayer
- Lava Flames count for Blaze Slayer
- Fishing Crystal on Private Island grants more frequent Prismarine drops
- Buy rain at The Park from Vanessa for faster fishing and Squid/Night Squid spawning

---

# Notable Fishing Drops and Their Value

## High-Value Drops

| Item | Source | Drop Rate | Notes |
|------|--------|-----------|-------|
| Baby Yeti Pet | Yeti (Jerry's Workshop) | Epic 3%, Legendary 1.5% | Very valuable pet |
| Megalodon Pet | Tiger/Great White Shark | Epic 1%, Legendary 1% | Fishing Festival exclusive |
| Flying Fish Pet | The Loch Emperor (Galatea) | Rare 4%, Epic 2%, Legendary 0.5% | Excellent fishing pet |
| Radioactive Vial | Lord Jawbus | 0.5% | Extremely rare, used for Hyperion upgrade |
| Water Hydra Head | Water Hydra | 14% | +1.8% SCC accessory |
| Hilt of True Ice | Yeti | 1.5% | Dungeon sword material |
| Bobbin' Scriptures | Grim Reaper / Yeti / Lord Jawbus | 1.85% / 1.8% / 4% | Fishing enchantment book |
| Deep Sea Orb | Spooky Sea Creatures | 0.1-1% | Rare drop |
| Titanoboa Shed | Titanoboa (Backwater Bayou) | 0.2% | Very rare drop |
| Attribute Shard | Thunder / Lord Jawbus | 2% | Used for attribute upgrades |
| Magma Lord Fragment | Lord Jawbus | Common drop | Used for Magma Lord Armor |
| Thunder Shards | Thunder | Common drop | Used for Thunder Armor |
| Lucky Clover Core | Carrot King | 0.66% | Accessory crafting material |
| Eternal Flame Ring | Flaming Worm / Lava Blaze | 0.5% | Accessory |
| Slug Boots | Magma Slug | 2% | Lava fishing armor piece |
| Moogma Leggings | Moogma | 2% | Lava fishing armor piece |
| Flaming Chestplate | Lava Flame | 2% | Lava fishing armor piece |
| Taurus Helmet | Taurus | 2% | Lava fishing armor piece |
