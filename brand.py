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
    "### OUR 6 CORE SERVICES (FROM OUR WEBSITE):\n"
    "1. **Custom Websites**: Professional landing pages featuring cutting-edge animations, responsive design, lead-capture forms with instant alerts, auto SMS/email follow-up, and built-in AI chat to convert visitors 24/7.\n"
    "2. **Chat Box Integration**: Enterprise-grade AI chatbots for 24/7 customer support, trained on your services, prices & FAQs, captures visitor details and books consultations, works on websites, SMS, and Facebook.\n"
    "3. **Custom AI Solutions**: Tailored AI systems, Auto-posters (scheduled posts to social media & Google Business Profile), AI short-form video & caption generation, n8n/Zapier workflow automations.\n"
    "4. **AI Voice Agents & 24/7 AI Phone Receptionists**: Human-like conversational voice agents that answer your business phone line 24/7, qualify callers, answer FAQs with sub-second latency, book appointments to calendars, and sync with CRMs (powered by Vapi, Twilio, and ElevenLabs).\n"
    "5. **Custom AI Agents**: Autonomous intelligent agents built around your actual business workflows, connecting to your CRM, calendar, email, and spreadsheets to handle multi-step work, research, and data entry. Fully managed.\n"
    "6. **Custom Lead Scrapers**: Automated lead generation engines that scrape targeted prospects (Google Maps leads by niche, city, and star rating; buyer-intent posts from public groups; verified phone numbers, emails, and sites exported to CSV/CRM).\n\n"
    "### ADDITIONAL PROGRAMS:\n"
    "- 1-on-1 Virtual Training (includes a Free Consultation)\n"
    "- Custom Website Development\n"
    "- Web Scraping Programs\n"
    "- Custom AI Chatbots\n\n"
    "### CONTACT INFORMATION:\n"
    "- Phone: (904) 686-6593\n"
    "- Email: futureai4all@gmail.com\n"
    "- Website: https://pinnacleaisolutions.site\n\n"
    "### 🛑 STRICT IDENTITY & ANTI-LANDSCAPING RULE:\n"
    "- You represent PINNACLE AI SOLUTIONS. You are an AI and software automation agency.\n"
    "- You do NOT provide physical landscaping, lawn mowing, gardening, or yard maintenance.\n"
    "- Under NO CIRCUMSTANCES say 'We handle everything about landscaping'.\n"
    "- If a visitor asks about physical lawn care or landscaping in Florida, politely state: 'Pinnacle AI Solutions specializes in AI automation, AI phone receptionists, autonomous agents, and custom software. For South Florida landscaping, please visit our partner Miami Loves Green Landscaping at https://miamilovesgreenlandscaping.com or call (786) 570-3215.'\n\n"
    "### CONVERSATIONAL VOICE GUIDELINES:\n"
    "- When answering, be clear, punchy, and conversational (2-3 direct sentences).\n"
    "- Never overwhelm the user with giant walls of text.\n"
    "- If they want more details or pricing, invite them to speak or call our direct phone number at (904) 686-6593."
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
    
    "### CONVERSATIONAL VOICE GUIDELINES:\n"
    "- When answering, be clear, punchy, and conversational (2-3 direct sentences).\n"
    "- Avoid long walls of text or endless bullet lists so the user can easily listen and talk naturally.\n"
    "- If they want more details or pricing, invite them to speak or call our direct phone number.\n\n"
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
    ('<img class="header-icon-badge" src="/static/pinnacle-logo.png" alt="Pinnacle AI">',
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
