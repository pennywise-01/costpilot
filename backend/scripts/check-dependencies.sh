#!/usr/bin/env bash
# Dependency security check
echo "=== Python Dependency Security Check ==="
pip audit 2>/dev/null || echo "pip-audit not installed. Run: pip install pip-audit && pip-audit"

echo ""
echo "=== Checking for known vulnerable packages ==="
# Manual check for commonly vulnerable packages
python -c "
import importlib.metadata
packages = ['python-jose', 'passlib', 'cryptography', 'fastapi', 'sqlalchemy']
for pkg in packages:
    try:
        version = importlib.metadata.version(pkg)
        print(f'{pkg}: {version}')
    except importlib.metadata.PackageNotFoundError:
        print(f'{pkg}: NOT INSTALLED')
"
