"""Per-deployment branding. The same code runs several Render services; set
BOT_BRAND=miami on the Miami Loves Green service. Unset = Pinnacle (unchanged)."""

import os

BRAND = os.getenv("BOT_BRAND", "pinnacle").strip().lower()
IS_MIAMI = BRAND == "miami"

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
    "hardscaping, irrigation, tree care, lighting or maintenance, or request a free estimate."
)

MIAMI_LEAD_PERMISSION = (
    "I'd love to help you get a **free estimate**! \n\n"
    "**Please allow me to send your project details to AZ and the Miami Loves Green team**, "
    "and I'll collect a few quick details so they can follow up with you.\n\n"
    "May I proceed? (Just say 'yes' or 'sure' to continue)"
)

# (old, new) swaps applied to static/index.html when serving the Miami brand
MIAMI_PAGE_SWAPS = [
    ("<title>Pinnacle AI Expert - Chatbot</title>",
     "<title>Miami Loves Green - Landscaping Assistant</title>"),
    ('<link rel="stylesheet" href="/static/style.css">',
     '<link rel="stylesheet" href="/static/style.css">\n'
     '    <link rel="stylesheet" href="/static/brand-miami.css">'),
    ("<body>", '<body class="brand-miami">'),
    ('<span class="logo-icon">🚀</span>',
     '<img class="brand-logo" src="/static/miami-logo.png" alt="Miami Loves Green Landscaping">'),
    ('<h1 class="logo-3d">Pinnacle AI<br><span class="subtitle">Expert Systems</span></h1>',
     '<h1 class="logo-3d">Miami Loves Green<br><span class="subtitle">Landscaping</span></h1>'),
    ('<span class="header-text">Pinnacle AI Expert Chat</span>',
     '<img class="header-logo" src="/static/miami-logo.png" alt="Miami Loves Green">'
     '<span class="header-text">Miami Loves Green Assistant</span>'),
    (">PINNACLE AI SOLUTIONS</h2>", ">MIAMI LOVES GREEN LANDSCAPING</h2>"),
    ("""                        <strong>🚀 Pinnacle AI Expert Systems</strong><br><br>
                        Welcome! I'm here to help you architect <strong>Elite AI Agents</strong>,
                        <strong>Stealthy Scrapers</strong>, and <strong>Scalable Web Applications</strong>.<br><br>
                        <em>Ready to transform your business with AI? Let's discuss your project!</em>""",
     """                        <strong>🌴 Welcome to Miami Loves Green!</strong><br><br>
                        I'm your landscaping assistant. Ask me about <strong>landscape design</strong>,
                        <strong>hardscaping</strong>, <strong>irrigation</strong>, <strong>tree care</strong>,
                        <strong>lighting</strong> or <strong>maintenance</strong>.<br><br>
                        <em>Want a free estimate? Just ask, or call <a href="tel:+17865703215">(786) 570-3215</a>.</em>"""),
    ('placeholder="Discuss your AI project..."',
     'placeholder="Ask about your yard, a project, or a free estimate..."'),
]


def brand_page(html: str) -> str:
    """Return the chat page for this deployment's brand."""
    if not IS_MIAMI:
        return html
    for old, new in MIAMI_PAGE_SWAPS:
        html = html.replace(old, new)
    return html


if __name__ == "__main__":
    # Self-check: every swap must match the real page, or Miami would show Pinnacle text.
    from pathlib import Path

    page = (Path(__file__).parent / "static" / "index.html").read_text(encoding="utf-8")
    missing = [old[:50] for old, _ in MIAMI_PAGE_SWAPS if old not in page]
    assert not missing, f"index.html changed, swaps no longer match: {missing}"
    print("brand swaps OK:", len(MIAMI_PAGE_SWAPS))
