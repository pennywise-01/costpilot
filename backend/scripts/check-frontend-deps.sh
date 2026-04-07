#!/usr/bin/env bash
echo "=== Frontend Dependency Security Check ==="
cd "$(dirname "$0")/../frontend" || exit
npm audit 2>/dev/null || echo "Run: npm audit"
