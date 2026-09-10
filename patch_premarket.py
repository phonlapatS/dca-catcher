import re

with open("src/handlers/mixins/scanning.py", "r") as f:
    content = f.read()

# Replace send_premarket_watchlist_digest
old_def = "    async def send_premarket_watchlist_digest(self):"

# I will find the boundaries of send_premarket_watchlist_digest to replace it safely.
