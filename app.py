"""Main application entry point for MCP-Integrated Chatbot"""

import asyncio
import sys
import logging
from pathlib import Path
from mcp_client_manager import MCPClientManager
from chatbot import MCPChatbot

from hf_inference_client import HFInferenceClient
from pollinations_client import PollinationsImageClient

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def main():
    """Main application function"""
    print("\n" + "=" * 70)
    print("🤖 MCP-Integrated AI Chatbot")
    print("=" * 70)

    # Get the project root directory
    project_root = Path(__file__).parent.parent
    config_path = project_root / "mcp_config.json"

    print(f"\n📁 Project directory: {project_root}")
    print(f"⚙️  Loading configuration from: {config_path}")

    # Initialize MCP Client Manager
    mcp_manager = MCPClientManager(config_path=str(config_path))

    try:
        # Load configuration
        await mcp_manager.load_config()

        # Connect to MCP servers
        print("\n🔌 Connecting to MCP servers...")
        await mcp_manager.connect_to_servers()

        # Initialize Clients
        print("\n🎨 Initializing Image Generation Clients...")

        # Initialize HF Inference Client (Required for routing)
        hf_inference = HFInferenceClient()
        await hf_inference.start()

        # Initialize Pollinations Client (Unlimited free images)
        pollinations_client = PollinationsImageClient()
        await pollinations_client.start()

        # Initialize chatbot
        print("\n🚀 Initializing chatbot...")
        chatbot = MCPChatbot(mcp_manager)

        # Inject clients
        chatbot.hf_inference = hf_inference
        chatbot.pollinations_client = pollinations_client

        # Print available tools
        chatbot.print_available_tools()

        # Start interactive chat
        print("\n💬 Chat started! Type 'quit', 'exit', or 'bye' to exit.")
        print("=" * 70 + "\n")

        while True:
            try:
                # Get user input
                user_input = input("You: ").strip()

                if not user_input:
                    continue

                # Check for exit commands
                if user_input.lower() in ["quit", "exit", "bye", "q"]:
                    print("\n👋 Goodbye!")
                    break

                # Special commands
                if user_input.lower() == "tools":
                    chatbot.print_available_tools()
                    continue

                # Send message to chatbot
                response = await chatbot.send_message(user_input)
                print(f"\n🤖 Assistant: {response}\n")

            except KeyboardInterrupt:
                print("\n\n👋 Chat interrupted. Goodbye!")
                break
            except Exception as e:
                logger.error(f"Error processing message: {e}", exc_info=True)
                print(f"\n❌ Error: {e}\n")

    except FileNotFoundError:
        print(f"\n❌ Error: Configuration file not found at {config_path}")
        print("Please create mcp_config.json with your MCP server configurations.")
        sys.exit(1)
    except ValueError as e:
        print(f"\n❌ Error: {e}")
        print("Please check your .env file and ensure GEMINI_API_KEY is set.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)
    finally:
        # Cleanup
        print("\n🧹 Cleaning up...")
        await mcp_manager.disconnect_all()
        print("✅ Disconnected from all MCP servers")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Application terminated by user")
        sys.exit(0)
