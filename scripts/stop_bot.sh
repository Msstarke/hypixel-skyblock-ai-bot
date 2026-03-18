#!/usr/bin/env bash
# Stop all running bot instances
taskkill //F //IM python.exe 2>/dev/null && echo "Bot stopped." || echo "No bot running."
