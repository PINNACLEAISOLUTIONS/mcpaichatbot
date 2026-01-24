"""
Conversation Logger - Separate module for logging chatbot conversations.

Stores conversations locally in /logs/conversations/ as JSON files.
Optionally supports manual push to GitHub (never auto-push during requests).

Environment Variables:
- ENABLE_CONVERSATION_LOGGING: true/false (default: true)
- ENABLE_GITHUB_LOGGING: true/false (default: false) - for manual push script only
"""

import json
import os
import re
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Configuration
LOGS_DIR = Path("logs/conversations")
ENABLE_LOGGING = os.getenv("ENABLE_CONVERSATION_LOGGING", "true").lower() == "true"


def _ensure_logs_dir():
    """Create logs directory if it doesn't exist."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)


def _sanitize_pii(text: str) -> str:
    """Remove or mask PII from text content."""
    if not text or not isinstance(text, str):
        return text or ""

    sanitized = text

    # Mask email addresses (keep first 2 chars + domain)
    email_pattern = r"([a-zA-Z0-9._%+-]+)@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})"

    def mask_email(match):
        local = match.group(1)
        domain = match.group(2)
        masked_local = local[:2] + "***" if len(local) > 2 else "***"
        return f"{masked_local}@{domain}"

    sanitized = re.sub(email_pattern, mask_email, sanitized)

    # Mask phone numbers (various formats)
    phone_patterns = [
        r"\b(\d{3})[-.\s]?(\d{3})[-.\s]?(\d{4})\b",  # 123-456-7890
        r"\((\d{3})\)\s*(\d{3})[-.\s]?(\d{4})",  # (123) 456-7890
        r"\b(\d{10})\b",  # 1234567890
    ]
    for pattern in phone_patterns:
        sanitized = re.sub(pattern, r"\1-***-****", sanitized)

    # Remove API keys (common patterns)
    api_key_patterns = [
        r"(sk-[a-zA-Z0-9]{20,})",  # OpenAI style
        r"(gsk_[a-zA-Z0-9]{20,})",  # Groq style
        r"(AIza[a-zA-Z0-9_-]{35})",  # Google API
        r"(Bearer\s+[a-zA-Z0-9._-]{20,})",  # Bearer tokens
    ]
    for pattern in api_key_patterns:
        sanitized = re.sub(pattern, "[REDACTED_API_KEY]", sanitized)

    return sanitized


def _sanitize_message(msg: Dict[str, Any]) -> Dict[str, str]:
    """Sanitize a single message, keeping only role and sanitized content."""
    return {
        "role": msg.get("role", "unknown"),
        "content": _sanitize_pii(msg.get("content", "") or ""),
    }


def _extract_tool_usage(messages: List[Dict]) -> List[str]:
    """Extract tool names used in the conversation (no payloads)."""
    tools_used = []
    for msg in messages:
        # Check for tool_calls in assistant messages
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            for tc in msg.get("tool_calls", []):
                if hasattr(tc, "function"):
                    tools_used.append(tc.function.name)
                elif isinstance(tc, dict) and "function" in tc:
                    tools_used.append(tc["function"].get("name", "unknown"))
        # Check for tool role messages
        if msg.get("role") == "tool" and msg.get("name"):
            if msg["name"] not in tools_used:
                tools_used.append(msg["name"])
    return list(set(tools_used))  # Deduplicate


def log_conversation(
    session_id: str,
    messages: List[Dict],
    location_context: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """
    Save a conversation to a local JSON file.

    Args:
        session_id: Unique session identifier
        messages: List of conversation messages
        location_context: Optional location data (city/state)

    Returns:
        Path to the saved log file, or None if logging is disabled/failed
    """
    if not ENABLE_LOGGING:
        return None

    try:
        _ensure_logs_dir()

        timestamp = datetime.utcnow().isoformat() + "Z"
        filename = f"{session_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = LOGS_DIR / filename

        # Build sanitized log entry
        log_entry = {
            "session_id": session_id,
            "timestamp": timestamp,
            "messages": [
                _sanitize_message(m)
                for m in messages
                if m.get("role") in ("user", "assistant", "tool")
            ],
            "location": {
                "city": location_context.get("city") if location_context else None,
                "region": location_context.get("region") if location_context else None,
                "state": location_context.get("state") if location_context else None,
            }
            if location_context and location_context.get("detected")
            else None,
            "tools_used": _extract_tool_usage(messages),
        }

        # Write to file
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(log_entry, f, indent=2, ensure_ascii=False)

        logger.info(f"📝 Conversation logged: {filename}")
        return str(filepath)

    except Exception as e:
        logger.warning(f"Failed to log conversation: {e}")
        return None


def get_all_logs() -> List[Dict]:
    """Read all conversation logs from the logs directory."""
    if not LOGS_DIR.exists():
        return []

    logs = []
    for log_file in LOGS_DIR.glob("*.json"):
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                logs.append(json.load(f))
        except Exception as e:
            logger.warning(f"Failed to read log {log_file}: {e}")

    return sorted(logs, key=lambda x: x.get("timestamp", ""), reverse=True)
