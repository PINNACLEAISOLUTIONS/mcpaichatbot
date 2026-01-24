from mcp.server.fastmcp import FastMCP
from duckduckgo_search import DDGS
import logging

# Initialize FastMCP server
mcp = FastMCP("websearch")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@mcp.tool()
def search(query: str, max_results: int = 10) -> str:
    """
    Perform a web search using DuckDuckGo.

    Args:
        query: The search query string.
        max_results: Maximum number of results to return (default: 10).
    """
    logger.info(f"Executing search for: {query}")
    try:
        results = []
        with DDGS() as ddgs:
            # text() method is the standard for web search
            # It returns a list of dictionaries in the newest version
            ddgs_results = ddgs.text(query, max_results=max_results)
            if ddgs_results:
                for r in ddgs_results:
                    results.append(r)

        if not results:
            return "No web search results found. Please answer from your general knowledge."

        # Format results as markdown
        formatted = f"### Web Search Results for '{query}'\n\n"
        for i, r in enumerate(results, 1):
            title = r.get("title", "No Title")
            link = r.get("href", r.get("link", "#"))
            body = r.get("body", r.get("snippet", ""))
            formatted += f"{i}. **[{title}]({link})**\n   {body}\n\n"

        return formatted

    except Exception as e:
        logger.error(f"Search failed: {e}")
        # Return as tool failure message so LLM knows to fallback
        return f"Tool Error: Web search failed ({str(e)}). Please proceed using your internal knowledge if possible."


if __name__ == "__main__":
    mcp.run()
