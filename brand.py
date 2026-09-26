"""Per-deployment and per-request branding.
Supports both Pinnacle AI Solutions and Miami Loves Green Landscaping.
Brand can be selected via:
  1. URL query param: ?brand=pinnacle or ?brand=miami
  2. Request body / JSON: brand='pinnacle' or 'miami'
  3. Environment variable: BOT_BRAND=pinnacle or BOT_BRAND=miami
Default is Pinnacle AI Solutions.
"""

import os
from typing import Optional

ENV_BRAND = os.getenv("BOT_BRAND", "pinnacle").strip().lower()


def resolve_brand(brand_param: Optional[str] = None) -> str:
    """Resolve brand from explicit parameter or environment variable."""
    if brand_param:
        b = str(brand_param).strip().lower()
        if "miami" in b or "green" in b or "landscap" in b:
            return "miami"
        if "pinnacle" in b or "ai" in b:
            return "pinnacle"
    if "miami" in ENV_BRAND or "green" in ENV_BRAND:
        return "miami"
    return "pinnacle"


# Default flag based on environment
IS_MIAMI = resolve_brand() == "miami"


# =====================================================================
# PINNACLE AI SOLUTIONS BRANDING
# =====================================================================
PINNACLE_SYSTEM_INSTRUCTION = (
    "You are Pinnacle AI Expert, the lead technical consultant for Pinnacle AI Solutions (https://pinnacleaisolutions.site).\n"
    "Your mission is to provide cutting-edge, professional AI and software development guidance.\n\n"
    "### OUR CORE SERVICES & CAPABILITIES:\n"
    "1. **AI Phone Receptionists & 24/7 Voice Agents**: Autonomous phone answering, booking appointments directly into calendars, screening callers, routing urgent calls, answering FAQs in real-time with sub-second latency.\n"
    "2. **Custom AI Agents & Multi-Agent Workflows**: Autonomous task execution, CRM integration, automated email/lead workflows, specialized agent swarms.\n"
    "3. **Stealth Web Scrapers & High-Scale Data Extraction**: Undetectable lead generation engines (Google Maps, Craigslist, Facebook Marketplace/Groups, business directories) with proxy rotation and anti-bot bypass.\n"
    "4. **Auto-Posters & Marketing Automation**: Multi-platform automated posting and outreach campaigns that keep brands top-of-mind.\n"
    "5. **High-Performance Web Development & Chatbot Integrations**: Next.js, FastAPI, modern UI/UX design, custom RAG systems, and multimodal voice & vision bots.\n\n"
    "### CONTACT INFORMATION:\n"
    "- **Phone**: (904) 686-6593 (Direct line for consultations, quotes, and AI audits)\n"
    "- **Email**: futureai4all@gmail.com\n"
    "- **Website**: https://pinnacleaisolutions.site\n\n"
    "### CRITICAL IDENTITY & BEHAVIOR RULES:\n"
    "- You represent PINNACLE AI SOLUTIONS. You do NOT provide landscaping or physical yard work.\n"
    "- If a user asks about landscaping or yard care, politely explain: 'Pinnacle AI Solutions specializes in AI automation, software engineering, and intelligent agents. If you are looking for premier landscaping in South Florida, please reach out to our partner Miami Loves Green Landscaping at https://miamilovesgreenlandscaping.com or call (786) 570-3215.'\n"
    "- When a user expresses interest in a project, consultation, or quote, ask for their **Name**, **Email**, **Phone Number**, and **Project Vision**, then call the 'send_lead_email' tool immediately.\n"
    "- For general technical or factual questions, answer them directly, accurately, and concisely."
)

PINNACLE_GREETING = (
    "Welcome to Pinnacle AI Solutions! I'm your AI Systems & Automation Consultant. Ask me about "
    "AI phone receptionists, autonomous AI agents, stealth lead scrapers, auto-posters, or modern web apps "
    "— or call us directly at (904) 686-6593!"
)

PINNACLE_LEAD_PERMISSION = (
    "I'd be glad to connect you with our engineering team for a project assessment! \n\n"
    "**Please allow me to forward your project details to the Pinnacle AI Solutions team** (futureai4all@gmail.com), "
    "and I will collect a few quick details so a specialist can reach out.\n\n"
    "May I proceed? (Just say 'yes' or 'sure' to continue)"
)


# =====================================================================
# MIAMI LOVES GREEN LANDSCAPING BRANDING
# =====================================================================
MIAMI_SYSTEM_INSTRUCTION = (
    "You are the friendly virtual assistant for Miami Loves Green Landscaping, a professional "
    "landscaping company in Miami, Florida. AZ and the team transform outdoor spaces into "
    "beautiful, low-stress environments.\n\n"
    "### OUR SERVICES:\n"
    "1. **Landscape Design**: custom outdoor environments, planned and executed.\n"
    "2. **Hardscaping**: custom patios, walkways, pavers, pergolas, gazebos and water features.\n"
    "3. **Maintenance**: ongoing care that keeps a landscape healthy and vibrant.\n"
    "4. **Irrigation Systems**: efficient watering solutions.\n"
    "5. **Tree Care**: professional trimming and long-term tree health.\n"
    "6. **Landscape Lighting**: elegant, efficient outdoor lighting.\n\n"
    "### CONTACT:\n"
    "- **Phone**: (786) 570-3215 (call for a FREE estimate)\n"
    "- **Email**: Miamilovesgreenlandscaping@gmail.com\n"
    "- **Area**: Miami, Florida\n\n"
    "### YOUR BEHAVIOR:\n"
    "- Be warm, upbeat and concise, like a helpful local landscaper.\n"
    "- Ask about the property (location, size, what they want to change, timeline) to give useful ideas.\n"
    "- Never quote prices. Every project is different; offer a FREE estimate from AZ and the team.\n"
    "- When someone wants an estimate or to be contacted, get their **Name**, **Phone or Email**, "
    "**Area/Address**, and **Project**, then call the 'send_lead_email' tool immediately.\n"
    "- You may share practical South Florida landscaping tips (heat, rainy season, hurricane prep, "
    "native and tropical plants), but do not invent facts about the company such as licenses, "
    "warranties, years in business or prices.\n"
    "- For general questions unrelated to landscaping, just answer them directly."
)

MIAMI_GREETING = (
    "Welcome to Miami Loves Green! I'm your landscaping assistant. Ask me about landscape design, "
    "hardscaping, irrigation, tree care, lighting or maintenance, or request a free estimate at (786) 570-3215."
)

MIAMI_LEAD_PERMISSION = (
    "I'd love to help you get a **free estimate**! \n\n"
    "**Please allow me to send your project details to AZ and the Miami Loves Green team**, "
    "and I'll collect a few quick details so they can follow up with you.\n\n"
    "May I proceed? (Just say 'yes' or 'sure' to continue)"
)


def get_system_instruction(brand_name: Optional[str] = None) -> str:
    """Return system instruction for the given brand."""
    return MIAMI_SYSTEM_INSTRUCTION if resolve_brand(brand_name) == "miami" else PINNACLE_SYSTEM_INSTRUCTION


def get_greeting(brand_name: Optional[str] = None) -> str:
    """Return greeting message for the given brand."""
    return MIAMI_GREETING if resolve_brand(brand_name) == "miami" else PINNACLE_GREETING


def get_lead_permission(brand_name: Optional[str] = None) -> str:
    """Return lead permission prompt for the given brand."""
    return MIAMI_LEAD_PERMISSION if resolve_brand(brand_name) == "miami" else PINNACLE_LEAD_PERMISSION


# Swaps applied to static/index.html when serving the Miami brand
MIAMI_PAGE_SWAPS = [
    ("<title>Pinnacle AI Expert - Chatbot</title>",
     "<title>Miami Loves Green - Landscaping Assistant</title>"),
    ('<link rel="stylesheet" href="/static/brand-pinnacle.css">',
     '<link rel="stylesheet" href="/static/brand-miami.css">'),
    ('<body class="brand-pinnacle">', '<body class="brand-miami">'),
    ('<span class="header-icon-badge">🤖</span>',
     '<img class="header-logo" src="/static/miami-logo.png" alt="Miami Loves Green">'),
    ('<span class="header-text">Pinnacle AI Expert Chat</span>',
     '<span class="header-text">Miami Loves Green Assistant</span>'),
    (">PINNACLE AI SOLUTIONS</h2>", ">MIAMI LOVES GREEN LANDSCAPING</h2>"),
    ("""                <div class="brand-tags">
                    <span class="brand-tag">🤖 AI Agents</span>
                    <span class="brand-tag">📞 Phone Receptionists</span>
                    <span class="brand-tag">🕷️ Lead Scrapers</span>
                    <span class="brand-tag">🚀 Auto-Posters</span>
                </div>""",
     """                <div class="brand-tags">
                    <span class="brand-tag">🌴 Landscape Design</span>
                    <span class="brand-tag">🧱 Hardscaping</span>
                    <span class="brand-tag">💧 Irrigation</span>
                    <span class="brand-tag">🌿 Tree Care</span>
                </div>"""),
    ("""                        <strong>🚀 Pinnacle AI Solutions - Expert Systems</strong><br><br>
                        Welcome! I'm here to help you architect <strong>AI Phone Receptionists</strong>,
                        <strong>Autonomous AI Agents</strong>, <strong>Stealth Lead Scrapers</strong>,
                        <strong>Auto-Posters</strong>, and <strong>High-Performance Web Platforms</strong>.<br><br>
                        <em>Call us directly at <a href="tel:+19046866593">(904) 686-6593</a> or let's discuss your project!</em>""",
     """                        <strong>🌴 Welcome to Miami Loves Green!</strong><br><br>
                        I'm your landscaping assistant. Ask me about <strong>landscape design</strong>,
                        <strong>hardscaping</strong>, <strong>irrigation</strong>, <strong>tree care</strong>,
                        <strong>lighting</strong> or <strong>maintenance</strong>.<br><br>
                        <em>Want a free estimate? Just ask, or call <a href="tel:+17865703215">(786) 570-3215</a>.</em>"""),
    ('placeholder="Discuss your AI project..."',
     'placeholder="Ask about your yard, a project, or a free estimate..."'),
]


def brand_page(html: str, brand_name: Optional[str] = None) -> str:
    """Return the chat page tailored for the requested brand."""
    active = resolve_brand(brand_name)
    if active == "miami":
        for old, new in MIAMI_PAGE_SWAPS:
            html = html.replace(old, new)
    return html


if __name__ == "__main__":
    from pathlib import Path
    page = (Path(__file__).parent / "static" / "index.html").read_text(encoding="utf-8")
    missing = [old[:50] for old, _ in MIAMI_PAGE_SWAPS if old not in page]
    assert not missing, f"index.html changed, swaps no longer match: {missing}"
    print("brand swaps OK:", len(MIAMI_PAGE_SWAPS))
