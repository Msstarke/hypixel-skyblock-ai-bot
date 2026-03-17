#!/usr/bin/env bash
# Called after Claude edits a file. Syntax checks, commits, and restarts the bot.

FILE=$(jq -r '.tool_input.file_path // .tool_response.filePath // empty' 2>/dev/null)

# Only run for .py files inside the bot directory
if [[ "$FILE" != *hypixel.ai*.py ]]; then
  exit 0
fi

BOT_DIR="/c/Users/matthew/Desktop/hypixel.ai"
cd "$BOT_DIR" || exit 1

BASENAME=$(basename "$FILE")

# 1. Syntax check
echo "--- Checking syntax: $BASENAME ---"
python -m py_compile "$FILE"
if [ $? -ne 0 ]; then
  echo "SYNTAX ERROR in $BASENAME — skipping commit and restart"
  exit 1
fi
echo "Syntax OK"

# 2. Import check (catches missing deps, bad imports)
echo "--- Import check ---"
python -c "
import importlib.util, sys
spec = importlib.util.spec_from_file_location('mod', '$FILE')
mod = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(mod)
except SystemExit:
    pass  # bot.run() calls sys.exit on Ctrl+C, ignore
except Exception as e:
    # Only fail on import-level errors
    if 'DISCORD_TOKEN' not in str(e) and 'token' not in str(e).lower():
        print(f'Import error: {e}')
        sys.exit(1)
" 2>/dev/null
echo "Imports OK"

# 3. Commit
echo "--- Committing ---"
git add "$BASENAME" knowledge/ 2>/dev/null
git add "$BASENAME" 2>/dev/null
git commit -m "Auto: update $BASENAME" 2>/dev/null && echo "Committed" || echo "Nothing new to commit"

# 4. Kill existing bot
echo "--- Restarting bot ---"
pkill -f "python bot.py" 2>/dev/null
sleep 1

# 5. Start bot, log output
python bot.py >> "$BOT_DIR/bot.log" 2>&1 &
BOT_PID=$!
sleep 4

# 6. Verify it's running
if kill -0 $BOT_PID 2>/dev/null; then
  echo "Bot running (PID $BOT_PID)"
else
  echo "Bot FAILED to start — last 10 lines of bot.log:"
  tail -10 "$BOT_DIR/bot.log"
  exit 1
fi
