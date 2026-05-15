#!/usr/bin/env python3
"""
INITIUM Video Studio — Admin CLI
Manage team API keys for video generation access.

Usage:
    python3 admin.py list              # List all team keys
    python3 admin.py create "Ainsley"  # Create key for team member
    python3 admin.py revoke <KEY>      # Revoke a key
    python3 admin.py delete <KEY>      # Delete a key permanently
    python3 admin.py stats             # Show usage stats
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from auth import (
    init_admin_key,
    create_team_key,
    revoke_team_key,
    delete_team_key,
    list_team_keys,
    _load_keys,
)

ADMIN_KEY = init_admin_key()


def cmd_list():
    keys = list_team_keys()
    if not keys:
        print("No team keys yet.")
        return
    print(f"\n{'Name':<20} {'Active':<8} {'Usage':<8} {'Last Used':<22} {'Key'}")
    print("-" * 120)
    for k in keys:
        print(f"{k['name']:<20} {str(k.get('active', True)):<8} {k.get('usage_count', 0):<8} {str(k.get('last_used') or '-'):<22} {k['key']}")
    print()


def cmd_create(name):
    entry = create_team_key(name)
    print(f"\n✅ Created key for: {entry['name']}")
    print(f"   Key: {entry['key']}")
    print(f"   Share this with {name} securely.")
    print()


def cmd_revoke(key):
    if revoke_team_key(key):
        print("✅ Key revoked.")
    else:
        print("❌ Key not found.")


def cmd_delete(key):
    if delete_team_key(key):
        print("✅ Key deleted.")
    else:
        print("❌ Key not found.")


def cmd_stats():
    data = _load_keys()
    keys = list_team_keys()
    jobs = _load_jobs()
    print(f"\nAdmin key: {ADMIN_KEY[:30]}...")
    print(f"Team keys: {len(keys)}")
    print(f"Total jobs: {len(jobs)}")
    print()


def _load_jobs():
    import json
    jobs_file = os.path.join(os.path.dirname(__file__), "jobs.json")
    if os.path.exists(jobs_file):
        with open(jobs_file) as f:
            return json.load(f)
    return {}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "list":
        cmd_list()
    elif cmd == "create" and len(sys.argv) >= 3:
        cmd_create(sys.argv[2])
    elif cmd == "revoke" and len(sys.argv) >= 3:
        cmd_revoke(sys.argv[2])
    elif cmd == "delete" and len(sys.argv) >= 3:
        cmd_delete(sys.argv[2])
    elif cmd == "stats":
        cmd_stats()
    else:
        print(__doc__)
        sys.exit(1)
