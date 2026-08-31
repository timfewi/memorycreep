<div align="center">

<img src="assets/memorycreep-logo.png" alt="MemoryCreep logo" width="240">

# MemoryCreep

### Hardened AI-assisted security testing on NixOS

[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE.txt)
[![Version](https://img.shields.io/badge/Version-0.2.0-orange.svg)](https://github.com/timfewi/memorycreep/releases)
[![Security](https://img.shields.io/badge/Security-Policy--Bound-red.svg)](docs/nixos-workstation.md)
[![MCP](https://img.shields.io/badge/MCP-Compatible-purple.svg)](https://github.com/timfewi/memorycreep)

</div>

MemoryCreep is a fork of
[PentestAgent](https://github.com/GH05TCREW/pentestagent) by
[GH05TCREW](https://github.com/GH05TCREW); the upstream license attributes the
original portions to Masic. MemoryCreep is a hardened NixOS host for
policy-bound, AI-assisted security testing and has evolved into an independent
project. It is not
affiliated with or endorsed by the original maintainers. See
[the repository guide](docs/repository-guide.md) and
[the upstream policy](UPSTREAM.md).

## Requirements

The hardened product targets an x86_64 machine with UEFI, KVM, at least eight
CPU cores, and 32 GiB RAM. Python is fixed to the 3.12 series. Provider keys
stay on the NixOS host and are exposed to the Pentest VM only through the
session-scoped broker.

## Hardened NixOS workstation

The supported security architecture is a minimal NixOS 26.05 host plus
Cloud-Hypervisor MicroVMs. The host has no agent, pentest tools, Docker daemon,
project mount, or free-shell execution path. Exact scope is enforced by
host-side nftables after local confirmation.

```bash
# Evaluate every host and guest, then build the installer.
nix flake check
nix build .#memorycreep
nix build .#installer-iso

# On an installed workstation:
sudo pta start pentest --project customer-a --scope 192.0.2.0/24 --net offline
sudo pta start pentest --project customer-a --scope target.example --net vpn
sudo pta start malware --guest linux --sample ./sample.bin
sudo pta status
sudo pta export --project malware-quarantine
sudo pta stop
```

See [the workstation deployment and recovery guide](docs/nixos-workstation.md).
For offline source checks, Semgrep, OSV, and the staged E2E commands, use the
[security verification guide](docs/security-verification.md).
The hardware-specific interface and kernel values live separately in
`nix/hosts/hardware-example.nix`; secrets, Secure Boot keys, project volumes,
VM overlays, audit logs, FIDO2 enrollment data, and Windows images are never
stored in Git or the Nix store.

## Legacy development install

The following setup is retained for development on non-product machines. It is
not the hardened workstation and must not be used as a host security boundary.

## Install

```bash
# Clone
git clone https://github.com/timfewi/memorycreep.git
cd memorycreep

# Preferred: pinned Nix environment
nix develop .#all

# Legacy helper scripts require a reviewed uv.lock and perform a frozen sync.
.\scripts\setup.ps1   # Windows
./scripts/setup.sh     # Linux/macOS

# Equivalent Linux/macOS command with an already trusted uv binary
UV_PROJECT_ENVIRONMENT=venv uv sync --frozen --extra dev --extra rag
```

## Configure

Create `.env` in the project root:

```
ANTHROPIC_API_KEY=sk-ant-...
PENTESTAGENT_MODEL=claude-sonnet-4-20250514
```

Or for OpenAI:

```
OPENAI_API_KEY=sk-...
PENTESTAGENT_MODEL=gpt-5
```

Any [LiteLLM-supported model](https://docs.litellm.ai/docs/providers) works.

### Using a relay / custom API base

Point MemoryCreep at any OpenAI-compatible endpoint via `OPENAI_API_BASE`:

```bash
OPENAI_API_KEY=your-relay-token
OPENAI_API_BASE=https://relay.example/v1
PENTESTAGENT_MODEL=openai/<model-name-on-your-relay>
```

For Anthropic-compatible endpoints use `ANTHROPIC_API_BASE` instead.
See `.env.example` for full provider notes and embedding options.

## Run

```bash
memorycreep                      # Launch TUI
memorycreep -t 192.168.1.1       # Launch with target
memorycreep tui --docker         # Run tools in Docker container

# The legacy `pentestagent` command remains available for compatibility.
```

## Docker (legacy compatibility only)

Docker mode is retained for development compatibility. It is not used by the
NixOS product and is not a security boundary equivalent to the MicroVM policy.
The strict supply-chain gate currently rejects these legacy images because
their APT/Pip/Playwright inputs are not yet fully immutable.

### Option 1: Pull pre-built image (fastest)

```bash
# Base image with nmap, netcat, curl
docker run -it --rm \
  -e ANTHROPIC_API_KEY=your-key \
  -e PENTESTAGENT_MODEL=claude-sonnet-4-20250514 \
  ghcr.io/timfewi/memorycreep:0.2.0

# Kali image with metasploit, sqlmap, hydra, etc.
docker run -it --rm \
  -e ANTHROPIC_API_KEY=your-key \
  ghcr.io/timfewi/memorycreep:kali-0.2.0
```

### Option 2: Build locally

```bash
# Build
docker compose build

# Run
docker compose run --rm pentestagent

# Or with Kali
docker compose --profile kali build
docker compose --profile kali run --rm pentestagent-kali
```

The container runs MemoryCreep with access to Linux pentesting tools. The agent can use `nmap`, `msfconsole`, `sqlmap`, etc. directly via the terminal tool.

Requires Docker to be installed and running.

## Modes

MemoryCreep has three modes, accessible via commands in the TUI:

| Mode | Command | Description |
|------|---------|-------------|
| Assist | `/assist <task>` | One single-shot instruction, with tool execution |
| Agent | `/agent <task>` | Autonomous execution of a single task |
| Crew | `/crew <task>` | Multi-agent mode. Orchestrator spawns specialized workers |
| Interact | `/interact <task>` | Interactive mode. Chat with the agent, it will help you and guide during the pentesting procedure |

### TUI Commands

```
/assist <task>    One single-shot instruction.
/agent <task>     Run autonomous agent on task
/crew <task>      Run multi-agent crew on task
/interact <task>  Chat with the agent in guided mode
/target <host>    Set target
/tools            List available tools
/notes            Show saved notes
/report           Generate report from session
/memory           Show token/memory usage
/scope            Show immutable host-confirmed scope
/approvals        List, approve, or deny high-risk actions
/network          Show the active offline/vpn/lan profile
/vm-status        Show the policy and MicroVM runtime state
/prompt           Show system prompt
/conversations    Browse and restore saved conversations
/mcp <list/add>   Visualizes or adds a new MCP server.
/spawn [target] [--scope CIDR] [--model M] [--no-rag] [--no-mcp]
                  Manually spawn a child MCP agent from the TUI.
/despawn <server_name>
                  Terminate and remove a previously spawned child agent.
/clear            Clear chat and history
/quit             Exit (also /exit, /q)
/help             Show help (also /h, /?)
```

Press `Esc` to stop a running agent. `Ctrl+Q` to quit.

## Playbooks

MemoryCreep includes prebuilt **attack playbooks** for black-box security testing. Playbooks define a structured approach to specific security assessments.

**Run a playbook:**

```bash
memorycreep run -t example.com --playbook thp3_web
```

![Playbook Demo](assets/playbook.gif)

## Tools

MemoryCreep includes built-in tools and supports MCP (Model Context Protocol) for extensibility.

**Built-in tools:** `terminal`, `browser`, `notes`, `web_search` (requires `TAVILY_API_KEY`), `spawn_mcp_agent`

### Agent Self-Spawning (`spawn_mcp_agent`)

`spawn_mcp_agent` is a built-in tool that allows a running agent to spawn a child copy of itself as a subordinate MCP server connected over stdio. The child process is fully isolated — its own runtime, LLM client, conversation history, and notes store — and its complete tool set is injected back into the parent agent's available tools after spawning.

This legacy development feature enables hierarchical workflows on non-product
machines. It is disabled inside the hardened Pentest VM because a subprocess
would otherwise own a separate approval store and audit chain; use `/crew`
there, whose workers share the exact session policy and runtime.

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `target` | string | — | Pentest target to pass to the child |
| `scope` | string[] | — | In-scope targets/CIDRs for the child |
| `model` | string | env var | Model identifier, overrides `PENTESTAGENT_MODEL` on the child |
| `no_rag` | boolean | `false` | Skip RAG engine initialisation on the child |
| `no_mcp` | boolean | `true` | Skip external MCP server connections on the child (recommended) |

After `spawn_mcp_agent` returns, the child's tools (`run_task`, `run_task_async`, `await_tasks`, etc.) are available on the **next** tool call. The child's server name is assigned automatically (e.g. `child_agent_1`) and returned in the result.

**Example — orchestrator delegating parallel recon to two children:**

```
# Turn 1: spawn two isolated child agents
spawn_mcp_agent  target="10.0.1.0/24"  scope=["10.0.1.0/24"]
spawn_mcp_agent  target="10.0.2.0/24"  scope=["10.0.2.0/24"]

# Turn 2: children's tools are now available — delegate work asynchronously
child_agent_1__run_task_async  task="Full port scan and service enumeration"
child_agent_2__run_task_async  task="Full port scan and service enumeration"

# Turn 3: wait and collect
child_agent_1__await_tasks  task_ids=["<id1>"]  timeout_seconds=600
child_agent_2__await_tasks  task_ids=["<id2>"]  timeout_seconds=600
child_agent_1__get_task_result  task_id="<id1>"
child_agent_2__get_task_result  task_id="<id2>"
```

### Manual Child Agent Control (`/spawn` and `/despawn`)

Beyond the automatic `spawn_mcp_agent` tool, the TUI exposes two commands that let you spawn and terminate child agents **manually**, independently of a running agent loop.

#### `/spawn`

```
/spawn [target] [--scope CIDR ...] [--model MODEL] [--no-rag] [--no-mcp]
```

Spawns a new child MCP agent over stdio and attaches it to the current session. The child appears as a collapsible terminal panel in the TUI sidebar and its tools become available to the parent agent on the next tool call.

| Argument | Description |
|----------|-------------|
| `target` | Pentest target to pass to the child (positional or `--target`) |
| `--scope CIDR` | One or more in-scope CIDRs (repeatable) |
| `--model MODEL` | Override the model for the child agent |
| `--no-rag` | Skip RAG engine initialisation on the child |
| `--no-mcp` | Skip external MCP server connections on the child |

**Examples:**

```
/spawn 10.0.1.1
/spawn 10.0.1.1 --scope 10.0.1.0/24 --model claude-sonnet-4-20250514
/spawn --target 10.0.1.1 --scope 10.0.1.0/24 --no-rag
```

#### `/despawn`

```
/despawn <server_name>
```

Terminates the child agent identified by `server_name` (e.g. `child_agent_1`), removes its terminal panel from the TUI, and disconnects its tools from the parent session. Use `/mcp list` to see the names of all currently active child agents.

**Example:**

```
/despawn child_agent_1
```

### MCP RAG Tool Optimizer

When an MCP server exposes more than 128 tools, MemoryCreep automatically replaces the full catalogue with a single `mcp_<server>_rag_optimizer` tool. This meta-tool uses embedding similarity (via LiteLLM, default `text-embedding-3-small`) to retrieve the most relevant tools for the task at hand and injects them into the agent's next turn — keeping the context window manageable without losing access to the full tool set.

The optimizer is transparent to the agent: it calls the RAG tool with focused natural-language queries describing what it needs, and the matching tools become available on the next turn to call directly.

**Usage guidance for the agent:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `queries` | string[] | *(required)* | One focused query per capability needed. More specific = higher accuracy |
| `top_k` | integer | `20` | Tools to retrieve per query (max 128). Results are merged and deduplicated |

Embeddings are computed once at startup and cached, so repeated queries are fast. The optimizer is built per-server, so each MCP server with a large catalogue gets its own independent index.

> **Tip:** Pass one query per distinct capability rather than combining everything into one query. `["list open ports on a host", "get process memory usage"]` retrieves better results than `["list ports and memory and CPU"]`.

### MCP Integration

MemoryCreep supports MCP (Model Context Protocol) in two directions: **consuming** external MCP servers as tool sources, and **exposing itself** as an MCP server so external clients (Claude Desktop, Cursor, etc.) can drive MemoryCreep programmatically.

---

#### Consuming External MCP Servers (Client Mode)

Configure `mcp_servers.json` to connect MemoryCreep to any external MCP servers. Example config:

```json
{
  "mcpServers": {
    "nmap": {
      "command": "npx",
      "args": ["-y", "gc-nmap-mcp"],
      "env": {
        "NMAP_PATH": "/usr/bin/nmap"
      }
    }
  }
}
```

---

#### Exposing MemoryCreep as an MCP Server (Server Mode)

MemoryCreep can run as an MCP server, allowing any MCP-compatible client to submit tasks, inspect results, and control the agent remotely. Two transports are supported:

**STDIO** — for local clients (e.g. Claude Desktop, Cursor):

```bash
memorycreep mcp_server --type stdio
memorycreep mcp_server --type stdio --target 192.168.1.1 --scope 192.168.1.0/24
memorycreep mcp_server --type stdio --model claude-sonnet-4-20250514 --docker
```

**SSE (HTTP)** — for remote or networked clients:

```bash
memorycreep mcp_server --type sse
memorycreep mcp_server --type sse --host 0.0.0.0 --port 8080
memorycreep mcp_server --type sse --target 10.0.0.1 --scope 10.0.0.0/24 --docker
```

The SSE transport exposes a single `/mcp` endpoint supporting `POST` (requests), `GET` (persistent SSE stream for server-initiated push), and `DELETE` (session teardown). Sessions are tracked via the `Mcp-Session-Id` header.

**All `mcp_server` flags:**

| Flag | Default | Description |
|------|---------|-------------|
| `--type` | *(required)* | Transport: `stdio` or `sse` |
| `--host` | `0.0.0.0` | SSE bind host |
| `--port` | `8080` | SSE bind port |
| `--target` | none | Primary pentest target (IP / hostname) |
| `--scope` | `[]` | In-scope targets/CIDRs (space-separated) |
| `--model` | env var | Model identifier, overrides `PENTESTAGENT_MODEL` |
| `--docker` | false | Use DockerRuntime instead of LocalRuntime |
| `--no-rag` | false | Skip RAG engine initialisation |
| `--no-mcp` | false | Skip external MCP server connections |

##### Example: Claude Desktop config (`claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "memorycreep": {
      "command": "memorycreep",
      "args": ["mcp_server", "--type", "stdio"]
    }
  }
}
```

---

#### MCP Server Tools Reference

When acting as an MCP server, MemoryCreep exposes the following tools:

**Server Status & Config**

| Tool | Description |
|------|-------------|
| `get_server_status` | Live server status: readiness, task counts by state, primary target/scope, memory store size |
| `get_config` | Primary agent configuration: target, scope, max iterations, tool list |
| `update_config` | Update target, scope, or max iterations for all subsequent tasks |

**Task Execution**

| Tool | Description |
|------|-------------|
| `run_task` | Submit a task and **block** until it completes. Returns full result, tools used, and notes snapshot |
| `run_task_async` | Submit a task and **return immediately** with a `task_id`. Poll with `get_task_status` |

**Task Inspection**

| Tool | Description |
|------|-------------|
| `list_tasks` | List all tasks with status, target, and summary. Filterable by status |
| `get_task_status` | Poll the current status and result preview of a task |
| `get_task_result` | Full task result: final output, thinking steps, all tool calls and results, notes snapshot |
| `await_tasks` | Block until a set of async task IDs have all finished (polls every 500 ms, configurable timeout) |

**Task Control**

| Tool | Description |
|------|-------------|
| `cancel_task` | Cancel a running or pending task by ID |

**Tool Management**

| Tool | Description |
|------|-------------|
| `list_tools` | List all tools available to the agent |
| `enable_tool` | Enable a named tool on the primary agent |
| `disable_tool` | Disable a named tool on the primary agent |



**Conversation History**

| Tool | Description |
|------|-------------|
| `get_conversation_history` | Return message history for a task or the primary agent. Supports a `limit` parameter |
| `reset_conversation` | Clear conversation history for a task or the primary agent |

**Memory**

| Tool | Description |
|------|-------------|
| `store_memory` | Persist a key-value pair to the in-process memory store |
| `retrieve_memory` | Retrieve by exact key, search by substring, or list all keys |
| `clear_memory` | Delete a specific key or wipe all memory with `scope='all'` |

**Observability**

| Tool | Description |
|------|-------------|
| `get_logs` | Return recent execution logs, optionally filtered by level (`info` / `warning` / `error`) |
| `get_metrics` | Runtime metrics: task counts, success rate, total tool calls, memory and log sizes |

---

#### Async Task Workflow Example

For long-running recon tasks, use the async pattern:

```
# 1. Submit tasks without blocking
run_task_async  task="Enumerate subdomains of example.com"  target="example.com"
run_task_async  task="Run nmap SYN scan on example.com"     target="example.com"

# 2. Block until both finish (up to 5 minutes)
await_tasks  task_ids=["<id1>", "<id2>"]  timeout_seconds=300

# 3. Retrieve full results
get_task_result  task_id="<id1>"
get_task_result  task_id="<id2>"
```

---

### CLI Tool Management

```bash
memorycreep tools list         # List all tools
memorycreep tools info <name>  # Show tool details
memorycreep mcp list           # List MCP servers
memorycreep mcp add <name> <command> [args...]  # Add MCP server
memorycreep mcp test <name>    # Test MCP connection
```

## Conversation History Controls

Each user message in the TUI exposes two inline action buttons: **rewind** and **fork**.

### Rewind

Click **rewind** on any user message to truncate the conversation back to just before that message — both in the UI and in the agent's in-memory history. Use it to retry a query from scratch without saving the discarded path.

### Fork

Click **>> fork** on any user message to branch the conversation from that point:

1. The current full conversation is **saved** to the conversation store and a short snapshot ID is shown.
2. The conversation is then **truncated** to just before the selected message (same as rewind).

This lets you try an alternative approach from any point while keeping the original thread retrievable via `/conversations`.

---

## Conversation History

MemoryCreep automatically persists every conversation so you can review, compare, and restore past sessions.

**Auto-save** triggers after each `/assist`, `/agent`, `/crew`, and `/interact` task, and before `/clear`. Up to 20 conversations are kept; older ones are pruned automatically.

**Storage location:** `workspaces/<active>/memory/conversations/` when a workspace is active, or `conversations/` at the project root otherwise. Each conversation is a JSON file.

**Browse & restore with `/conversations`:**

The `/conversations` command opens a split-pane modal inside the TUI:
- **Left panel** — list of saved conversations with title and date.
- **Right panel** — metadata preview plus the first 5 messages (user messages in blue, agent responses in green, tool calls in yellow, tool results in grey). A count shows how many additional messages exist.

<img width="1657" height="662" alt="imagen" src="https://github.com/user-attachments/assets/da42f083-9b7f-445e-8c59-2402ac8e5ddc" />


Select a conversation and press **Restore** to reload it into the current session, or **Close** to dismiss the modal.

## Knowledge

- **RAG:** Place methodologies, CVEs, or wordlists in `pentestagent/knowledge/sources/` for automatic context injection.
- **Notes:** Agents save findings to `loot/notes.json` with categories (`credential`, `vulnerability`, `finding`, `artifact`). Notes persist across sessions and are injected into agent context.
- **Shadow Graph:** In Crew mode, the orchestrator builds a knowledge graph from notes to derive strategic insights (e.g., "We have credentials for host X").

## Project Structure

```
pentestagent/
  agents/         # Agent implementations
  config/         # Settings and constants
  interface/      # TUI and CLI
  knowledge/      # RAG system and shadow graph
  llm/            # LiteLLM wrapper
  mcp/            # MCP client and server configs
  playbooks/      # Attack playbooks
  runtime/        # Execution environment
  tools/          # Built-in tools
```

## Development

```bash
pip install -e ".[dev]"
pytest                       # Run tests
pytest --cov=pentestagent    # With coverage
black pentestagent           # Format
ruff check pentestagent      # Lint
```

## Legal

Only use against systems you have explicit authorization to test. Unauthorized access is illegal.

## License

MIT
