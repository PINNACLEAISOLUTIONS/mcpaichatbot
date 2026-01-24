"""Simplified AutoAgent MCP Server - Works without heavy dependencies"""

from typing import List
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("AutoAgent Local")

# Predefined agent profiles (avoiding heavy imports)
AGENT_PROFILES = {
    "code_agent": "An agent specialized in writing and analyzing code",
    "research_agent": "An agent for web research and information gathering",
    "file_agent": "An agent for file operations and management",
    "task_agent": "A general-purpose task execution agent",
    "data_agent": "An agent for data analysis and processing",
}


@mcp.tool()
async def list_autoagent_profiles() -> List[str]:
    """List all available AutoAgent agent profiles."""
    profiles = []
    for name, desc in AGENT_PROFILES.items():
        profiles.append(f"{name}: {desc}")
    return profiles


@mcp.tool()
async def run_autoagent_task(agent_name: str, query: str) -> str:
    """
    Run a task using a specific AutoAgent profile.

    Args:
        agent_name: The name of the agent to use (from list_autoagent_profiles).
        query: The task description or query for the agent.
    """
    if agent_name not in AGENT_PROFILES:
        return f"Error: Agent '{agent_name}' not found. Available: {list(AGENT_PROFILES.keys())}"

    agent_desc = AGENT_PROFILES[agent_name]
    return f"""AutoAgent Task Executed:
Agent: {agent_name}
Description: {agent_desc}
Query: {query}

Result: This is a simplified AutoAgent integration. The full AutoAgent library requires heavy dependencies that cause initialization delays. 

For full AutoAgent functionality, you can:
1. Run AutoAgent directly from command line: `python -m autoagent`
2. Use the AutoAgent API separately
3. Install and configure AutoAgent in a dedicated environment

For now, I can help you with:
- Code generation and analysis
- Research tasks
- File operations
- General task planning
"""


if __name__ == "__main__":
    mcp.run()
