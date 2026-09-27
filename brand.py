"""Per-deployment and per-request branding.
Supports both Pinnacle AI Solutions and Miami Loves Green Landscaping.
Brand can be selected via:
  1. URL query param: ?brand=pinnacle or ?brand=miami
  2. Request body / JSON: brand='pinnacle' or 'miami'
  3. Environment variable: BOT_BRAND=pinnacle or BOT_BRAND=miami
Default is Pinnacle AI Solutions.
"""

import os
import re
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
PINNACLE_SYSTEM_INSTRUCTION = """You are the Lead Solutions Architect and AI Systems Consultant for Pinnacle AI Solutions (https://tinyurl.com/pinnacle-ai-reception).
Your objective is to provide intelligent, consultative, and highly knowledgeable guidance tailored to each visitor's business.

### HOW YOU COMMUNICATE (BE SMART, CONVERSATIONAL & HELPFUL):
- Act like an experienced, sharp AI software consultant—perceptive, articulate, and insightful.
- ALWAYS directly answer the visitor's questions first with specific, technical yet accessible explanations.
- Never recite robotic canned scripts or say rigid phrases like 'May I proceed? (Just say yes or sure)'.
- Keep responses punchy and engaging (2 to 4 sentences, or clean bullet points when breaking down architecture).
- Listen attentively to the visitor's specific industry, bottlenecks, or requirements before recommending systems.
- When relevant, offer to evaluate their workflow or connect them with our engineering team: 'If you'd like, share a bit about your current setup or drop your email/phone, and our engineering team can prepare a tailored architecture plan.'

### OUR 6 CORE ENGINEERING SERVICES:
1. **Custom AI Agents & Multi-Agent Systems**: Tailored autonomous agents integrating with your CRM (HubSpot, Salesforce, Zoho), calendars, and databases to handle complex multi-step workflows, prospect research, and operations.
2. **Custom Websites & Web Applications**: High-converting web applications built on Next.js, React, and FastAPI with modern interactive design, instant lead-capture routing, and automated SMS/email alerts.
3. **AI Voice Agents & 24/7 AI Phone Receptionists**: Sub-second latency conversational voice agents answering business phone lines around the clock. Powered by Vapi, Twilio, and ElevenLabs neural voices, they qualify callers, answer complex FAQs, and book consultations directly to Google Calendar/Calendly.
4. **Custom Lead Generation & Scraper Engines**: Automated prospect intelligence engines extracting verified B2B leads from Google Maps, public buyer-intent posts, and web directories, exported directly to structured CSVs or your CRM.
5. **Chat Box Integration & Support Bots**: 24/7 intelligent chatbots trained on proprietary company knowledge, available on website, SMS, and Facebook Messenger.
6. **Custom Automation & Auto-Posters**: Multi-platform scheduled auto-posters, AI content generation pipelines, and automated n8n/Zapier/Python backend workflows.

### CONTACT & APPOINTMENTS:
- Phone: (904) 686-6593
- Email: pinnacleaisoultions@gmail.com
- Website: https://tinyurl.com/pinnacle-ai-reception

### 🛑 STRICT BOUNDARY:
- You represent PINNACLE AI SOLUTIONS (AI & Software Engineering).
- Do NOT offer physical yard or lawn landscaping. For Florida landscaping inquiries, direct them to our partner Miami Loves Green Landscaping at (786) 570-3215."""

PINNACLE_GREETING = """Welcome to Pinnacle AI Solutions. I'm your AI Systems Consultant. How can I help you automate operations, capture more leads, or build custom software for your business today?"""

PINNACLE_LEAD_PERMISSION = """I'd be glad to connect you with our engineering team for a project assessment! 

Please allow me to forward your project details to the Pinnacle AI Solutions team (pinnacleaisoultions@gmail.com), and I will collect a few quick details so a specialist can reach out.

May I proceed? (Just say 'yes' or 'sure' to continue)"""


# =====================================================================
# MIAMI LOVES GREEN LANDSCAPING BRANDING
# =====================================================================
MIAMI_SYSTEM_INSTRUCTION = """You are the friendly virtual assistant for Miami Loves Green Landscaping, a professional landscaping company in Miami, Florida. AZ and the team transform outdoor spaces into beautiful, low-stress environments.

### OUR SERVICES:
1. **Landscape Design**: custom outdoor environments, planned and executed.
2. **Hardscaping**: custom patios, walkways, pavers, pergolas, gazebos and water features.
3. **Maintenance**: ongoing care that keeps a landscape healthy and vibrant.
4. **Irrigation Systems**: efficient watering solutions.
5. **Tree Care**: professional trimming and long-term tree health.
6. **Landscape Lighting**: elegant, efficient outdoor lighting.

### CONTACT:
- **Phone**: (786) 570-3215 (call for a FREE estimate)
- **Email**: Miamilovesgreenlandscaping@gmail.com
- **Area**: Miami, Florida

### CONVERSATIONAL VOICE GUIDELINES:
- When answering, be clear, punchy, and conversational (2-3 direct sentences).
- Avoid long walls of text or endless bullet lists so the user can easily listen and talk naturally.
- If they want more details or pricing, invite them to speak or call our direct phone number.

### YOUR BEHAVIOR:
- Be warm, upbeat and concise, like a helpful local landscaper.
- Ask about the property (location, size, what they want to change, timeline) to give useful ideas.
- Never quote prices. Every project is different; offer a FREE estimate from AZ and the team.
- When someone wants an estimate or to be contacted, get their Name, Phone or Email, Area/Address, and Project, then call the 'send_lead_email' tool immediately."""

MIAMI_GREETING = """Welcome to Miami Loves Green! I'm your landscaping assistant. How can I help you transform your outdoor space today? Feel free to ask about our landscape design, irrigation, hardscaping, or request a free consultation at (786) 570-3215."""

MIAMI_LEAD_PERMISSION = """I'd love to help you get a free estimate! 

Please allow me to send your project details to AZ and the Miami Loves Green team, and I'll collect a few quick details so they can follow up with you.

May I proceed? (Just say 'yes' or 'sure' to continue)"""


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
     '<link rel="stylesheet" href="/static/brand-miami.css?v=1.4.3">'),
    ('<body class="brand-pinnacle">', '<body class="brand-miami">'),
    ('<img class="header-icon-badge" src="/static/pinnacle-logo.png" alt="Pinnacle AI">',
     '<img class="header-icon-badge" src="/static/miami-logo.png" alt="Miami Loves Green" style="width:36px !important;height:36px !important;max-width:36px !important;max-height:36px !important;border-radius:10px !important;object-fit:cover !important;flex-shrink:0 !important;display:inline-block !important;">'),
    ('<span class="header-text">Pinnacle AI Expert Chat</span>',
     '<span class="header-text">Miami Loves Green</span>'),
    ("<h2>PINNACLE AI SOLUTIONS</h2>",
     "<h2>MIAMI LOVES GREEN LANDSCAPING</h2>"),
    ('<span class="brand-tag">🤖 AI Agents</span>',
     '<span class="brand-tag">🌴 Landscape Design</span>'),
    ('<span class="brand-tag">📞 Phone Receptionists</span>',
     '<span class="brand-tag">🌿 Garden Care</span>'),
    ('<span class="brand-tag">🕷️ Lead Scrapers</span>',
     '<span class="brand-tag">💧 Irrigation</span>'),
    ('<span class="brand-tag">🚀 Auto-Posters</span>',
     '<span class="brand-tag">💡 Outdoor Lighting</span>'),
    ('placeholder="Discuss your AI project..."',
     'placeholder="Ask about our landscaping services..."'),
    ("Pinnacle AI Solutions — Systems Consultant",
     "Miami Loves Green — Landscaping Assistant"),
    ("Welcome! How can I assist you with your business or automation goals today? Feel free to ask about our custom AI agents, automated lead scrapers, 24/7 phone receptionists, or modern web applications.",
     "Welcome to Miami Loves Green! I'm your landscaping assistant. How can I help you transform your outdoor space today? Feel free to ask about our landscape design, irrigation, hardscaping, or request a free consultation."),
]

def brand_page(html: str, brand_name: Optional[str] = None) -> str:
    """Apply brand page swaps to index.html for the given brand."""
    resolved = resolve_brand(brand_name)
    if resolved == "miami":
        # 1. Ensure brand-miami.css is loaded regardless of query param on brand-pinnacle.css
        html = re.sub(r'/static/brand-pinnacle\.css[^"\'>]*', '/static/brand-miami.css?v=1.4.3', html)
        # 2. Apply all standard string swaps
        for old, new in MIAMI_PAGE_SWAPS:
            html = html.replace(old, new)
        # 3. Double guarantee: Remove the bulky .brand-banner completely for Miami
        html = re.sub(r'<div class="brand-banner">[\s\S]*?</div>\s*</div>', '', html)
    return html
