"""Setup script to help configure the MCP chatbot"""

import os
import sys
from pathlib import Path


def create_env_file():
    """Create .env file from template if it doesn't exist"""
    env_example = Path(".env.example")
    env_file = Path(".env")

    if env_file.exists():
        print("✅ .env file already exists")
        return

    if not env_example.exists():
        print("❌ .env.example not found")
        return

    # Copy template
    with open(env_example, "r") as f:
        content = f.read()

    print("\n🔧 Setting up environment variables...")
    print("=" * 60)

    # Ask for Gemini API key
    print("\n📝 Please enter your Google Gemini API key")
    print("   (Get one from: https://makersuite.google.com/app/apikey)")
    api_key = input("   API Key: ").strip()

    if api_key:
        content = content.replace("your_gemini_api_key_here", api_key)

    # Write .env file
    with open(env_file, "w") as f:
        f.write(content)

    print("\n✅ Created .env file successfully!")
    print(f"   Location: {env_file.absolute()}")


def check_dependencies():
    """Check if required dependencies are installed"""
    print("\n🔍 Checking Python dependencies...")
    print("=" * 60)

    required = {
        "mcp": "mcp",
        "google.generativeai": "google-generativeai",
        "dotenv": "python-dotenv",
    }

    missing = []

    for module, package in required.items():
        try:
            __import__(module)
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package} - NOT INSTALLED")
            missing.append(package)

    if missing:
        print(f"\n⚠️  Missing {len(missing)} package(s)")
        print("\nTo install missing packages, run:")
        print(f"   pip install {' '.join(missing)}")
        return False
    else:
        print("\n✅ All Python dependencies are installed!")
        return True


def check_node():
    """Check if Node.js is installed (needed for filesystem server)"""
    print("\n🔍 Checking Node.js installation...")
    print("=" * 60)

    import subprocess

    try:
        result = subprocess.run(
            ["node", "--version"], capture_output=True, text=True, timeout=5
        )

        if result.returncode == 0:
            version = result.stdout.strip()
            print(f"✅ Node.js is installed: {version}")
            return True
        else:
            print("❌ Node.js not found")
            return False
    except Exception as e:
        print(f"❌ Node.js not found: {e}")
        print("\n💡 Node.js is required for the filesystem MCP server")
        print("   Download from: https://nodejs.org/")
        return False


def main():
    """Main setup function"""
    print("\n" + "=" * 60)
    print("🚀 MCP Chatbot Setup")
    print("=" * 60)

    # Check current directory
    if not Path("mcp_config.json").exists():
        print("\n⚠️  Warning: mcp_config.json not found in current directory")
        print("   Make sure you're running this from the project root")
        print(f"   Current directory: {Path.cwd()}")

        response = input("\nContinue anyway? (y/n): ").strip().lower()
        if response != "y":
            print("Setup cancelled")
            return

    # Create .env file
    create_env_file()

    # Check dependencies
    deps_ok = check_dependencies()

    # Check Node.js
    node_ok = check_node()

    # Summary
    print("\n" + "=" * 60)
    print("📋 Setup Summary")
    print("=" * 60)

    if deps_ok and node_ok:
        print("\n✅ All checks passed! You're ready to run the chatbot.")
        print("\n🚀 To start the chatbot, run:")
        print("   cd src")
        print("   python app.py")
    else:
        print("\n⚠️  Some checks failed. Please address the issues above.")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nSetup cancelled by user")
        sys.exit(0)
