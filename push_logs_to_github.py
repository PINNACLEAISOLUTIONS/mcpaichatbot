#!/usr/bin/env python3
"""
Manual GitHub Push Script for Conversation Logs

This script manually pushes conversation logs to a GitHub repository.
It should NEVER be called during live chat requests.

Usage:
    python push_logs_to_github.py

Environment Variables Required:
    GITHUB_TOKEN: Personal access token with repo write access
    GITHUB_REPO: Repository in format "owner/repo" (e.g., "MiamiLovesGreen/mcpaichatbot")
    GITHUB_BRANCH: Branch to push to (default: "main")
    ENABLE_GITHUB_LOGGING: Must be "true" to enable

The script will:
1. Read all local conversation logs from /logs/conversations/
2. Create/update a combined log file in the repo under /conversation_logs/
3. Commit and push changes
"""

import os
import sys
import json
import base64
import logging
from datetime import datetime
from pathlib import Path

import httpx

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Configuration
LOGS_DIR = Path("logs/conversations")
ENABLE_GITHUB_LOGGING = os.getenv("ENABLE_GITHUB_LOGGING", "false").lower() == "true"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
GITHUB_REPO = os.getenv("GITHUB_REPO", "").strip()
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main").strip()


def check_prerequisites() -> bool:
    """Verify all required environment variables are set."""
    if not ENABLE_GITHUB_LOGGING:
        logger.error("❌ ENABLE_GITHUB_LOGGING is not set to 'true'. Aborting.")
        return False

    if not GITHUB_TOKEN:
        logger.error("❌ GITHUB_TOKEN environment variable is not set.")
        return False

    if not GITHUB_REPO:
        logger.error(
            "❌ GITHUB_REPO environment variable is not set (format: owner/repo)."
        )
        return False

    return True


def get_local_logs() -> list:
    """Read all local conversation logs."""
    if not LOGS_DIR.exists():
        logger.warning(f"Logs directory does not exist: {LOGS_DIR}")
        return []

    logs = []
    for log_file in LOGS_DIR.glob("*.json"):
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                logs.append(json.load(f))
        except Exception as e:
            logger.warning(f"Failed to read {log_file}: {e}")

    logger.info(f"📂 Found {len(logs)} local log files")
    return logs


def get_file_sha(filepath: str) -> str | None:
    """Get the SHA of an existing file in the repo (needed for updates)."""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{filepath}"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }

    try:
        with httpx.Client() as client:
            resp = client.get(url, headers=headers, params={"ref": GITHUB_BRANCH})
            if resp.status_code == 200:
                return resp.json().get("sha")
    except Exception:
        pass
    return None


def push_logs_to_github(logs: list) -> bool:
    """Push logs to GitHub repository."""
    if not logs:
        logger.info("No logs to push.")
        return True

    # Create a combined log file with timestamp
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"conversation_logs/logs_{timestamp}.json"

    content = {
        "exported_at": datetime.utcnow().isoformat() + "Z",
        "total_conversations": len(logs),
        "conversations": logs,
    }

    content_json = json.dumps(content, indent=2, ensure_ascii=False)
    content_b64 = base64.b64encode(content_json.encode("utf-8")).decode("utf-8")

    # Check if file exists (for update)
    sha = get_file_sha(filename)

    # Prepare API request
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{filename}"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }

    payload = {
        "message": f"📝 Add conversation logs - {len(logs)} conversations",
        "content": content_b64,
        "branch": GITHUB_BRANCH,
    }

    if sha:
        payload["sha"] = sha

    try:
        with httpx.Client() as client:
            resp = client.put(url, headers=headers, json=payload, timeout=30.0)

            if resp.status_code in (200, 201):
                logger.info(f"✅ Successfully pushed logs to {GITHUB_REPO}/{filename}")
                return True
            else:
                logger.error(
                    f"❌ GitHub API error: {resp.status_code} - {resp.text[:200]}"
                )
                return False

    except Exception as e:
        logger.error(f"❌ Failed to push to GitHub: {e}")
        return False


def main():
    """Main entry point."""
    logger.info("=" * 50)
    logger.info("📤 Starting manual GitHub log push")
    logger.info("=" * 50)

    if not check_prerequisites():
        sys.exit(1)

    logs = get_local_logs()

    if not logs:
        logger.info("No logs found to push. Exiting.")
        sys.exit(0)

    success = push_logs_to_github(logs)

    if success:
        logger.info("✅ Log push completed successfully!")
        sys.exit(0)
    else:
        logger.error("❌ Log push failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
