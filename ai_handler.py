import os
import asyncio
from groq import AsyncGroq
from hypixel_api import HypixelAPI
from knowledge_base import KnowledgeBase

PRICE_KEYWORDS = [
    "cost", "price", "worth", "buy", "sell", "bazaar", "coins",
    "how much", "profit", "flip", "instabuy", "instasell"
]

MAX_DISCORD_LEN = 1900  # leave buffer under 2000


class AIHandler:
    def __init__(self):
        self.groq = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))
        self.hypixel = HypixelAPI(os.getenv("HYPIXEL_API_KEY", ""))
        self.knowledge = KnowledgeBase()
        self.semaphore = asyncio.Semaphore(5)  # max 5 concurrent AI calls
        self.model = "llama-3.3-70b-versatile"  # best free Groq model

    def _needs_live_data(self, question: str) -> bool:
        q = question.lower()
        return any(kw in q for kw in PRICE_KEYWORDS)

    async def _build_live_context(self, question: str) -> str:
        if not os.getenv("HYPIXEL_API_KEY"):
            return ""

        # Pull every word/phrase combo (1-3 words) and search bazaar
        words = question.split()
        seen = set()
        results = {}

        for i in range(len(words)):
            for j in range(i + 1, min(i + 4, len(words) + 1)):
                phrase = " ".join(words[i:j])
                if phrase in seen or len(phrase) < 3:
                    continue
                seen.add(phrase)
                try:
                    matches = await self.hypixel.search_bazaar(phrase)
                    for m in matches:
                        results[m["id"]] = m
                except Exception:
                    pass

        if not results:
            return ""

        lines = ["Current Bazaar prices (live):"]
        for item in list(results.values())[:20]:
            lines.append(
                f"  {item['id']}: buy {item['buy']:,.1f} | sell {item['sell']:,.1f} coins"
            )
        return "\n".join(lines)

    async def get_response(self, question: str) -> str:
        async with self.semaphore:
            static_ctx = self.knowledge.get_relevant_knowledge(question)
            live_ctx = ""

            if self._needs_live_data(question):
                try:
                    live_ctx = await self._build_live_context(question)
                except Exception as e:
                    live_ctx = f"(Live price fetch failed: {e})"

            system = (
                "You are a Hypixel Skyblock expert assistant. "
                "Answer questions accurately and concisely. "
                "Show calculations when asked about costs or quantities. "
                "Format coin amounts with commas (e.g. 1,234,567 coins). "
                "If unsure, say so rather than guessing."
            )

            if static_ctx:
                system += f"\n\nRelevant game info:\n{static_ctx}"
            if live_ctx:
                system += f"\n\n{live_ctx}"

            try:
                resp = await self.groq.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": question},
                    ],
                    max_tokens=600,
                    temperature=0.2,
                )
                text = resp.choices[0].message.content.strip()
                # Trim to Discord limit
                if len(text) > MAX_DISCORD_LEN:
                    text = text[:MAX_DISCORD_LEN] + "…"
                return text
            except Exception as e:
                return f"AI error: {e}"
