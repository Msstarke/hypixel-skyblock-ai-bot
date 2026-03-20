"""
Bazaar historical data tracker.
Snapshots all Bazaar products every 5 minutes into SQLite.
Provides trend analysis, volatility detection, and demand surge alerts.
"""
import sqlite3
import time
import asyncio
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent / "data" / "bazaar_history.db"
SNAPSHOT_INTERVAL = 300  # 5 minutes
KEEP_DAYS = 90           # keep 90 days for long-term analysis


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("""
        CREATE TABLE IF NOT EXISTS snapshots (
            id            INTEGER PRIMARY KEY,
            item_id       TEXT    NOT NULL,
            ts            INTEGER NOT NULL,
            buy_price     REAL,
            sell_price    REAL,
            buy_vol_week  INTEGER,
            sell_vol_week INTEGER,
            buy_orders    INTEGER,
            sell_orders   INTEGER
        )
    """)
    con.execute("CREATE INDEX IF NOT EXISTS idx_item_ts ON snapshots(item_id, ts)")
    con.commit()
    return con


class BazaarTracker:
    def __init__(self):
        self._con = _connect()

    def save_snapshot(self, products: dict):
        """Insert a snapshot row for every product in the Bazaar API response."""
        ts = int(time.time())
        rows = []
        for item_id, product in products.items():
            qs = product.get("quick_status", {})
            rows.append((
                item_id, ts,
                qs.get("buyPrice"),
                qs.get("sellPrice"),
                qs.get("buyMovingWeek"),
                qs.get("sellMovingWeek"),
                qs.get("buyOrders"),
                qs.get("sellOrders"),
            ))
        self._con.executemany(
            "INSERT INTO snapshots(item_id,ts,buy_price,sell_price,buy_vol_week,sell_vol_week,buy_orders,sell_orders) "
            "VALUES(?,?,?,?,?,?,?,?)",
            rows,
        )
        self._con.commit()
        self._prune()

    def _prune(self):
        cutoff = int(time.time()) - KEEP_DAYS * 86400
        self._con.execute("DELETE FROM snapshots WHERE ts < ?", (cutoff,))
        self._con.commit()

    def last_snapshot_age(self) -> Optional[int]:
        """Returns seconds since last snapshot, or None if no data."""
        row = self._con.execute("SELECT MAX(ts) as t FROM snapshots").fetchone()
        if row and row["t"]:
            return int(time.time()) - row["t"]
        return None

    def get_history(self, item_id: str, hours: int = 24) -> list[dict]:
        """Return price history rows for an item over the last N hours."""
        since = int(time.time()) - hours * 3600
        rows = self._con.execute(
            "SELECT ts, buy_price, sell_price, buy_vol_week, sell_vol_week "
            "FROM snapshots WHERE item_id=? AND ts>=? ORDER BY ts ASC",
            (item_id, since),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_trend(self, item_id: str, hours: int = 6) -> dict:
        """
        Analyse recent price trend for an item.
        Returns: direction ('rising'|'falling'|'stable'), pct_change, avg_buy, avg_sell, data_points
        """
        rows = self.get_history(item_id, hours)
        if len(rows) < 2:
            return {"direction": "unknown", "pct_change": 0, "data_points": len(rows)}

        prices = [r["buy_price"] for r in rows if r["buy_price"]]
        if not prices:
            return {"direction": "unknown", "pct_change": 0, "data_points": 0}

        first = sum(prices[:3]) / min(3, len(prices))  # avg of first 3
        last  = sum(prices[-3:]) / min(3, len(prices)) # avg of last 3
        pct = ((last - first) / first) * 100 if first else 0

        direction = "stable"
        if pct > 2:
            direction = "rising"
        elif pct < -2:
            direction = "falling"

        sells = [r["sell_price"] for r in rows if r["sell_price"]]
        return {
            "direction": direction,
            "pct_change": round(pct, 2),
            "avg_buy": round(sum(prices) / len(prices), 1),
            "avg_sell": round(sum(sells) / len(sells), 1) if sells else 0,
            "data_points": len(rows),
        }

    def get_volatile_items(self, hours: int = 6, top_n: int = 10) -> list[dict]:
        """
        Items with the highest price swing % in the last N hours.
        High volatility = risky but potentially profitable to time.
        """
        since = int(time.time()) - hours * 3600
        # Get min/max buy price per item in the window
        rows = self._con.execute("""
            SELECT item_id,
                   MIN(buy_price) as min_buy, MAX(buy_price) as max_buy,
                   AVG(buy_price) as avg_buy, AVG(sell_price) as avg_sell,
                   COUNT(*) as pts
            FROM snapshots
            WHERE ts >= ? AND buy_price > 0
            GROUP BY item_id
            HAVING pts >= 3
        """, (since,)).fetchall()

        results = []
        for r in rows:
            swing = ((r["max_buy"] - r["min_buy"]) / r["min_buy"]) * 100
            if swing > 5:
                results.append({
                    "id": r["item_id"],
                    "name": r["item_id"].replace("_", " ").title(),
                    "swing_pct": round(swing, 1),
                    "min": round(r["min_buy"]),
                    "max": round(r["max_buy"]),
                    "avg_buy": round(r["avg_buy"], 1),
                    "avg_sell": round(r["avg_sell"], 1) if r["avg_sell"] else 0,
                })

        results.sort(key=lambda x: x["swing_pct"], reverse=True)
        return results[:top_n]

    def get_demand_surges(self, hours: int = 3, top_n: int = 10) -> list[dict]:
        """
        Items where buy volume (demand) spiked significantly vs. their own baseline.
        Surge = buy_vol_week in last snapshot >> avg over the past N hours.
        """
        since = int(time.time()) - hours * 3600
        rows = self._con.execute("""
            SELECT item_id,
                   AVG(buy_vol_week) as avg_vol,
                   MAX(buy_vol_week) as max_vol,
                   AVG(buy_price) as avg_buy,
                   AVG(sell_price) as avg_sell,
                   COUNT(*) as pts
            FROM snapshots
            WHERE ts >= ? AND buy_vol_week > 0
            GROUP BY item_id
            HAVING pts >= 2
        """, (since,)).fetchall()

        surges = []
        for r in rows:
            if r["avg_vol"] <= 0:
                continue
            surge_pct = ((r["max_vol"] - r["avg_vol"]) / r["avg_vol"]) * 100
            if surge_pct > 20:
                surges.append({
                    "id": r["item_id"],
                    "name": r["item_id"].replace("_", " ").title(),
                    "surge_pct": round(surge_pct, 1),
                    "avg_vol": int(r["avg_vol"]),
                    "peak_vol": int(r["max_vol"]),
                    "avg_buy": round(r["avg_buy"], 1),
                    "avg_sell": round(r["avg_sell"], 1) if r["avg_sell"] else 0,
                })

        surges.sort(key=lambda x: x["surge_pct"], reverse=True)
        return surges[:top_n]

    def get_smart_flips(self, min_margin_pct: float = 1.5, min_vol: int = 5_000, top_n: int = 15) -> list[dict]:
        """
        Enhanced flip finder using historical data:
        - Uses 6h avg price (more stable than live snapshot)
        - Filters out items with rising buy price (margin shrinking)
        - Boosts score for items with stable or falling buy price (better entry)
        - Penalises high volatility (risky)
        """
        TAX = 1.25
        since = int(time.time()) - 6 * 3600

        rows = self._con.execute("""
            SELECT item_id,
                   AVG(buy_price)  as avg_buy,
                   AVG(sell_price) as avg_sell,
                   MIN(buy_price)  as min_buy,
                   MAX(buy_price)  as max_buy,
                   AVG(buy_vol_week)  as avg_buy_vol,
                   AVG(sell_vol_week) as avg_sell_vol,
                   AVG(buy_orders)    as avg_buy_orders,
                   AVG(sell_orders)   as avg_sell_orders,
                   COUNT(*) as pts
            FROM snapshots
            WHERE ts >= ? AND buy_price > 0 AND sell_price > 0
            GROUP BY item_id
            HAVING pts >= 3
        """, (since,)).fetchall()

        flips = []
        for r in rows:
            buy  = r["avg_buy"]
            sell = r["avg_sell"]
            if buy <= sell:
                continue

            margin = buy - sell
            margin_pct = (margin / buy) * 100
            net_pct = margin_pct - TAX
            weekly_vol = min(r["avg_buy_vol"] or 0, r["avg_sell_vol"] or 0)

            if net_pct < min_margin_pct or weekly_vol < min_vol or margin < 100:
                continue

            # Volatility penalty: high swing = risky
            swing = ((r["max_buy"] - r["min_buy"]) / r["min_buy"]) * 100 if r["min_buy"] else 0
            volatility_factor = max(0.5, 1 - swing / 100)

            # Trend: get last vs first snapshot in window
            trend = self.get_trend(r["item_id"], hours=6)
            trend_factor = 1.0
            if trend["direction"] == "falling":
                trend_factor = 1.2   # good: buy price falling = cheaper entry
            elif trend["direction"] == "rising":
                trend_factor = 0.75  # bad: margin may shrink further

            score = net_pct * (weekly_vol / 100_000) * volatility_factor * trend_factor

            flips.append({
                "id": r["item_id"],
                "name": r["item_id"].replace("_", " ").title(),
                "buy": round(buy, 1),
                "sell": round(sell, 1),
                "margin": round(margin, 1),
                "margin_pct": round(net_pct, 2),
                "weekly_vol": int(weekly_vol),
                "buy_orders": int(r["avg_buy_orders"] or 0),
                "sell_orders": int(r["avg_sell_orders"] or 0),
                "trend": trend["direction"],
                "trend_pct": trend["pct_change"],
                "swing_pct": round(swing, 1),
                "score": score,
                "data_pts": r["pts"],
            })

        flips.sort(key=lambda x: x["score"], reverse=True)
        return flips[:top_n]

    def format_history_for_ai(self, item_id: str, hours: int = 24) -> str:
        """Compact history string for injection into AI context."""
        rows = self.get_history(item_id, hours)
        if not rows:
            return ""
        trend = self.get_trend(item_id, hours)
        lines = [
            f"Price history for {item_id.replace('_',' ').title()} (last {hours}h, {len(rows)} snapshots):",
            f"  Trend: {trend['direction']} ({trend['pct_change']:+.1f}%)",
            f"  Avg buy: {trend.get('avg_buy', 0):,.1f} | Avg sell: {trend.get('avg_sell', 0):,.1f}",
        ]
        # Sample up to 5 evenly spaced data points
        step = max(1, len(rows) // 5)
        samples = rows[::step][-5:]
        for s in samples:
            t = time.strftime("%H:%M", time.localtime(s["ts"]))
            lines.append(f"  [{t}] buy {s['buy_price']:,.1f} | sell {s['sell_price']:,.1f}")
        return "\n".join(lines)
