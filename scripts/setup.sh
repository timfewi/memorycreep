#!/bin/bash
# MemoryCreep Setup Script

set -e

echo "=================================================================="
echo "                        PENTESTAGENT"
echo "                  AI Penetration Testing"
echo "=================================================================="
echo ""

# Check Python version
echo "Checking Python version..."
python_version=$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
required_version="3.12"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "Error: Python $required_version or higher is required (found $python_version)"
    exit 1
fi
echo "[OK] Python $python_version"

# Resolve only the reviewed lockfile. This script deliberately performs no
# package-manager, browser, or operating-system bootstrap downloads.
if ! command -v uv >/dev/null 2>&1; then
    echo "Error: uv is required; use the pinned environment: nix develop .#all"
    exit 1
fi
if [ ! -f "uv.lock" ]; then
    echo "Error: uv.lock is missing; generate and review it before setup"
    exit 1
fi

echo "Synchronizing the reviewed Python environment..."
export UV_PROJECT_ENVIRONMENT=venv
uv sync --frozen --extra dev --extra rag
# shellcheck disable=SC1091
source venv/bin/activate
echo "[OK] Locked dependencies installed"
echo "[INFO] Browser and clipboard support come from the declared NixOS guest."

# Create .env file if not exists
if [ ! -f ".env" ]; then
    echo "Creating .env file..."
    cat > .env << EOF
# MemoryCreep Configuration

# API Keys (set at least one for chat model)
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GEMINI_API_KEY=

# OpenAI-compatible relay (optional — any URL that speaks /v1/chat/completions)
# OPENAI_API_BASE=https://your-relay.example/v1
# PENTESTAGENT_MODEL=openai/<model-name-on-your-relay>

# For web search functionality (optional)
TAVILY_API_KEY=

# Chat Model (any LiteLLM-supported model)
# OpenAI: gpt-5, gpt-4.1, gpt-4.1-mini
# Anthropic: claude-sonnet-4-20250514, claude-opus-4-20250514
# Google: gemini models require gemini/ prefix (e.g., gemini/gemini-2.5-flash)
# Other providers: azure/, bedrock/, groq/, ollama/, together_ai/ (see litellm docs)
PENTESTAGENT_MODEL=gpt-5

# Embeddings (for RAG knowledge base)
# Options: openai, local (default: openai if OPENAI_API_KEY set, else local)
# PENTESTAGENT_EMBEDDINGS=local

# Settings
PENTESTAGENT_DEBUG=false

# Agent max iterations (regular agent + crew workers, default: 30)
# PENTESTAGENT_AGENT_MAX_ITERATIONS=30

# Orchestrator max iterations (crew mode coordinator, default: 50)
# PENTESTAGENT_ORCHESTRATOR_MAX_ITERATIONS=50
EOF
    echo "[OK] .env file created"
    echo "[!] Please edit .env and add your API keys"
fi

# Create loot directory for reports
mkdir -p loot
echo "[OK] Loot directory created"

echo ""
echo "=================================================================="
echo "Setup complete!"
echo ""
echo "To get started:"
echo "  1. Edit .env and add your API keys"
echo "  2. Activate the virtual environment: source venv/bin/activate"
echo "  3. Run MemoryCreep: memorycreep (legacy: pentestagent)"
echo ""
echo "For Docker usage:"
echo "  docker-compose up pentestagent"
echo "  docker-compose --profile kali up pentestagent-kali"
echo ""
echo "=================================================================="
