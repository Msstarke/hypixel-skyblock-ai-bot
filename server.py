"""
Main entry point — starts the web API server.
No Discord bot. The in-game mod talks directly to the Railway API.
"""
import os
import traceback
from dotenv import load_dotenv

load_dotenv()

try:
    from ai_handler import AIHandler
    from bazaar_tracker import BazaarTracker
    import web_dashboard

    ai = AIHandler()
    tracker = BazaarTracker()
    ai.tracker = tracker

    web_dashboard._live_knowledge_base = ai.knowledge
    web_dashboard._live_ai_handler = ai
except Exception as e:
    print(f"[server] STARTUP ERROR: {e}")
    traceback.print_exc()
    # Start web server anyway so we can see the error
    import web_dashboard

if __name__ == "__main__":
    web_dashboard.run_dashboard()
