"""AI Chatbot for Miami Loves Green Landscaping"""

import base64
import json
import logging
import os
import re
import time
import uuid
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv  # type: ignore
from fastapi import HTTPException
import litellm  # type: ignore
import httpx
import asyncio

from mcp_client_manager import MCPClientManager
from groq import Groq  # type: ignore
import db_utils
import sqlite3
import conversation_logger  # Conversation logging (non-intrusive)
import email_utils


# Configure logging
# Production mode: set LOG_LEVEL=WARNING in environment to reduce verbosity
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, log_level, logging.INFO))
logger = logging.getLogger(__name__)

# LiteLLM Configuration (Production Optimized)
litellm.set_verbose = False
if "LITELLM_LOG" in os.environ:
    del os.environ["LITELLM_LOG"]

# Load environment variables
load_dotenv(override=True)

# Suppress specific litellm logs
urllib_log = logging.getLogger("urllib3")
urllib_log.setLevel(logging.WARNING)


class MCPChatbot:
    """AI Chatbot powered by LiteLLM (supports Gemini, Ollama, OpenAI, etc.) with MCP integration"""

    def __init__(self, mcp_manager: MCPClientManager, session_id: Optional[str] = None):
        """
        Initialize the chatbot with an MCP manager and session ID.
        """
        self.mcp_manager = mcp_manager

        # Initialize clients to None
        self.hf_client = None  # HuggingFace MCP client (for search, not images)
        self.gemini_image_client = None  # FREE Gemini 2.0 Flash image generation
        self.public_base_url = (os.getenv("PUBLIC_BASE_URL") or "").rstrip("/")
        logger.info(
            f"🌐 PUBLIC_BASE_URL initialized as: {self.public_base_url or 'NOT SET'}"
        )

        self.groq_client = None

        # Sanitize keys to remove newlines (prevents header injection errors)
        raw_groq = os.getenv("GROQ_API_KEY")
        raw_gemini = os.getenv("GEMINI_API_KEY")
        self.groq_api_key = raw_groq.strip() if raw_groq else None
        self.gemini_api_key = raw_gemini.strip() if raw_gemini else None

        # Update os.environ with sanitized keys so LiteLLM doesn't read the raw ones
        if self.groq_api_key:
            os.environ["GROQ_API_KEY"] = self.groq_api_key
        if self.gemini_api_key:
            os.environ["GEMINI_API_KEY"] = self.gemini_api_key

        self.model = "groq/llama-3.3-70b-versatile"  # Default model

        # Business Assistant State
        self.knowledge_base = self._load_business_knowledge()
        self.lead_state: Dict[str, Any] = {
            "active": False,
            "field": None,
            "data": {},
            "awaiting_permission": False,  # Track if waiting for user permission
            "fields_to_collect": [
                "name",
                "email",
                "phone",  # Optional - user can skip
                "description",  # What they want built/done
            ],
        }

        # ========== LOCAL BUSINESS CONTEXT (ADDITIVE) ==========
        # Tracks user location for personalized local business advice
        self.location_context: Dict[str, Any] = {
            "detected": False,
            "region": None,  # e.g., "North Florida", "Jacksonville area"
            "city": None,  # e.g., "Jacksonville", "Gainesville"
            "state": None,  # e.g., "Florida", "FL"
        }
        # Default home region for Miami Loves Green (used when no location detected)
        self.default_region = "Miami, Florida"
        # ========== END LOCAL BUSINESS CONTEXT ==========

        # ========== PROFESSIONAL HARDENING (ADDITIVE) ==========
        # Image rate limiting - 15 second cooldown per session
        self._last_image_request: float = 0.0
        self._image_cooldown_seconds: int = 15
        # Lead capture staleness tracking
        self._lead_last_activity: float = 0.0
        self._lead_stale_seconds: int = 300  # 5 minutes
        # ========== END PROFESSIONAL HARDENING ==========

        # Session management
        self.sessions_dir = Path("sessions")
        self.sessions_dir.mkdir(exist_ok=True)

        self.session_id = session_id or str(uuid.uuid4())
        self.session_title = None  # Will be generated after first message
        self.conversation_history = self.load_history(self.session_id)
        self.context_summary = ""  # Holds summarized history

        self.system_instruction = (
            "You are the Miami Loves Green Landscaping Chatbot, a helpful assistant for a premier landscaping company in Miami, Florida. "
            "Help with: landscape design, garden maintenance, hardscaping, irrigation, tree care, and outdoor lighting. "
            "Be friendly, professional, and concise. "
            "Our contact info: (786) 570-3215 | miamilovesgreenlandscaping@gmail.com. "
        )

        # Session management

        # System prompt is now added if history is empty
        if not self.conversation_history:
            self._add_system_prompt()

        if self.groq_api_key:
            logger.info("Groq API key found. Initializing Groq client...")
            self.groq_client = Groq(api_key=self.groq_api_key)
        elif self.gemini_api_key:
            self.model = "gemini/gemini-1.5-pro"
            os.environ["GEMINI_API_KEY"] = self.gemini_api_key
            logger.info(f"Gemini API key found. Default model: {self.model}")
        else:
            self.model = "gemini/gemini-2.0-flash"
            logger.warning(
                "NO API KEYS FOUND! Using backup model without key (will likely fail)."
            )

    def _load_business_knowledge(self) -> str:
        """Load business_knowledge.md content into memory."""
        kb_path = Path("business_knowledge.md")
        if kb_path.exists():
            try:
                return kb_path.read_text(encoding="utf-8")
            except Exception as e:
                logger.error(f"Failed to load business_knowledge.md: {e}")
        return ""

    def _detect_quote_intent(self, message: str) -> bool:
        """Detect if the user wants a quote or estimate."""
        keywords = [
            "quote",
            "estimate",
            "pricing",
            "price",
            "how much",
            "cost",
            "build me",
            "create me",
            "make me",
            "need a",
            "want a",
            "get a",
            "interested in",
        ]
        msg_lower = message.lower()
        return any(kw in msg_lower for kw in keywords)

    async def _request_quote_permission(self) -> str:
        """Ask for permission to collect info and email Miami Loves Green."""
        self.lead_state["awaiting_permission"] = True
        return (
            "I'd be happy to help you get a personalized quote! \n\n"
            "**Please allow me to email the Miami Loves Green Landscaping Team with your project details**, "
            "and I'll collect some quick information to get you an accurate estimate for your specific needs.\n\n"
            "May I proceed with collecting your information? (Just say 'yes' or 'sure' to continue)"
        )

    async def _start_lead_capture(self) -> str:
        """Start the lead capture flow after permission granted."""
        self.lead_state["active"] = True
        self.lead_state["awaiting_permission"] = False
        self.lead_state["field"] = self.lead_state["fields_to_collect"][0]
        self.lead_state["data"] = {}
        return "Great! Let's get started. What is your **full name**?"

    async def _process_lead_step(self, user_message: str) -> str:
        """Process one step of the lead capture flow."""
        current_field = self.lead_state["field"]

        # Allow users to skip optional fields
        skip_keywords = ["skip", "pass", "n/a", "none", "no", "don't have"]
        is_skip = any(kw in user_message.lower() for kw in skip_keywords)

        # Phone is optional - user can skip it
        if current_field == "phone" and is_skip:
            self.lead_state["data"][current_field] = "Not provided"
        else:
            self.lead_state["data"][current_field] = user_message

        # Determine next field
        fields = self.lead_state["fields_to_collect"]
        idx = fields.index(current_field)

        if idx + 1 < len(fields):
            next_field = fields[idx + 1]
            self.lead_state["field"] = next_field
            prompts = {
                "email": "Great! What's your **email address**?",
                "phone": "What's the best **phone number** to reach you at? (You can skip this if you prefer email only - just type 'skip')",
                "description": "Perfect! Please provide a **brief description** of what you want built or done:",
            }
            return prompts.get(next_field, f"Please provide your {next_field}:")
        else:
            # All fields collected
            data = self.lead_state["data"]
            self.lead_state["active"] = False
            self.lead_state["field"] = None

            # Save lead to database
            db_utils.save_lead(data)

            # Automated email notification
            email_sent = email_utils.send_lead_email(data)

            summary = "### Quote Request Summary\n\n"
            summary += f"- **Name:** {data.get('name')}\n"
            summary += f"- **Email:** {data.get('email')}\n"
            summary += f"- **Phone:** {data.get('phone', 'Not provided')}\n"
            summary += f"- **Project:** {data.get('description')}\n\n"

            if email_sent:
                summary += "✅ **Request Sent Automatically!** I have emailed your details directly to our team at Miami Loves Green Landscaping.\n\n"
            else:
                summary += "⚠️ **Processing Note:** I've saved your details to our database, but our automated email system is currently warming up.\n\n"
                summary += "No worries! Our team reviews these daily, or you can click below to send a quick backup email:\n"
                summary += f"[Send Backup Email Now]({email_utils.generate_mailto_link(data)})\n\n"

            summary += "Our experts will review your details and contact you within 24 hours to discuss your project.\n\n"
            summary += "For urgent requests, call us at **(786) 570-3215**."

            logger.info(
                f"Lead captured for {data.get('name')}. Email sent: {email_sent}"
            )

            return summary

    async def _lookup_business_knowledge(self, message: str) -> Optional[str]:
        """Classify message and return relevant business knowledge if applicable.

        SMART FILTER: Skips KB injection for generic questions to improve response speed.
        All existing Miami Loves Green detection logic is preserved below.
        """
        msg_lower = message.lower()

        # ========== SMART FILTER (RELAXED) ==========
        # Only skip if it's clearly a pure math/code task unrelated to the business
        if re.match(r"^(calculate|compute|solve|what is \d|how much is \d)", msg_lower):
            logger.info("Smart filter: Skipping KB for math question")
            return None
        # ========== END SMART FILTER ==========

        # ----- ORIGINAL LOGIC BELOW (UNCHANGED) -----
        # Service-related keywords for smarter detection
        service_keywords = [
            "service",
            "services",
            "what do you",
            "what can you",
            "help with",
            "help me",
            "landscape",
            "landscaping",
            "garden",
            "maintenance",
            "mowing",
            "lawn",
            "irrigation",
            "sprinkler",
            "hardscape",
            "hardscaping",
            "paving",
            "paver",
            "patios",
            "patio",
            "tree care",
            "palm",
            "trimming",
            "pruning",
            "lighting",
            "outdoor lighting",
            "design",
            "consultation",
            "quote",
            "estimate",
        ]

        # General inquiry keywords
        general_keywords = [
            "business",
            "company",
            "pricing",
            "cost",
            "contact",
            "support",
            "who are you",
            "about you",
            "tell me about",
            "miami loves green",
            "hours",
            "service area",
            "location",
        ]

        all_keywords = service_keywords + general_keywords

        if any(kw in msg_lower for kw in all_keywords) and self.knowledge_base:
            # Return business knowledge to help answer service inquiries
            logger.info("Injecting business knowledge for Miami Loves Green query")
            return self.knowledge_base
        return None

    def _detect_location(self, message: str) -> bool:
        """Detect location mentions in user message and update location_context.

        LOCAL BUSINESS CONTEXT FEATURE (ADDITIVE - can be removed to revert)
        Returns True if a new location was detected.
        """
        msg_lower = message.lower()

        # Florida regions and their associated cities
        florida_regions = {
            "north florida": {
                "cities": [
                    "jacksonville",
                    "st. augustine",
                    "gainesville",
                    "ocala",
                    "palatka",
                    "fernandina",
                    "orange park",
                ],
                "region": "North Florida",
            },
            "central florida": {
                "cities": [
                    "orlando",
                    "tampa",
                    "lakeland",
                    "daytona",
                    "kissimmee",
                    "sanford",
                    "winter park",
                ],
                "region": "Central Florida",
            },
            "south florida": {
                "cities": [
                    "miami",
                    "fort lauderdale",
                    "west palm beach",
                    "boca raton",
                    "hollywood",
                    "pompano",
                ],
                "region": "South Florida",
            },
            "florida panhandle": {
                "cities": [
                    "pensacola",
                    "tallahassee",
                    "panama city",
                    "destin",
                    "fort walton",
                ],
                "region": "the Florida Panhandle",
            },
            "southwest florida": {
                "cities": [
                    "naples",
                    "fort myers",
                    "sarasota",
                    "cape coral",
                    "bradenton",
                ],
                "region": "Southwest Florida",
            },
        }

        # Also detect state mentions for out-of-state users
        state_patterns = {
            "georgia": "Georgia",
            "alabama": "Alabama",
            "south carolina": "South Carolina",
            "tennessee": "Tennessee",
            "texas": "Texas",
            "california": "California",
            "new york": "New York",
        }

        # Check for explicit location phrases first
        location_phrases = [
            r"i('m| am) (in|from|located in|based in) ([a-z\s,]+)",
            r"my (business|company|shop|store) is in ([a-z\s,]+)",
            r"here in ([a-z\s,]+)",
            r"(in|around|near) ([a-z]+),?\s*(fl|florida)?",
        ]

        for pattern in location_phrases:
            match = re.search(pattern, msg_lower)
            if match and match.lastindex is not None:
                location_text = match.group(match.lastindex)
                if location_text and isinstance(location_text, str):
                    # Try to match against known cities/regions
                    for region_key, region_data in florida_regions.items():
                        for city in region_data["cities"]:
                            if city in location_text:
                                self.location_context["detected"] = True
                                self.location_context["city"] = city.title()
                                self.location_context["region"] = region_data["region"]
                                self.location_context["state"] = "Florida"
                                logger.info(
                                    f"📍 Location detected: {city.title()}, {region_data['region']}"
                                )
                                return True

        # Scan message for city mentions even without explicit phrases
        for region_key, region_data in florida_regions.items():
            # Check region name directly
            region_name = str(region_data["region"])
            if region_key in msg_lower or region_name.lower() in msg_lower:
                self.location_context["detected"] = True
                self.location_context["region"] = region_data["region"]
                self.location_context["state"] = "Florida"
                logger.info(f"📍 Region detected: {region_data['region']}")
                return True

            # Check city names
            for city in region_data["cities"]:
                if city in msg_lower:
                    self.location_context["detected"] = True
                    self.location_context["city"] = city.title()
                    self.location_context["region"] = region_data["region"]
                    self.location_context["state"] = "Florida"
                    logger.info(
                        f"📍 City detected: {city.title()}, {region_data['region']}"
                    )
                    return True

        # Check out-of-state mentions
        for state_key, state_name in state_patterns.items():
            if state_key in msg_lower:
                self.location_context["detected"] = True
                self.location_context["state"] = state_name
                self.location_context["region"] = state_name
                logger.info(f"📍 Out-of-state location detected: {state_name}")
                return True

        return False

    def _get_location_context_prompt(self) -> str:
        """Generate a location context string to inject into the system prompt.

        LOCAL BUSINESS CONTEXT FEATURE (ADDITIVE)
        """
        if self.location_context.get("detected"):
            city = self.location_context.get("city")
            region = self.location_context.get("region")
            state = self.location_context.get("state", "")

            if city:
                return f"The user is located in {city}, {region}. Tailor your advice for businesses in the {city}/{region} area."
            elif region:
                return f"The user is in {region}. Provide locally relevant advice for businesses in {region}."
            elif state:
                return f"The user is in {state}. Adjust your recommendations for that market."

        # Default to home region
        return f"When discussing local business strategies, you may reference {self.default_region} as the home region for Miami Loves Green Landscaping."

    def load_history(self, session_id: str) -> List[Dict]:
        """Load conversation history and optional title from SQLite database."""
        try:
            # Check if we can get title and history together
            conn = sqlite3.connect(db_utils.DB_PATH)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT title, history FROM sessions WHERE session_id = ?",
                (session_id,),
            )
            row = cursor.fetchone()
            conn.close()

            if row:
                self.session_title = row[0]
                return json.loads(row[1])
            return []
        except Exception as e:
            logger.error(f"Failed to load session {session_id} from DB: {e}")
            return []

    def save_history(self):
        """Save conversation history to SQLite database."""
        if not self.session_id:
            return
        try:
            db_utils.save_session_history(
                self.session_id, self.conversation_history, self.session_title
            )
            # ========== CONVERSATION LOGGING (ADDITIVE) ==========
            # Log conversation to local file for later review (non-blocking)
            conversation_logger.log_conversation(
                self.session_id,
                self.conversation_history,
                self.location_context if hasattr(self, "location_context") else None,
            )
            # ========== END CONVERSATION LOGGING ==========
        except Exception as e:
            logger.error(f"Failed to save session {self.session_id} to DB: {e}")

    def _add_system_prompt(self):
        self.conversation_history.append(
            {"role": "system", "content": self.system_instruction}
        )
        self.conversation_history.append(
            {
                "role": "assistant",
                "content": "Hello! I'm the Miami Loves Green Landscaping AI Agent. I'm here to help you with any questions about our landscaping services in Miami. How can I assist you today?",
            }
        )

    def _get_context_summary(self, messages: List[Dict]) -> str:
        """Helper to create a short summary of older messages."""
        if len(messages) <= 10:
            return ""

        # Take messages before the last 10
        older_messages = messages[:-10]
        summary_parts = []
        for m in older_messages:
            role = m.get("role", "unknown")
            content = m.get("content", "") or ""
            if isinstance(content, str) and content:
                # Take first 40 chars of each old message
                summary_parts.append(f"{role}: {content[:40]}...")

        # Keep the summary very tight (300 chars max)
        summary_text = " ".join(summary_parts)
        return f"[History: {summary_text[-300:]}]" if summary_text else ""

    def start_chat(self) -> None:
        """Initialize a new chat session (reset history)"""
        self.conversation_history = [
            {"role": "system", "content": self.system_instruction},
            {
                "role": "assistant",
                "content": "Hello! I'm the Miami Loves Green Landscaping AI Agent. I can help you with landscaping questions, generate design ideas, and provide quotes. How can I assist you today?",
            },
        ]
        logger.info("Chat session reset.")

    def _get_relevant_tools(self, user_message: str) -> List[str]:
        """
        Determine which specific tools are relevant based on keywords.
        Returns a list of tool names to include.
        Returns empty list for no tools (simple chat) - saves tokens!
        """
        message_lower = user_message.lower()
        relevant_tools = []

        # IMAGE GENERATION - Only when user explicitly asks for image/picture/logo
        # Uses FREE Gemini 2.0 Flash
        image_request = any(
            kw in message_lower
            for kw in [
                "image",
                "picture",
                "photo",
                "draw",
                "logo",
                "icon",
                "illustration",
                "pattern",
                "background",
                "diagram",
                "flowchart",
                "story",
                "sequence",
                "edit",
                "modify",
                "restore",
                "enhance",
            ]
        )
        if image_request:
            # Only send ONE primary image tool name to avoid LLM confusion
            relevant_tools.append("generate_image")
            logger.info("DEBUG: Routing to image/design tools")
            # ========== PROFESSIONAL HARDENING ==========
            # When image is requested, skip web search to reduce token usage
            # and avoid confusing the model with multiple tool options
            # ========== END PROFESSIONAL HARDENING ==========

        # WEB SEARCH - For real internet searches (attorneys, businesses, news, etc.)
        # Skip if image request to avoid token waste (professional hardening)
        if not image_request and (
            any(
                kw in message_lower
                for kw in [
                    "search",
                    "find",
                    "look up",
                    "lookup",
                    "attorney",
                    "lawyer",
                    "news",
                    "weather",
                    "price",
                    "review",
                    "jacksonville",
                    "browse",
                    "google",
                    "check",
                    "internet",
                    "online",
                    "latest",
                    "current",
                ]
            )
            or (
                any(
                    kw in message_lower
                    for kw in ["who is", "what is", "when is", "where is", "how to"]
                )
                and not any(
                    factual in message_lower
                    for factual in [
                        "capital of",
                        "capitol of",
                        "math",
                        "square root",
                        "plus",
                        "minus",
                        "divided by",
                        "multiplied by",
                    ]
                )
                and len(user_message.split())
                > 5  # Simple short "What is X" is usually factual
            )
        ):
            # Use DuckDuckGo web search MCP
            relevant_tools.append("websearch_search")
            logger.info("DEBUG: Routing to WEB SEARCH (DuckDuckGo)")

        # Hugging Face Discovery - ONLY for AI model/space specific searches
        if any(
            kw in message_lower
            for kw in ["huggingface", "hf model", "hf space", "ai model", "ml model"]
        ):
            relevant_tools.extend(
                ["space_search", "model_search", "get_model_info", "list_spaces"]
            )

        # Memory - only if explicit memory keywords
        if any(
            kw in message_lower
            for kw in ["remember", "recall", "memory", "fact", "note"]
        ):
            relevant_tools.append("create_entities")

        # AutoAgent - agent, code, execute, task
        if any(
            kw in message_lower
            for kw in [
                "agent",
                "autoagent",
                "profile",
                "python",
                "script",
                "code",
                "execute",
                "task",
            ]
        ):
            relevant_tools.extend(["list_autoagent_profiles", "run_autoagent_task"])

        # Limit to max 10 tools to keep context sane
        relevant_tools = list(set(relevant_tools))[:10]

        if relevant_tools:
            logger.info(f"Sending only {len(relevant_tools)} tool(s): {relevant_tools}")
        else:
            logger.info("No tools needed for this query (saving tokens)")

        return relevant_tools

    async def _format_tools_for_litellm(
        self, tool_filter: Optional[List[str]] = None
    ) -> Optional[List[Dict[str, Any]]]:
        """Format MCP tools for LiteLLM with EXTREME token saving"""
        mcp_tools = self.mcp_manager.get_all_tools().copy()

        # Add Hugging Face MCP tools if client is available
        if self.hf_client:
            hf_tools_data = await self.hf_client.list_tools()
            hf_tools = hf_tools_data.get("tools", [])
            for hf_tool in hf_tools:
                # Add HF tools to the pool
                mcp_tools.append(
                    {
                        "server": "hf",  # Symbolic server name for formatting
                        "name": hf_tool["name"],
                        "description": hf_tool.get("description", ""),
                        "inputSchema": hf_tool.get("inputSchema", {}),
                    }
                )

        # Add Gemini image generation tool (FREE tier)
        if self.gemini_image_client and self.gemini_image_client.enabled:
            gemini_tools = self.gemini_image_client.get_tools()
            mcp_tools.extend(gemini_tools)

        if not mcp_tools:
            return None

        # Filter tools by tool name if a filter is provided
        if tool_filter is not None:
            if not tool_filter:  # Empty list means no tools
                return None
            mcp_tools = [
                t
                for t in mcp_tools
                if f"{t['name']}" in tool_filter
                or f"{t['server']}_{t['name']}" in tool_filter
                or t["name"] in tool_filter
                or any(
                    t["name"].startswith(p) for p in ["hf.", "spaces.", "hub."]
                )  # Always allow HF tools if they match prefix in some logic? Or just rely on user message.
            ]
            if not mcp_tools:
                return None

        openai_tools = []
        seen_functions = set()
        for tool in mcp_tools:
            # SPECIAL CASE: 'generate_image' should NOT have a prefix to keep it simple
            if tool["name"] == "generate_image":
                function_name = "generate_image"
            elif any(tool["name"].startswith(p) for p in ["hf.", "spaces.", "hub."]):
                function_name = tool["name"]
            else:
                function_name = f"{tool['server']}_{tool['name']}"

            if function_name in seen_functions:
                continue
            seen_functions.add(function_name)

            # Ultra-short description
            desc = (
                (tool["description"][:60] + "..")
                if tool.get("description") and len(tool["description"]) > 60
                else tool.get("description", "")
            )

            # Simplify parameters - remove parameter descriptions
            params = tool.get("inputSchema", {})
            if "properties" in params:
                for p_name in params["properties"]:
                    if "description" in params["properties"][p_name]:
                        params["properties"][p_name]["description"] = "required"

            openai_tool = {
                "type": "function",
                "function": {
                    "name": function_name,
                    "description": desc,
                    "parameters": params,
                },
            }
            openai_tools.append(openai_tool)

        logger.info(f"Sending {len(openai_tools)} minimal tools")
        return openai_tools

    async def send_message(self, user_message: str) -> Dict[str, Any]:
        """
        Send a message to the chatbot and get a response
        """
        self._last_image_data = None  # Reset tracking
        if not self.conversation_history:
            self.start_chat()

        self.conversation_history.append({"role": "user", "content": user_message})
        logger.info(f"User: {user_message}")

        # Relaxed trimming: keep more context
        max_history = 11  # Keep ~5 exchanges
        if len(self.conversation_history) > max_history:
            system_msg = self.conversation_history[0]
            # Keep system message and last few exchanges
            self.conversation_history = [system_msg] + self.conversation_history[
                -(max_history - 1) :
            ]
            logger.info(
                f"Trimmed conversation history to {len(self.conversation_history)} messages"
            )

        # ========== PROFESSIONAL HARDENING: Lead Capture Auto-Reset ==========
        # Auto-reset stale lead captures (5 min timeout)
        if self.lead_state["active"] or self.lead_state["awaiting_permission"]:
            if time.time() - self._lead_last_activity > self._lead_stale_seconds:
                logger.info("🔄 Auto-resetting stale lead capture state")
                self.lead_state["active"] = False
                self.lead_state["awaiting_permission"] = False
                self.lead_state["field"] = None
                self.lead_state["data"] = {}
        # ========== END PROFESSIONAL HARDENING ==========

        # 1. Lead Capture Flow (Intercept)
        if self.lead_state["active"]:
            self._lead_last_activity = time.time()  # Update activity timestamp
            res_content = await self._process_lead_step(user_message)
            return {"response": res_content}

        # 2. Permission Request Flow (Intercept)
        if self.lead_state["awaiting_permission"]:
            # Check if user said yes/sure/ok/etc
            affirmative_keywords = [
                "yes",
                "sure",
                "ok",
                "yeah",
                "yep",
                "proceed",
                "go ahead",
                "fine",
            ]
            negative_keywords = ["no", "nope", "not now", "later", "cancel"]
            msg_lower = user_message.lower()

            if any(kw in msg_lower for kw in affirmative_keywords):
                res_content = await self._start_lead_capture()
                return {"response": res_content}
            elif any(kw in msg_lower for kw in negative_keywords):
                res_content = "No problem! Feel free to ask me any questions about our services, or request a quote whenever you're ready. You can also contact us directly at (786) 570-3215 or miamilovesgreenlandscaping@gmail.com."
                return {"response": res_content}
            else:
                res_content = "I didn't quite catch that. Would you like me to proceed with collecting your information for a quote? (Please say 'yes' or 'no')"
                return {"response": res_content}

        # 3. Intent Detection for Quote Request
        if self._detect_quote_intent(user_message):
            res_content = await self._request_quote_permission()
            return {"response": res_content}

        # ========== LOCAL BUSINESS CONTEXT (ADDITIVE) ==========
        # Detect location from user message for personalized advice
        self._detect_location(user_message)
        location_context = self._get_location_context_prompt()
        # ========== END LOCAL BUSINESS CONTEXT ==========

        # 4. Business Knowledge Lookup
        kb_response = await self._lookup_business_knowledge(user_message)

        # Dynamic tool filtering
        relevant_tools = self._get_relevant_tools(user_message)

        # Build system prompt with optional KB and location context
        if kb_response:
            logger.info("Found business knowledge for query.")
            # Inject KB + location context for this turn
            current_system = (
                self.system_instruction
                + f"\n\n{location_context}"
                + f"\n\nCONTEXT FROM BUSINESS KNOWLEDGE PACK:\n{kb_response}"
            )
        else:
            # Still inject location context even without KB
            current_system = self.system_instruction + f"\n\n{location_context}"

        tools = await self._format_tools_for_litellm(tool_filter=relevant_tools)

        try:
            # Pass the custom system prompt with KB/location context
            response = await self._get_completion(
                tools=tools, system_override=current_system
            )

            # Process response with safety check
            if not response.choices:
                logger.error("No choices in model response")
                return {
                    "response": "Error: The AI model failed to provide a response. Please try again."
                }

            message = response.choices[0].message

            # If there is content, print it (streaming support could be added later)
            if message.content:
                logger.info(f"Assistant: {message.content}")

            # Check for tool calls
            tool_calls = message.tool_calls if message.tool_calls else []

            # --- Fallback: Check for text-based tool calls ---
            if not tool_calls:
                # Regex for generate_image{"prompt":...}
                image_pattern = re.search(
                    r"generate_image\s*\(?(\{.*?\})\)?",
                    message.content or "",
                    re.DOTALL,
                )

                if image_pattern:
                    try:
                        json_str = image_pattern.group(1)
                        # clean up potential markdown code blocks
                        if "```json" in json_str:
                            json_str = (
                                json_str.split("```json")[1].split("```")[0].strip()
                            )
                        elif "```" in json_str:
                            json_str = json_str.split("```")[1].split("```")[0].strip()

                        args = json.loads(json_str)
                        logger.info(
                            f"Fallback detected text-based tool call for generate_image: {args}"
                        )

                        # Manually construct a tool call object
                        fallback_tool_call = SimpleNamespace(
                            id="call_fallback_" + str(int(time.time())),
                            function=SimpleNamespace(
                                name="generate_image",
                                arguments=json.dumps(args),
                            ),
                            type="function",
                        )
                        tool_calls = [fallback_tool_call]
                        message.content = ""  # Clear text if we found a tool call
                    except (json.JSONDecodeError, Exception) as e:
                        logger.warning(f"Failed to parse text-based tool call: {e}")

            # If the model wants to call tools, execute them
            if tool_calls:
                # Convert message object to dict to prevent SimpleNamespace errors
                message_dict = {
                    "role": "assistant",
                    "content": getattr(message, "content", "") or "",
                }
                # Include tool_calls if present
                if hasattr(message, "tool_calls") and message.tool_calls:
                    message_dict["tool_calls"] = message.tool_calls

                self.conversation_history.append(message_dict)

                last_tool_result_obj = None
                # Execute all tool calls
                for tool_call in tool_calls:
                    function_name = tool_call.function.name
                    function_args_str = tool_call.function.arguments

                    logger.info(
                        f"DEBUG: Raw tool_call.function.arguments = '{function_args_str}' (type: {type(function_args_str)})"
                    )

                    try:
                        function_args = json.loads(function_args_str)
                        logger.info(
                            f"PARSED TOOL ARGS OK: {function_name} -> {function_args}"
                        )
                    except Exception as json_err:
                        logger.error(
                            f"Failed to parse tool arguments as JSON: {json_err}"
                        )
                        function_args = {}

                    logger.info(f"Tool Call: {function_name}({function_args})")

                    # Initialize variables to handle both success and error cases
                    result_obj = None

                    try:
                        result = await self._execute_mcp_tool(
                            function_name, function_args
                        )
                        # Store last tool result for potential use if AI doesn't respond
                        # We keep it as an object for image detection below
                        result_obj = result
                        last_tool_result_obj = result

                        # CAPTURE IMAGE DATA FOR EXPLICIT RETURN
                        if isinstance(result, dict) and (
                            result.get("image_base64") or result.get("image_url")
                        ):
                            self._last_image_data = {
                                "image_url": result.get("image_url"),
                                "image_base64": result.get("image_base64"),
                                "mime_type": result.get("mime_type", "image/png"),
                                "provider": result.get("provider"),
                            }

                        result_str = str(result)
                        last_tool_result = result_str

                        # TRUNCATE for history: If result is too large (like base64 image),
                        # don't send it back to the LLM as it will crash the token limit.
                        history_result = result_str
                        if len(result_str) > 1000:
                            logger.info(
                                f"Truncating tool result for history ({len(result_str)} chars)"
                            )
                            history_result = (
                                result_str[:200] + "... [TRUNCATED DUE TO SIZE] ..."
                            )
                    except Exception as e:
                        result_obj = None  # No result object on error
                        result_str = f"Error: {str(e)}"
                        history_result = result_str
                        last_tool_result = result_str
                        logger.error(f"Tool execution error: {e}")

                    # SPECIAL CASE: For images, don't send the massive data back to model
                    # Only check if we have a valid result object from successful execution
                    if (
                        result_obj
                        and isinstance(result_obj, dict)
                        and ("image_base64" in result_obj or "image_url" in result_obj)
                    ):
                        # Just send a summary to the AI to save tokens and prevent crashes
                        history_result = f"[IMAGE GENERATED: {result_obj.get('prompt', 'no prompt')}]"
                        if result_obj.get("image_url"):
                            history_result += f" URL: {result_obj.get('image_url')}"
                        result_str = history_result  # Also update result_str for fallthrough message

                    # Add tool result to history
                    self.conversation_history.append(
                        {
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": function_name,
                            "content": history_result,
                        }
                    )

                # OPTIMIZATION: Skip second API call for image generation to save quota
                # If we have an image, just return it directly without another LLM call
                if last_tool_result_obj and isinstance(last_tool_result_obj, dict):
                    if (
                        "image_url" in last_tool_result_obj
                        or "image_base64" in last_tool_result_obj
                    ):
                        # We have an image - no need for another API call
                        logger.info(
                            "Skipping second completion call - returning image directly"
                        )
                        final_message = None  # Signal to skip LLM response
                    else:
                        # Not an image, get final response
                        final_response = await self._get_completion(tools=tools)
                        final_message = (
                            final_response.choices[0].message
                            if final_response.choices
                            else None
                        )
                else:
                    # Second pass: Get final response after tool execution
                    final_response = await self._get_completion(tools=tools)
                    # Process final response with safety check
                    final_message = (
                        final_response.choices[0].message
                        if final_response.choices
                        else None
                    )

                # AUTO-DETECT IMAGES: If tool result has image data, prepare markdown tags
                image_markdown = ""
                if last_tool_result_obj:
                    logger.info(
                        f"DEBUG: last_tool_result_obj type: {type(last_tool_result_obj)}"
                    )
                    logger.info(
                        f"DEBUG: last_tool_result_obj content: {last_tool_result_obj}"
                    )

                    # Case 1: Simple base64 dict (HF Inference / Pollinations)
                    if isinstance(last_tool_result_obj, dict):
                        img_url = last_tool_result_obj.get("image_url")
                        img_b64 = last_tool_result_obj.get("image_base64")

                        logger.info(
                            f"DEBUG: image_url = {img_url}, image_base64 exists = {bool(img_b64)}"
                        )

                        # ALWAYS prefer base64 if we have it - it's embedded and guaranteed to work
                        if img_b64:
                            mime = last_tool_result_obj.get("mime_type", "image/png")
                            image_markdown += (
                                f"\n\n![Generated Image](data:{mime};base64,{img_b64})"
                            )
                        elif img_url:
                            # Add image with a backup link below it (Part B & D)
                            image_markdown += f"\n\n![Generated Image]({img_url})\n\n[🔗 Open Image in New Tab]({img_url})"

                    # Case 2: Standard MCP content (Nano Banana / standard servers)
                    elif hasattr(last_tool_result_obj, "content") and isinstance(
                        last_tool_result_obj.content, list
                    ):
                        for item in last_tool_result_obj.content:
                            # Standard MCP Image item
                            if hasattr(item, "type") and item.type == "image":
                                data = getattr(item, "data", None)
                                mime = getattr(item, "mimeType", "image/png")
                                if data:
                                    image_markdown += f"\n\n![Generated Image](data:{mime};base64,{data})"
                            # Also check dict-like access for robustness
                            elif isinstance(item, dict):
                                if item.get("type") == "image" and item.get("data"):
                                    mime = item.get("mimeType", "image/png")
                                    image_markdown += f"\n\n![Generated Image](data:{mime};base64,{item['data']})"
                                elif "image_url" in item:
                                    img_url = item["image_url"]
                                    image_markdown += (
                                        f"\n\n![Generated Image]({img_url})"
                                    )

                if final_message and final_message.content:
                    assistant_content = final_message.content + image_markdown
                    # Convert final_message to dict to prevent SimpleNamespace errors
                    final_message_dict = {
                        "role": "assistant",
                        "content": assistant_content,  # Include image markdown in history
                    }
                    self.conversation_history.append(final_message_dict)

                    # Generate title after first user message if not set
                    if not self.session_title and len(self.conversation_history) >= 2:
                        try:
                            title_prompt = (
                                f"Based on this message: '{user_message}', "
                                "generate a 2-3 word chat title. Return ONLY the words. No quotes."
                            )
                            # Call LLM for title (low cost)
                            title_resp = await self._get_completion(
                                system_override="You generate short, 2-word titles.",
                                messages=[{"role": "user", "content": title_prompt}],
                            )
                            if (
                                hasattr(title_resp, "choices")
                                and title_resp.choices
                                and title_resp.choices[0].message.content
                            ):
                                self.session_title = title_resp.choices[
                                    0
                                ].message.content.strip()
                                logger.info(
                                    f"Generated Smart Title: {self.session_title}"
                                )
                                # Save immediately so sidebar can see it
                                self.save_history()
                        except Exception as e:
                            logger.error(f"Title generation failed: {e}")

                    logger.info(f"Assistant: {assistant_content[:100]}...")

                    res = {"response": assistant_content}
                    if self.session_title:
                        res["session_title"] = self.session_title
                    if self._last_image_data:
                        res.update(self._last_image_data)
                    return res
                elif image_markdown:
                    notice = ""
                    if isinstance(last_tool_result_obj, dict):
                        tool_notice = last_tool_result_obj.get("notice")
                        if tool_notice:
                            notice = tool_notice + "\n\n"

                    assistant_content = notice + image_markdown
                    self.conversation_history.append(
                        {"role": "assistant", "content": assistant_content}
                    )

                    res = {"response": assistant_content}
                    if self._last_image_data:
                        res.update(self._last_image_data)
                    return res
                else:
                    # ELIMINATE SECOND MODEL CALL:
                    # Return the actual tool result directly (formatted) instead of asking LLM to summarize.
                    # This saves one full completion call per tool use.

                    status_prefix = "✅ Tool executed successfully.\n\n"
                    if "error" in str(last_tool_result).lower():
                        status_prefix = "⚠️ Tool execution finished with results:\n\n"

                    assistant_content = f"{status_prefix}{last_tool_result}"

                    # Add to history so the bot knows it answered
                    self.conversation_history.append(
                        {"role": "assistant", "content": assistant_content}
                    )

                    return {"response": assistant_content}

            # No tool calls, just return text
            # Prepare trimmed messages for completion
            # Truncate to last 10 messages + memory block for token saving
            trimmed_history = self.conversation_history[-10:]
            memory_block = self._get_context_summary(self.conversation_history)

            # Re-insert memory as a pseudo-system note if it exists
            if memory_block:
                trimmed_history.insert(
                    0,
                    {
                        "role": "system",
                        "content": f"Memory of previous talk: {memory_block}",
                    },
                )

            # Consolidate all system messages into one at the front
            current_time = datetime.now().strftime("%Y-%m-%d %I:%M %p")
            time_context = f"\n\n[Current local time: {current_time}]"

            system_content = None
            for m in trimmed_history:
                if m.get("role") == "system":
                    system_content = m.get("content", "")
                    break

            trimmed_history = [m for m in trimmed_history if m.get("role") != "system"]
            trimmed_history.insert(
                0,
                {
                    "role": "system",
                    "content": (system_content or self.system_instruction)
                    + time_context,
                },
            )

            # Use 256-512 max tokens as requested
            response = await self._get_completion(
                tools=tools, system_override=None, messages=trimmed_history
            )
            message = response.choices[0].message

            # Handle Tool Calls
            if hasattr(message, "tool_calls") and message.tool_calls:
                # This path should ideally not be taken if `if tool_calls:` block above handles it.
                # However, if a model without explicit tool_calls support generates text that looks like a tool call,
                # the initial parsing might catch it. For now, we'll assume the main tool_calls block handles it.
                # If this block is reached, it means the model returned tool_calls *after* the initial check,
                # which is unexpected for the "No tool calls, just return text" branch.
                # For robustness, we could re-process tool calls here, but for now, we'll just log and return text.
                logger.warning(
                    "Model returned tool calls in the 'no tool calls' branch. This should not happen."
                )
                # Fallback to treating it as text if content is also present, or just return empty if only tool calls.
                message_dict = {"role": "assistant", "content": message.content or ""}
                self.conversation_history.append(message_dict)
                self.save_history()  # Save full history including new message
                return {"response": message.content or ""}

            # Normal Text Response
            message_dict = {"role": "assistant", "content": message.content or ""}
            self.conversation_history.append(message_dict)
            self.save_history()  # Save full history including new message
            return {"response": message.content or ""}

        except HTTPException as he:
            raise he
        except Exception as e:
            logger.error(f"Error in chat loop: {e}")
            return {"response": f"I encountered an error: {str(e)}"}

    async def _get_completion(
        self, tools=None, max_retries=2, system_override=None, messages=None
    ):
        """
        Helper to call litellm completion with advanced multi-model fallback logic.
        Fallback Chain: Groq -> Gemini 2.0 Flash -> Gemini 2.0 Flash Exp
        Silently switches between models on rate limits or token exhaustion.
        """
        # Define the fallback chain with VERIFIED WORKING models only
        # Last tested: 2024-12-26
        fallback_chain = []

        # Prepare messages
        if messages is None:
            messages = self.conversation_history.copy()
        else:
            messages = messages.copy()

        if system_override:
            # deduplicate: if there's already a system prompt, just update it, don't double up
            if messages and messages[0]["role"] == "system":
                messages[0] = {"role": "system", "content": system_override}
            else:
                messages.insert(0, {"role": "system", "content": system_override})

        # Ensure ONLY ONE system prompt exists at the start
        system_msgs = [m for m in messages if m.get("role") == "system"]
        if len(system_msgs) > 1:
            # Combine them or keep the newest override? Let's combine for safety.
            combined_content = "\n".join([m["content"] for m in system_msgs])
            # Filter out all system msgs and insert one at the top
            messages = [m for m in messages if m.get("role") != "system"]
            messages.insert(0, {"role": "system", "content": combined_content})

        # 1. Groq models FIRST to preserve Gemini free tier quota
        if self.groq_api_key:
            fallback_chain.append(
                "groq/llama-3.3-70b-versatile"
            )  # Best quality, verified
            fallback_chain.append(
                "groq/llama-3.1-8b-instant"
            )  # Fast fallback, verified

        # 2. Gemini models as fallback - using latest 2026 free-tier models
        if self.gemini_api_key:
            fallback_chain.append("gemini/gemini-2.5-flash")
            fallback_chain.append("gemini/gemini-2.5-pro")
            fallback_chain.append("gemini/gemini-2.0-flash")
            fallback_chain.append("gemini/gemini-2.0-flash-lite")
            fallback_chain.append("gemini/gemini-1.5-pro")

        # 3. Absolute final fallback
        if not fallback_chain:
            logger.warning("No API keys found! Chatbot will not work.")
            fallback_chain = [
                "groq/llama-3.3-70b-versatile"
            ]  # Will fail but gives clear error

        # Deduplicate while preserving order
        seen = set()
        unique_chain = [x for x in fallback_chain if not (x in seen or seen.add(x))]

        logger.info(f"Model fallback chain: {unique_chain}")

        errors_encountered = []
        max_retries_per_model = 3

        for model_name in unique_chain:
            logger.info(f"Attempting completion with model: {model_name}")

            retry_count = 0
            base_delay = 2.0

            while retry_count <= max_retries_per_model:
                try:
                    # Prepare completion arguments
                    completion_kwargs = {
                        "model": model_name,
                        "messages": messages,
                        "tools": tools,
                        "tool_choice": "auto" if tools else None,
                        "max_tokens": 512,  # Optimized for tokens
                        "temperature": 0.7,
                    }

                    # Explicitly pass API keys based on provider
                    if model_name.startswith("gemini/") and self.gemini_api_key:
                        completion_kwargs["api_key"] = self.gemini_api_key
                    elif model_name.startswith("groq/") and self.groq_api_key:
                        completion_kwargs["api_key"] = self.groq_api_key

                    response = await litellm.acompletion(**completion_kwargs)

                    if model_name != self.model:
                        logger.info(f"Silent switch: {self.model} -> {model_name}")

                    if response and response.choices:
                        msg = response.choices[0].message
                        if msg.content or (
                            hasattr(msg, "tool_calls") and msg.tool_calls
                        ):
                            return response

                    logger.warning(f"Model {model_name} returned empty response")
                    errors_encountered.append(f"{model_name}: Empty response")
                    break  # Try next model

                except Exception as e:
                    error_msg = str(e)

                    # Detect Quota/Rate Limit (429 / QuotaFailure)
                    if (
                        "429" in error_msg
                        or "quota" in error_msg.lower()
                        or "limit" in error_msg.lower()
                    ):
                        # 3. Parse retryDelay from Google's response (JSON or plain)
                        delay_match = re.search(
                            r'retryDelay"\s*:\s*"(\d+)s"', error_msg
                        ) or re.search(r"retryDelay:\s*(\d+)s", error_msg)
                        if delay_match:
                            retry_delay_secs = int(delay_match.group(1))
                            logger.error(
                                f"❌ Stop: Gemini Quota Exceeded. Google requested {retry_delay_secs}s wait."
                            )
                            # STOP THE STORM: Raise a specific exception that the API layer can catch
                            raise HTTPException(
                                status_code=429,
                                detail=f"Rate limited by Gemini free tier. Try again in {retry_delay_secs} seconds.",
                            )

                        if retry_count < max_retries_per_model:
                            delay = (base_delay * (2**retry_count)) + (
                                time.time() % 1.0
                            )  # Exp backoff + jitter
                            delay = min(delay, 60.0)
                            logger.warning(
                                f"⚠️ {model_name} rate limited. Retrying in {delay:.1f}s... (Attempt {retry_count + 1}/{max_retries_per_model})"
                            )
                            await asyncio.sleep(delay)
                            retry_count += 1
                            continue
                        else:
                            # Final retry failed
                            logger.error(
                                f"❌ {model_name} failed all {max_retries_per_model} retries."
                            )
                            # On quota failure, if no retryDelay was found, still try one fallback?
                            # User said: "When you see a Gemini QuotaFailure... do not switch models"
                            if "gemini" in model_name:
                                raise HTTPException(
                                    status_code=429,
                                    detail="Gemini quota exhausted. Please wait before next request.",
                                )

                            errors_encountered.append(
                                f"{model_name}: Rate limited. Use backup path."
                            )
                            break  # Try next model in fallback chain

        # If we get here, all credentialed models failed (Rate Limit or Auth)
        # 4. Ultimate Fallback: Pollinations AI (Unified API - Free with optional API key for no rate limits)
        logger.warning(
            "All primary models failed. Attempting ultimate fallback: Pollinations AI"
        )

        # Use single best model first (openai via Pollinations), only try backup if it fails
        pollinations_api_key = os.getenv(
            "POLLINATIONS_API_KEY"
        )  # Optional: sk_ key for no rate limits
        poll_model = os.getenv(
            "POLLINATIONS_MODEL", "openai"
        )  # Default to openai, configurable

        try:
            logger.info(f"Trying Pollinations model: {poll_model}")

            headers = {"Content-Type": "application/json"}
            if pollinations_api_key:
                headers["Authorization"] = f"Bearer {pollinations_api_key}"

            # Clean messages for Pollinations (it only likes role/content)
            clean_messages = []
            for m in messages:
                clean_msg = {"role": m["role"], "content": m.get("content", "") or ""}
                clean_messages.append(clean_msg)

            # Use the new unified OpenAI-compatible endpoint
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://text.pollinations.ai/openai",
                    headers=headers,
                    json={
                        "model": poll_model,
                        "messages": clean_messages,
                        "max_tokens": 512,  # Reduced for efficiency
                        "temperature": 0.7,
                    },
                    timeout=45.0,
                )

                if resp.status_code == 200:
                    try:
                        json_resp = resp.json()
                        text_out = (
                            json_resp.get("choices", [{}])[0]
                            .get("message", {})
                            .get("content", "")
                        )
                        if not text_out:
                            text_out = resp.text
                    except Exception:
                        text_out = resp.text

                    if text_out:
                        logger.info(f"✅ Pollinations AI ({poll_model}) success")

                        # Mock a LiteLLM response object
                        mock_resp = SimpleNamespace(
                            choices=[
                                SimpleNamespace(
                                    message=SimpleNamespace(
                                        content=text_out,
                                        role="assistant",
                                        tool_calls=None,
                                    )
                                )
                            ],
                            model=f"pollinations/{poll_model}",
                        )
                        return mock_resp
                else:
                    logger.warning(
                        f"Pollinations {poll_model} returned status {resp.status_code}"
                    )

        except Exception as poll_err:
            logger.warning(f"Pollinations {poll_model} failed: {poll_err}")

        # If even Pollinations failed
        error_summary = "; ".join(errors_encountered)
        logger.error(f"All models failed. Details: {error_summary}")

        # User-friendly message with specific diagnostics
        friendly_error = (
            "API Connection Error: All models failed. "
            f"Providers reported: {error_summary}. "
            "Please check your API keys and Render environment variables."
        )
        raise Exception(friendly_error)

    async def _execute_mcp_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Execute an MCP tool with safety gate and robust image fallback"""
        logger.info(f"DEBUG: _execute_mcp_tool -> tool='{tool_name}' args={arguments}")

        # 1. IMAGE GENERATION - Deterministic Chain: Gemini → Pollinations
        if tool_name == "generate_image":
            # ========== PROFESSIONAL HARDENING: Image Cooldown ==========
            time_since_last = time.time() - self._last_image_request
            if time_since_last < self._image_cooldown_seconds:
                wait_time = int(self._image_cooldown_seconds - time_since_last)
                logger.info(f"⏳ Image cooldown active, {wait_time}s remaining")
                return {
                    "error": f"Please wait {wait_time} seconds before requesting another image.",
                    "cooldown": True,
                }
            self._last_image_request = time.time()
            # ========== END PROFESSIONAL HARDENING ==========

            img_prompt = (arguments.get("prompt") or "").strip()
            if not img_prompt:
                logger.warning("⚠️ Image prompt missing in tool arguments.")
                return {"error": "Image prompt missing."}

            aspect_ratio = arguments.get("aspect_ratio", "1:1")

            # --- STEP 1: Gemini Image ---
            if self.gemini_image_client:
                logger.info("🎨 Trying provider: gemini")
                try:
                    res = await self.gemini_image_client.generate_image(
                        prompt=img_prompt, aspect_ratio=aspect_ratio
                    )
                    if res.get("success"):
                        logger.info("✅ Gemini success")
                        image_url = res.get("image_url")
                        if (
                            image_url
                            and not image_url.startswith("http")
                            and self.public_base_url
                        ):
                            image_url = f"{self.public_base_url}{image_url}"

                        return {
                            "image_url": image_url,
                            "image_base64": res.get("image_base64"),
                            "prompt": img_prompt,
                            "provider": "gemini",
                            "mime_type": res.get("mime_type", "image/png"),
                        }
                    logger.warning(f"Gemini failed: {res.get('error')}")
                except Exception as e:
                    logger.warning(f"Gemini failed: {e}")

            # --- STEP 2: Pollinations ---
            logger.info("🎨 Trying provider: pollinations")
            try:
                import urllib.parse

                encoded_prompt = urllib.parse.quote(img_prompt)
                poll_models = [os.getenv("POLLINATIONS_IMAGE_MODEL", "turbo"), "flux"]

                for p_model in poll_models:
                    logger.info(f"Trying Pollinations model: {p_model}")
                    for attempt in range(2):
                        try:
                            poll_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&seed={uuid.uuid4().int % 1000000}&nologo=true&model={p_model}"
                            async with httpx.AsyncClient() as client:
                                resp = await client.get(poll_url, timeout=30.0)
                                c_type = resp.headers.get("content-type", "").lower()
                                if resp.status_code == 200 and "image" in c_type:
                                    img_b64 = base64.b64encode(resp.content).decode(
                                        "utf-8"
                                    )

                                    # Save to static
                                    filename = f"pollin_{uuid.uuid4().hex[:8]}.jpg"
                                    local_path = Path("static/generated") / filename
                                    local_path.parent.mkdir(parents=True, exist_ok=True)
                                    with open(local_path, "wb") as f:
                                        f.write(resp.content)

                                    rel_url = f"/static/generated/{filename}"
                                    abs_url = (
                                        f"{self.public_base_url}{rel_url}"
                                        if self.public_base_url
                                        else rel_url
                                    )

                                    logger.info(f"✅ Pollinations success ({p_model})")
                                    return {
                                        "image_url": abs_url,
                                        "image_base64": img_b64,
                                        "prompt": img_prompt,
                                        "provider": "pollinations",
                                        "mime_type": "image/jpeg",
                                    }
                                else:
                                    logger.warning(
                                        f"Pollinations {p_model} non-image response: {resp.text[:100]}"
                                    )
                        except Exception as e:
                            logger.warning(f"Pollinations {p_model} exception: {e}")

                logger.warning("Pollinations failed: All models/attempts exhausted")
            except Exception as e:
                logger.warning(f"Pollinations overall failure: {e}")

            # Final log for verification (Acceptance Test 4)
            final_provider = (
                self._last_image_data.get("provider", "unknown")
                if self._last_image_data
                else "none"
            )
            url_type = "none"
            if self._last_image_data:
                if self._last_image_data.get("image_base64"):
                    url_type = "base64"
                elif self._last_image_data.get("image_url"):
                    img_url = str(self._last_image_data.get("image_url") or "")
                    url_type = "local" if "onrender.com" in img_url else "external"

            logger.info(
                f"📸 IMAGE REQUEST: provider={final_provider}, url_type={url_type}"
            )

            return {
                "error": "All image generation providers failed. Please try a different prompt or try again later."
            }

        # 2. STANDARD MCP TOOLS
        server_name, actual_tool_name = self.mcp_manager.parse_tool_call(tool_name)

        # Hugging Face MCP tools
        if any(
            tool_name.startswith(p) for p in ["hf.", "spaces.", "hub."]
        ) or server_name in ["hf", "huggingface"]:
            if not self.hf_client:
                return "Error: Hugging Face MCP client not initialized."
            return await self.hf_client.call_tool(actual_tool_name, arguments)

        # Generic MCP routing
        if not server_name:
            return f"Refused: Tool '{tool_name}' is not recognized."

        return await self.mcp_manager.call_tool(
            server_name, actual_tool_name, arguments
        )

    def print_available_tools(self) -> None:
        """Print all available MCP tools"""
        tools = self.mcp_manager.get_all_tools()
        if not tools:
            print("\n❌ No MCP tools available")
            return
        print(f"\n✅ Available MCP Tools ({len(tools)}):")
        for tool in tools:
            print(f"  🔧 {tool['name']} ({tool['server']})")
