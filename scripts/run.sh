#!/bin/bash
# MemoryCreep Run Script

set -e

# Activate virtual environment if exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# The application reads .env through python-dotenv. Do not parse secrets in
# shell code or expose them through an expanded command line.

# Parse arguments
MODE="cli"
TARGET=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --tui)
            MODE="tui"
            shift
            ;;
        --target)
            TARGET="$2"
            shift 2
            ;;
        --help)
            echo "MemoryCreep - AI Penetration Testing"
            echo ""
            echo "Usage: run.sh [options]"
            echo ""
            echo "Options:"
            echo "  --tui              Run in TUI mode"
            echo "  --target <url>     Set initial target"
            echo "  --help             Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Build an argv array so targets cannot change command structure.
command=(python -m pentestagent)

if [ "$MODE" = "tui" ]; then
    command+=(--tui)
fi

if [ -n "$TARGET" ]; then
    command+=(--target "$TARGET")
fi

# Run MemoryCreep
echo "Starting MemoryCreep..."
exec "${command[@]}"
