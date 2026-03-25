import argparse
import uvicorn


def main():
    parser = argparse.ArgumentParser(
        description="Shipyard - Ship Requirements & MBSE Platform"
    )
    parser.add_argument("--web", action="store_true", help="Start web server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--setup", action="store_true", help="Run setup wizard")
    args = parser.parse_args()

    if args.setup:
        _run_setup()
    elif args.web:
        _start_web(args.host, args.port)
    else:
        parser.print_help()


def _start_web(host: str, port: int):
    import webbrowser
    url = f"http://{host}:{port}"
    print(f"Starting Shipyard at {url}")
    webbrowser.open(url)
    uvicorn.run("src.web.app:app", host=host, port=port, reload=False)


def _run_setup():
    from pathlib import Path
    from src.core.config import CWD

    env_path = CWD / ".env"
    print("=" * 50)
    print("  Shipyard Setup Wizard")
    print("=" * 50)
    print()

    # Provider
    provider = input("LLM Provider (anthropic/openrouter/local) [anthropic]: ").strip() or "anthropic"

    # API Keys
    anthropic_key = ""
    openrouter_key = ""
    local_url = "http://localhost:11434/v1"

    if provider in ("anthropic", "openrouter"):
        if provider == "anthropic":
            anthropic_key = input("Anthropic API Key: ").strip()
        else:
            openrouter_key = input("OpenRouter API Key: ").strip()
        # Optionally get the other key too
        if not anthropic_key:
            anthropic_key = input("Anthropic API Key (optional, press Enter to skip): ").strip()
        if not openrouter_key:
            openrouter_key = input("OpenRouter API Key (optional, press Enter to skip): ").strip()
    else:
        local_url = input(f"Local LLM URL [{local_url}]: ").strip() or local_url

    # Models
    decompose_model = input("Decompose model [claude-sonnet-4-6]: ").strip() or "claude-sonnet-4-6"
    mbse_model = input("MBSE model [claude-sonnet-4-6]: ").strip() or "claude-sonnet-4-6"

    # Mode
    mode = input("Default mode (capella/rhapsody) [capella]: ").strip() or "capella"

    # Write .env
    env_content = f"""PROVIDER={provider}
ANTHROPIC_API_KEY={anthropic_key}
OPENROUTER_API_KEY={openrouter_key}
LOCAL_LLM_URL={local_url}
DECOMPOSE_MODEL={decompose_model}
MBSE_MODEL={mbse_model}
DEFAULT_MODE={mode}
"""
    env_path.write_text(env_content)
    print(f"\nConfiguration saved to {env_path}")
    print("Run 'shipyard --web' to start the server.")


if __name__ == "__main__":
    main()
