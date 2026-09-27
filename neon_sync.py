"""
Neon PostgreSQL Lead Sync Module
Connects the Render Chatbot backend to the Neon PostgreSQL database
for bidirectional lead pipeline synchronization.
"""

import os
import re
import json
import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, Any

logger = logging.getLogger("neon_sync")

DEFAULT_NEON_URL = (
    "postgresql://neondb_owner:npg_NXec3rGRkO4K"
    "@ep-odd-union-b5golfmp-pooler.c-7.us-east-2.aws.neon.tech/neondb?sslmode=require"
)

NEON_DATABASE_URL = os.environ.get("NEON_DATABASE_URL", DEFAULT_NEON_URL)

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
PHONE_REGEX = re.compile(
    r"(?:\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})"
)
COMPANY_REGEX = re.compile(
    r"(?:company|business|work at|firm|org|representing)[:\s]+([A-Za-z0-9\s&.,'-]{3,40})",
    re.IGNORECASE,
)
NAME_REGEX = re.compile(
    r"(?:my name is|i am|i'm|this is)[:\s]+([A-Za-z\s]{2,30})",
    re.IGNORECASE,
)


def extract_lead_info(message: str) -> Dict[str, Optional[str]]:
    """Extract lead indicators (email, phone, company, name) from a chat message."""
    if not message:
        return {}

    lead_data: Dict[str, Optional[str]] = {
        "email": None,
        "phone": None,
        "company_name": None,
        "contact_name": None,
    }

    # Email
    email_match = EMAIL_REGEX.search(message)
    if email_match:
        lead_data["email"] = email_match.group(0).strip()

    # Phone
    phone_match = PHONE_REGEX.search(message)
    if phone_match:
        lead_data["phone"] = phone_match.group(0).strip()

    # Company
    company_match = COMPANY_REGEX.search(message)
    if company_match:
        lead_data["company_name"] = company_match.group(1).strip()

    # Name
    name_match = NAME_REGEX.search(message)
    if name_match:
        lead_data["contact_name"] = name_match.group(1).strip()

    return lead_data


def append_lead_to_workspace(lead_dict: Dict[str, Any]):
    """Ensure inbound leads are also appended to leads.json and leads.csv in gemini_workspace."""
    workspace_dir = Path(r"C:\Users\futur\gemini_workspace")
    if not workspace_dir.exists():
        return

    # 1. Append to leads.json
    json_path = workspace_dir / "leads.json"
    try:
        data = []
        if json_path.exists() and json_path.stat().st_size > 0:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        data.append(lead_dict)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.warning(f"Failed to append to workspace leads.json: {e}")

    # 2. Append to leads.csv
    csv_path = workspace_dir / "leads.csv"
    try:
        import csv
        fieldnames = ["id", "company_name", "contact_name", "email", "phone", "status", "source", "brand", "notes", "created_at"]
        exists = csv_path.exists() and csv_path.stat().st_size > 0
        with open(csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            if not exists:
                writer.writeheader()
            writer.writerow(lead_dict)
    except Exception as e:
        logger.warning(f"Failed to append to workspace leads.csv: {e}")


def insert_inbound_lead_sync(
    company_name: Optional[str] = None,
    contact_name: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    status: str = "inbound_chat",
    source: str = "website_chat",
    brand: str = "pinnacle",
    notes: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> bool:
    """Synchronous insertion into Neon leads table using psycopg2."""
    try:
        import psycopg2

        db_url = os.environ.get("NEON_DATABASE_URL", DEFAULT_NEON_URL)
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()

        now = datetime.now(timezone.utc)
        meta_json = json.dumps(metadata) if metadata else None

        cur.execute(
            """
            INSERT INTO public.leads 
            (company_name, contact_name, email, phone, status, source, brand, notes, metadata, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
            """,
            (
                company_name,
                contact_name,
                email,
                phone,
                status,
                source,
                brand,
                notes,
                meta_json,
                now,
                now,
            ),
        )
        lead_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()

        # Workspace file backup
        try:
            append_lead_to_workspace({
                "id": lead_id,
                "company_name": company_name,
                "contact_name": contact_name,
                "email": email,
                "phone": phone,
                "status": status,
                "source": source,
                "brand": brand,
                "notes": notes,
                "created_at": now.isoformat()
            })
        except Exception:
            pass
        logger.info(f"✅ Inbound lead #{lead_id} synced to Neon PostgreSQL successfully.")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to sync lead to Neon: {e}")
        return False


async def insert_inbound_lead_async(
    company_name: Optional[str] = None,
    contact_name: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    status: str = "inbound_chat",
    source: str = "website_chat",
    brand: str = "pinnacle",
    notes: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> bool:
    """Async insertion into Neon leads table (runs sync in threadpool)."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        insert_inbound_lead_sync,
        company_name,
        contact_name,
        email,
        phone,
        status,
        source,
        brand,
        notes,
        metadata,
    )


async def process_chat_message_for_leads(
    user_message: str,
    session_id: str,
    brand: Optional[str] = "pinnacle",
    client_ip: str = "unknown",
) -> Optional[Dict[str, Any]]:
    """
    Scans an incoming chat message for lead information (email, phone, company).
    If found, writes to Neon with status='inbound_chat'.
    """
    info = extract_lead_info(user_message)
    if info.get("email") or info.get("phone") or info.get("company_name"):
        logger.info(
            f"🎯 Inbound lead detected from chat! Email={info.get('email')}, Phone={info.get('phone')}, Company={info.get('company_name')}"
        )

        meta = {
            "session_id": session_id,
            "client_ip": client_ip,
            "detected_at": datetime.now(timezone.utc).isoformat(),
            "raw_message": user_message[:500],
        }

        asyncio.create_task(
            insert_inbound_lead_async(
                company_name=info.get("company_name"),
                contact_name=info.get("contact_name"),
                email=info.get("email"),
                phone=info.get("phone"),
                status="inbound_chat",
                source="website_chat",
                brand=brand or "pinnacle",
                notes=f"User dropped contact details in chat session {session_id}: {user_message[:200]}",
                metadata=meta,
            )
        )
        return info
    return None