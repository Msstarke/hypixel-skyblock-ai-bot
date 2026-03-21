# Minions

Minions are NPCs that produce items while placed on a player's Private Island. Each minion generates and harvests resources within a 5x5 area. Players start with 5 minion slots and a Tier I Cobblestone Minion. Minions cannot be traded on the Auction House but can be traded player-to-player.

## Minion Mechanics

### How Minions Work
- Minions perform an action every X seconds (Time Between Actions / action time / minion speed)
- Resources are generated every OTHER action. So if a minion has a 14s action time, it produces 1 item every 28 seconds, not 14 seconds
- Minions work 24/7, even while the player is offline
- Minions operate in a 5x5 area centered on them (expandable with Minion Expander)
- All co-op members can interact with all minions on the island

### Minion Speed Calculation
Speed boosts are additive. The formula is:
**Effective Time = Base Time / (1 + Total Speed Boost %)**

Example: T11 Clay Minion (16s base) with Enchanted Lava Bucket (+25%) = 16 / 1.25 = 12.8 seconds

### Minion Interface Slots
- **Skin Slot (x1)** - Cosmetic only, no performance effect
- **Fuel Slot (x1)** - Increases minion production speed
- **Automated Shipping Slot (x1)** - Auto-sells items when storage is full
- **Upgrade Slots (x2)** - Various upgrades that modify speed, output, or behavior

## Minion Tiers and Storage

All minions can be crafted from Tier I to Tier XI (11). Many minions also have Tier XII available through special NPCs or upgrade stones. Higher tiers have faster action times and more storage.

### Storage Capacity by Tier
Most minions follow this storage pattern:
| Tier | Storage Slots |
|------|--------------|
| I | 64 (1 row) |
| II | 128 |
| III | 192 |
| IV | 256 |
| V | 320 |
| VI | 384 |
| VII | 448 |
| VIII | 512 |
| IX | 576 |
| X | 640 |
| XI | 960 (15 rows) |
| XII | 960 |

Exceptions: Fishing Minion starts at 640, Chicken/Rabbit start at 192, Cow/Sheep/Gravel/Wheat start at 128, Flower Minion always has 960 at all tiers.

### External Storage (Minion Chests)
Place chests adjacent to minions (not above) for extra storage:
| Chest | Extra Slots | Collection |
|-------|------------|------------|
| Small Storage | 3 | Oak Log IV |
| Medium Storage | 9 | Oak Log VI |
| Large Storage | 15 | Oak Log IX |
| X-Large Storage | 21 | 1,500 Bits |
| XX-Large Storage | 27 | 3,000 Bits total |

## Minion Fuel (Speed Boosts)

Fuel is placed in the fuel slot to increase minion speed. Some fuels have limited duration, others are infinite.

### Fuel Ranked by Cost-Efficiency (Best to Worst for Long-Term Use)

#### Infinite Fuels (Best Long-Term Value)
| Fuel | Speed Boost | Approx Cost | Notes |
|------|------------|-------------|-------|
| Everburning Flame | +40% | ~9.3M coins | Best infinite fuel, requires 4 Inferno Fuel components |
| Plasma Bucket | +35% | ~9.3M coins | Second best infinite fuel |
| Magma Bucket | +30% | ~3.1M coins | Good mid-range infinite option |
| Enchanted Lava Bucket | +25% | ~78K coins | BEST budget infinite fuel, extremely popular |
| Solar Panel | +25% | ~172K coins | Same boost as E. Lava Bucket but ONLY works during daytime |

#### Limited Duration Fuels
| Fuel | Boost | Duration | Cost/Day | Notes |
|------|-------|----------|----------|-------|
| Foul Flesh | +90% | 5 hours | ~124K/day | Highest % boost but very expensive per day |
| Hamster Wheel | +50% | 1 day | ~22K/day | Great boost, reasonable daily cost |
| Enchanted Charcoal | +20% | 1.5 days | ~2.3K/day | Cheap option |
| Enchanted Coal | +10% | 1 day | ~1.5K/day | Budget option |
| Enchanted Bread | +5% | 12 hours | ~1.8K/day | Not recommended |
| Block of Coal | +5% | 5 hours | ~428/day | Cheapest but weakest |
| Coal | +5% | 30 min | ~475/day | Not worth the hassle |

#### Multiplier Fuels (Special)
| Fuel | Multiplier | Duration | Cost/Day | Notes |
|------|-----------|----------|----------|-------|
| Hyper Catalyst | x4 | 6 hours | ~710K/day | Best multiplier fuel for cost |
| Catalyst | x3 | 3 hours | ~953K/day | Expensive per day |
| Tasty Cheese | x2 | 1 hour | ~282K/day | Very expensive, not recommended |

#### Inferno Minion Fuels (Inferno Minion Only)
| Fuel | Multiplier | Duration | Notes |
|------|-----------|----------|-------|
| RARE Inferno Fuel | x10 | 1 day | Replaces 4/5 output with specialty items |
| EPIC Inferno Fuel | x15 | 1 day | Replaces 4/5 output with specialty items |
| LEGENDARY Inferno Fuel | x20 | 1 day | Enables Chili Pepper, Inferno Vertex, Inferno Apex, Reaper Pepper drops |

### Best Fuel Recommendation
- **For most players**: Enchanted Lava Bucket (+25%, infinite, ~78K coins) is the best value
- **For maximum speed on a budget**: Hamster Wheel (+50%, 22K/day) if you check daily
- **For endgame**: Plasma Bucket (+35%) or Everburning Flame (+40%) if you can afford it
- **Never use**: Coal, Block of Coal, Enchanted Bread, or Tasty Cheese - terrible value

## Minion Upgrades

### Speed Upgrades
| Upgrade | Effect | Source |
|---------|--------|--------|
| Minion Expander | +5% speed, +1 block range (7x7). Stacks with 2nd copy for 9x9 | Quartz V |
| Flycatcher | +20% speed | Spider Slayer LVL 6 |
| Mithril Infusion | +10% speed permanently (applied via anvil, does not use upgrade slot) | Mithril VIII |

### Resource Upgrades
| Upgrade | Effect | Source |
|---------|--------|--------|
| Diamond Spreading | Occasionally generates a Diamond alongside normal resources. Does NOT slow the minion | Diamond VI |
| Potato Spreading | Occasionally generates a Potato. One per profile | Shiny Pig rare drop |
| Corrupt Soil | Makes mob minions spawn Corrupted Mobs (more drops) | Mycelium VI |
| Lesser Soulflow Engine | -50% output but generates Soulflow | Enderman Slayer 2 |
| Soulflow Engine | -50% output but generates Soulflow. +3% speed per tier on Voidling Minion | Enderman Slayer 5 |
| Enchanted Egg | Guarantees egg drops from Chicken Minion | Raw Chicken V |
| Flint Shovel | Guarantees flint from Gravel Minion | Gravel II |
| Krampus Helmet | Occasionally generates Red Gifts (one per profile, best with Snow Minion) | Red Gift drops |
| Sleepy Hollow | Occasionally generates Purple Candy (one per profile) | Vargul the Unearthed |

### Processing Upgrades
| Upgrade | Effect | Source |
|---------|--------|--------|
| Super Compactor 3000 | Compacts items to enchanted forms automatically | Cobblestone X |
| Dwarven Super Compactor | Auto-smelts AND compacts to enchanted forms (combines Auto Smelter + Super Compactor) | Mithril VI |
| Auto Smelter | Smelts items (ore to ingot, etc.) | Cobblestone III |
| Compactor | Compacts items to block forms (9x item to block) | Cobblestone V |

### Automated Shipping
| Item | Effect | Source |
|------|--------|--------|
| Budget Hopper | Sells items at 50% NPC price when full | Iron Ingot V |
| Enchanted Hopper | Sells items at 90% NPC price when full | Iron Ingot IX |

### Best Upgrade Combinations
1. **Super Compactor 3000 + Diamond Spreading** - The most popular combo for almost all minions. Super Compactor makes items worth more (enchanted forms sell higher on Bazaar), Diamond Spreading adds free diamonds worth ~8 coins each to NPC or more on Bazaar
2. **Super Compactor 3000 + Enchanted Hopper** - For AFK money setups where you don't want to manually collect
3. **Super Compactor 3000 + Corrupt Soil** - For combat/mob minions, triples drop value
4. **Minion Expander + Minion Expander** - Double expanders for 9x9 range, good for farming minions
5. **Flycatcher + Diamond Spreading** - If you can't afford Super Compactor yet
6. **Super Compactor 3000 + Flycatcher** - Maximum speed when Diamond Spreading profit is negligible

## All Minion Types

### Combat Minions
| Minion | Action Time (T1 to T11/T12) | Items | Notes |
|--------|---------------------------|-------|-------|
| Blaze | 33s to 15s | Blaze Rod | Max T12 |
| Cave Spider | 26s to 13s | String, Spider Eye | Max T11 |
| Creeper | 27s to 14s | Gunpowder | Max T11 |
| Enderman | 32s to 18s | Ender Pearl | Max T11 |
| Ghast | 50s to 30s | Ghast Tear | Max T12 |
| Magma Cube | 32s to 16s | Magma Cream | Max T12 |
| Skeleton | 26s to 13s | Bone | Max T11 |
| Slime | 26s to 12s | Slimeball | Max T11, Corrupt Soil triples profit |
| Spider | 26s to 13s | String, Spider Eye | Max T11 |
| Vampire | 190s to 95s | Hemovibe | Max T11, spawns Scions, slowest combat minion |
| Zombie | 26s to 13s | Rotten Flesh, Poisonous Potato, Carrot, Potato | Max T11 |

### Farming Minions
| Minion | Action Time (T1 to T11/T12) | Items | Notes |
|--------|---------------------------|-------|-------|
| Cactus | 27s to 12s | Cactus | Max T12 |
| Carrot | 20s to 8s | Carrot | Max T12, very fast |
| Chicken | 26s to 12s | Raw Chicken, Feather, Egg (with Enchanted Egg) | Max T12 |
| Cocoa Beans | 27s to 12s | Cocoa Beans | Max T12 |
| Cow | 26s to 10s | Raw Beef, Leather | Max T12 |
| Melon | 24s to 10s | Melon Slice (3-7 per action) | Max T12 |
| Mushroom | 30s to 12s | Red/Brown Mushroom | Max T12 |
| Nether Wart | 50s to 27s | Nether Wart | Max T12, slow |
| Pig | 26s to 10s | Raw Porkchop | Max T12 |
| Potato | 20s to 8s | Potato | Max T12, very fast |
| Pumpkin | 32s to 12s | Pumpkin | Max T12 |
| Rabbit | 26s to 10s | Raw Rabbit, Rabbit's Foot, Rabbit Hide | Max T12 |
| Sheep | 24s to 9s | Raw Mutton, White Wool | Max T12 |
| Sugar Cane | 22s to 9s | Sugar Cane | Max T12 |
| Wheat | 15s to 7s | Wheat, Seeds | Max T12, fastest farming minion |

### Mining Minions
| Minion | Action Time (T1 to T11/T12) | Items | Notes |
|--------|---------------------------|-------|-------|
| Coal | 15s to 6s | Coal | Max T12, very fast |
| Cobblestone | 14s to 6s | Cobblestone | Max T12, fastest mining minion |
| Diamond | 29s to 12s | Diamond | Max T12 |
| Emerald | 28s to 12s | Emerald | Max T12 |
| End Stone | 26s to 13s | End Stone | Max T11 |
| Glowstone | 25s to 11s | Glowstone Dust | Max T12 |
| Gold | 22s to 9s | Gold Ore (needs Auto Smelter for ingots) | Max T12 |
| Gravel | 26s to 13s | Gravel (Flint with Flint Shovel) | Max T11 |
| Hard Stone | 14s to 6s | Hard Stone | Max T12, same speed as Cobblestone |
| Ice | 14s to 6s | Ice | Max T12, very fast, great for money |
| Iron | 17s to 7s | Iron Ore (needs Auto Smelter for ingots) | Max T12 |
| Lapis | 29s to 16s | Lapis Lazuli (4-8 per action) | Max T12 |
| Mithril | 80s to 50s | Mithril | Max T12, SLOWEST normal minion |
| Mycelium | 26s to 11s | Mycelium | Max T12 |
| Obsidian | 45s to 21s | Obsidian | Max T12 |
| Quartz | 22.5s to 10s | Nether Quartz | Max T12 |
| Red Sand | 26s to 11s | Red Sand | Max T12 |
| Redstone | 29s to 16s | Redstone Dust | Max T12 |
| Sand | 26s to 13s | Sand | Max T11 |
| Snow | 13s to 5.8s | Snowball (4 per action) | Max T12, obtained from Gifts only |

### Fishing Minion
| Minion | Action Time (T1 to T11/T12) | Items | Notes |
|--------|---------------------------|-------|-------|
| Fishing | 75s to 30s | Raw Cod, Raw Salmon, Pufferfish, Tropical Fish, Prismarine | Max T12, slow but many item types |
| Clay | 32s to 14s | Clay Ball (4 per action) | Max T12, technically Fishing category |

### Foraging Minions
| Minion | Action Time (T1 to T11/T12) | Items | Notes |
|--------|---------------------------|-------|-------|
| Acacia | 48s to 27s | Acacia Log | Max T11 |
| Birch | 48s to 27s | Birch Log | Max T11 |
| Dark Oak | 48s to 27s | Dark Oak Log | Max T11 |
| Jungle | 48s to 27s | Jungle Log | Max T11 |
| Oak | 48s to 27s | Oak Log | Max T11 |
| Spruce | 48s to 27s | Spruce Log | Max T11 |
| Flower | 30s to 15s | Various Flowers (14 types) | Max T12, obtained from Dark Auction (~2.5M+), all storage unlocked at T1 |

### Slayer Minions
| Minion | Action Time (T1 to T11/T12) | Items | Notes |
|--------|---------------------------|-------|-------|
| Revenant | 29s to 8s | Rotten Flesh, Diamond | Zombie Slayer V, Max T12, very fast at high tiers |
| Tarantula | 29s to 10s | String, Spider Eye, Iron Ingot | Spider Slayer V, Max T11 |
| Voidling | 45s to 24s | Nether Quartz, Obsidian, Enchanted Ender Pearl (rare) | Enderman Slayer IV, Max T11 |
| Inferno | 1013s to 697s | Crude Gabagool (base), special items with fuel | Blaze Slayer III, Max T11, SLOWEST minion in game |

## Inferno Minion Details

The Inferno Minion is the slowest minion in the game with base action times from 1013s (T1) to 697s (T11). It has unique mechanics:

- **Speed Stacking**: Each placed Inferno Minion boosts ALL Inferno Minions by +18% speed (additive). With 10 Inferno Minions, all get +180% speed (1.9x faster)
- **Without Fuel**: Produces only Crude Gabagool (low value)
- **With Inferno Fuel**: Uses special Inferno Minion Fuel crafted from 6 Distillates + 2 Inferno Fuel Blocks + 1 Gabagool
- **Distillate Types**: Gabagool, Blaze Rod, Magma Cream, Glow Stone, Nether Wart - each produces different specialty items
- **LEGENDARY Fuel Only**: Enables drops of Chili Pepper, Inferno Vertex, Inferno Apex, Reaper Pepper, and Gabagool The Fish
- **Expected Output**: Approximately a couple Inferno Vertices per day with maxed setup (all 10 minions + LEGENDARY fuel)
- **Cost**: Very expensive to run. LEGENDARY Inferno Fuel costs ~3.7M + distillate costs PER minion PER day

## Top Money-Making Minions (Coins Per Day Estimates)

Profit varies with Bazaar prices. These are approximate values for T11 minions with Enchanted Lava Bucket + Super Compactor 3000 + Diamond Spreading.

### Best Budget Money Minions (Cheap to Set Up)
1. **Snow Minion T11** - ~50-70K coins/day. Very cheap to upgrade (~150K for T1 to T11). Sells Snow Blocks/Enchanted Snow Blocks to NPC. Best beginner money minion
2. **Clay Minion T11** - ~50-70K coins/day. Sells Enchanted Clay to NPC. Very consistent earner
3. **Ice Minion T11** - ~40-60K coins/day. Fast action time (6s), sells Enchanted Ice well
4. **Cobblestone Minion T11** - ~20-30K coins/day. Fastest mining minion but low item value

### Best Mid-Game Money Minions
5. **Revenant Minion T11** - ~60-100K coins/day. Produces Diamonds + Rotten Flesh. Very fast (8s action time at T11)
6. **Tarantula Minion T11** - ~50-80K coins/day. Produces String + Spider Eye + Iron
7. **Slime Minion T11 + Corrupt Soil** - ~60-90K coins/day. Corrupt Soil greatly increases output
8. **Melon Minion T11** - ~30-50K coins/day. Produces 3-7 Melon Slices per action

### Best Endgame Money Minions
9. **Inferno Minion** (10x setup with LEGENDARY fuel) - Potentially millions/day but costs millions to fuel daily
10. **Voidling Minion T11** - Good for Ender Pearl/Obsidian collection, decent money with Soulflow Engine

### Without Diamond Spreading (Save Upgrade Slot)
Profit drops by roughly 5-15K coins/day for most minions. Diamond Spreading is almost always worth using.

### Without Super Compactor
Profit drops significantly (often 30-50% less) because raw items sell for much less than enchanted forms. However, some items (Glowstone Dust, Lapis) actually lose value when compacted - check Bazaar prices.

### NPC vs Bazaar Selling
- **NPC Selling** (with Enchanted Hopper): More consistent, no price fluctuations. Best for Snow, Clay, and items with good NPC prices
- **Bazaar Selling** (manual): Usually more profitable but prices change. Best for most enchanted items

## Minion Crystals (Area Speed Buffs)

Place these near minions for a speed boost in a radius:
| Crystal | Affects | Boost | Radius | Source |
|---------|---------|-------|--------|--------|
| Farm Crystal | Farming minions (crop-based, not mob) | +10% | - | Pumpkin VIII |
| Woodcutting Crystal | Foraging minions | +10% | 12 | Spruce Log VII |
| Mithril Crystal | Mining minions | +10% | 40 | Mithril IV |
| Winter Crystal | Snow Minion only | +5% | 16 | Red Gifts |

## Beacons (Island-Wide Speed Buffs)

| Beacon | Speed Boost | Radius |
|--------|------------|--------|
| Beacon I | +2% | 120 |
| Beacon II | +4% | 125 |
| Beacon III | +6% | 130 |
| Beacon IV | +8% | 135 |
| Beacon V | +10% | 140 |

Beacons require Scorched Power Crystals (from Inferno Demonlord) to power for 48 hours (+1% each).

## Minion Speed Pets

Certain pets at Level 100 give +30% speed to specific minions:
| Pet | Affected Minions |
|-----|-----------------|
| Rabbit Pet | Farming minions |
| Ocelot Pet | Foraging minions + Flower Minion |
| Magma Cube Pet | Slime + Magma Cube Minions |
| Mooshroom Cow Pet | Mushroom + Mycelium Minions |
| Snail Pet | Red Sand Minions |
| Chicken Pet | Chicken Minions |
| Pigman Pet | Pig Minions |
| Spider Pet | Spider, Cave Spider, Tarantula Minions |

## Minion Slot Unlocking

You start with 5 minion slots. Craft unique minions (new types OR higher tiers of existing ones) to unlock more slots.

| Slots | Unique Minion Crafts Needed |
|-------|---------------------------|
| 5 | 0 (starting) |
| 6 | 5 |
| 7 | 15 |
| 8 | 30 |
| 9 | 50 |
| 10 | 75 |
| 11 | 100 |
| 12 | 125 |
| 13 | 150 |
| 14 | 175 |
| 15 | 200 |
| 16 | 225 |
| 17 | 250 |
| 18 | 275 |
| 19 | 300 |
| 20 | 350 |
| 21 | 400 |
| 22 | 450 |
| 23 | 500 |
| 24 | 550 |
| 25 | 600 |
| 26 | 650 |

**+5 additional slots** from Community Shop upgrades. **Maximum: 31 minion slots.**

### Tips for Unlocking Slots Cheaply
- Craft every minion type at T1 first (cheapest unique crafts)
- Then upgrade the cheapest minions to higher tiers (Cobblestone, Coal, Wheat, etc.)
- Each tier of each minion type counts as one unique craft
- Crafting new unique minions gives SkyBlock XP
- Total unique minions possible: 50+ types x 11-12 tiers each = 550+ possible unique crafts

## Best Minions by Purpose

### Best Minions for Money (Overall)
1. Snow Minion T11 (budget king, ~60K/day, cheap setup)
2. Clay Minion T11 (consistent NPC money)
3. Revenant Minion T11 (fastest slayer minion)
4. Inferno Minion (endgame, expensive to run)
5. Ice Minion T11 (fast, decent money)

### Best Minions for Collection
- Use the minion matching the collection you need
- Fastest minions for collection: Cobblestone (6s), Coal (6s), Ice (6s), Hard Stone (6s), Wheat (7s), Iron (7s)
- Slow but necessary: Mithril (50s), Obsidian (21s), Nether Wart (27s), Ghast (30s)

### Best Minions for XP
- Combat XP: Any mob-spawning minion (Zombie, Skeleton, Spider, etc.) - must be nearby to collect XP
- Mining XP: Cobblestone, Coal, Diamond minions
- Farming XP: Wheat, Carrot, Potato (fastest action times)

### Best Minions for Specific Items
- **Diamonds**: Diamond Minion or Revenant Minion (drops diamonds too)
- **Enchanted Ender Pearls**: Voidling Minion or Enderman Minion
- **Soulflow**: Any minion with Soulflow Engine (best with fast minions like Snow/Ice)
- **Red Gifts**: Snow Minion with Krampus Helmet (fastest action time = most gifts)
- **Blaze Rods**: Blaze Minion
- **String**: Tarantula Minion or Spider Minion
- **Inferno Vertex / Chili Pepper / Reaper Pepper**: Inferno Minion with LEGENDARY fuel only

## Mob Spawning Minion Mechanics

Combat and slayer minions spawn mobs instead of mining blocks:
- Mobs spawn in a 5x5 area (expandable with Minion Expander)
- Vertical range: 6 blocks (3 below, 2 above, 1 at eye level)
- Need clear spawning space with solid blocks below
- Mobs wider than 1 block (Slimes, Ghasts) may spawn partially in walls
- If a mob wanders outside the minion's range, it will NOT be killed automatically
- Use proper platform layouts for mob minions to maximize efficiency

## Tier XII Upgrade Sources

Different minion categories get T12 from different places:
- **Mining Minions T12**: Bulvar at Dwarven Mines entrance (resources + coins)
- **Farming Minions T12**: Tony's Shop in Trapper's Den
- **Revenant Minion T12**: Upgrade Stone from the Bartender (Zombie Slayer IX required)
- **Tarantula Minion T12**: Upgrade Stone from the Bartender
- **Flower Minion T12**: Museum Milestone 10
- **Snow/Ice Minion T12**: Einary
- **Fishing/Clay Minion T12**: Upgrade Stone from Lukas the Aquarist

## Quick Recommendation Guide

### Early Game (First Island Setup)
- Use whatever minions you can craft
- Get at least T5 Snow or Clay Minions for passive income
- Use Enchanted Lava Bucket for fuel (78K, infinite, +25%)
- Use Super Compactor 3000 + Diamond Spreading as upgrades
- Focus on unlocking more minion slots by crafting unique minions

### Mid Game
- Max out Snow/Clay/Ice Minions to T11
- Fill all slots with money-making minions
- Consider Revenant/Tarantula minions if you have slayer levels
- Use Large Storage or better on all minions
- Collect from minions every 1-2 days

### Late Game / Endgame
- Consider Inferno Minions with LEGENDARY fuel for maximum profit
- Use Plasma Bucket or Everburning Flame for fuel
- Beacon V for +10% island-wide speed buff
- Appropriate pet for +30% speed on your minion type
- Mithril Infusion on all minions for permanent +10%

### Optimal Money Setup (Per Minion)
- Minion: Snow T11 or Clay T11 (budget) / Revenant T11 (mid) / Inferno T11 (endgame)
- Fuel: Enchanted Lava Bucket (budget) / Plasma Bucket or Everburning Flame (endgame)
- Upgrade 1: Super Compactor 3000
- Upgrade 2: Diamond Spreading
- Storage: Large Storage or better
- Crystal: Appropriate type crystal nearby if available
- Selling: NPC via Enchanted Hopper (AFK) or manual Bazaar sell (more profit)

## Tier Upgrade Cost Advice

- Generally, upgrade minions to T5 for the best cost-to-profit ratio
- T11 is worth it for Snow, Clay, and Ice minions (cheap upgrade materials)
- Beyond T5, the time-to-payoff increases dramatically for most minions
- Exception: Revenant and Tarantula - T4 is often the sweet spot due to expensive upgrade materials
- Always craft at least one of every minion tier for unique craft count toward more slots
