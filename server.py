"""
Main entry point — starts the web API server.
No Discord bot. The in-game mod talks directly to the Railway API.
"""
import os
from dotenv import load_dotenv
from ai_handler import AIHandler
from bazaar_tracker import BazaarTracker
import web_dashboard

load_dotenv()

ai = AIHandler()
tracker = BazaarTracker()
ai.tracker = tracker

web_dashboard._live_knowledge_base = ai.knowledge
web_dashboard._live_ai_handler = ai

if __name__ == "__main__":
    web_dashboard.run_dashboard()
