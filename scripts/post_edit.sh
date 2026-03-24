#!/usr/bin/env bash
# PostToolUse hook: syntax check, auto-commit, bot restart

BOT_DIR="/c/Users/matthew/Desktop/hypixel.ai"

# Read file path from stdin JSON using Python (jq not available)
FILE=$(python -c "
import sys, json
try:
    data = json.load(sys.stdin)
    path = data.get('tool_input', {}).get('file_path') or data.get('tool_response', {}).get('filePath') or ''
    print(path.replace('\\\\', '/'))
except:
    print('')
" 2>/dev/null)

# Only run for .py files inside the bot directory
if [[ "$FILE" != *hypixel.ai*.py ]]; then
  exit 0
fi

cd "$BOT_DIR" || exit 1
BASENAME=$(basename "$FILE")

# 1. Syntax check
echo "--- Syntax check: $BASENAME ---"
python -m py_compile "$FILE"
if [ $? -ne 0 ]; then
  echo "SYNTAX ERROR — skipping restart"
  exit 1
fi
echo "OK"

# 2. Commit
echo "--- Committing ---"
git add "$BASENAME" 2>/dev/null
git commit -m "Auto: update $BASENAME" 2>/dev/null && echo "Committed" || echo "No changes"

# 3. Skip local bot restart (runs on Railway, not desktop)
echo "--- Skipping local restart (Railway handles this) ---"
