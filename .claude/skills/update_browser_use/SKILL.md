---
name: update-browser-use
description: Intelligently syncs noesium browser_use module with community repository, analyzes code structure dynamically, excludes commercial features (cloud, telemetry, cloud events), and adapts to structural changes in the community codebase.
metadata:
  author: noesium
  version: 1.0.0
---

# Update Browser-Use

AI-driven skill for syncing noesium's `browser_use` module with the community repository at https://github.com/browser-use/browser-use.git.

## When to Use

- Community browser-use repository releases new features
- Bug fixes are needed from the community version
- New functionality from community is desired
- Regular maintenance cycles
- After community repository structural changes

## Approach

This skill uses AI-driven analysis rather than hardcoded scripts to adapt to community codebase evolution:

1. **Dynamic Discovery**: Analyze the community repository structure each time
2. **Intelligent Filtering**: Detect and exclude commercial features automatically
3. **Smart Migration**: Handle import paths, remove cloud/telemetry code, preserve noesium-specific code
4. **Validation**: Check imports and basic functionality after update

## Step-by-Step Process

### 1. Clone Community Repository

```bash
git clone --depth 1 https://github.com/browser-use/browser-use.git /tmp/browser-use-community
```

### 2. Analyze Community Structure

Examine the community repository structure to identify:
- New modules/directories in `browser_use/`
- Changes to core files (agent/service.py, agent/prompts.py, agent/views.py)
- New dependencies or imports
- Changes to system prompts

**Key directories to analyze**: agent/, browser/, dom/, tools/, code_use/, actor/, sandbox/, tokens/, llm/ (EXCLUDED)

### 3. Identify Commercial Features to Exclude

**Directories to exclude:**
- `browser/cloud/` - Cloud browser support
- `telemetry/` - Product telemetry and OTel integration
- `llm/` - Full LLM provider integrations (noesium uses adapters/)
- `skills/` - Community skill system
- `skill_cli/` - Skill CLI

**Files to exclude:**
- `agent/cloud_events.py` - Cloud event definitions
- Any file containing OTel/tracing imports

**Events to exclude (defined in cloud_events.py):**
- `CreateAgentStepEvent` - Sends agent steps with screenshots to cloud
- `CreateAgentSessionEvent` - Creates cloud session with live URLs
- `CreateAgentTaskEvent` - Creates cloud task entry
- `UpdateAgentTaskEvent` - Updates task status in cloud
- `CreateAgentOutputFileEvent` - Uploads output files to cloud

These are commercial cloud features with cloud-specific fields (user_id, device_id, browser_session_live_url, etc.) that are only used by the browser-use cloud service.

### 4. Copy and Update Modules

**Core files to update:**
- `agent/service.py` - Main agent logic (remove cloud events, telemetry, skills)
- `agent/prompts.py` - System prompts
- `agent/views.py` - Agent data models
- `agent/variable_detector.py` - Variable detection
- `browser/session.py` - Browser session (remove cloud browser support)
- `browser/profile.py` - Browser profile (remove cloud browser params)
- `browser/session_manager.py` - Session manager
- `browser/watchdogs/*` - All watchdog files

**New modules to include (if not commercial):**
- `actor/` - CDP-Use high-level API
- `agent/judge.py`
- `agent/system_prompts/` - System prompt templates
- `code_use/` - Code execution agent
- `sandbox/` - Sandbox execution
- `sync/` - Sync utilities
- `tokens/` - Token tracking
- `tools/extraction/` - Data extraction
- `browser/demo_mode.py`, `browser/video_recorder.py`
- `utils.py` - Utility functions

**Resource files to include:**
- `agent/system_prompts/*.md` - System prompt templates
- `code_use/system_prompt.md` - Code use system prompt

### 5. Fix Import Paths

Replace all imports from `browser_use.` to `noesium.agents.browser_use.`:

```bash
find noesium/agents/browser_use -name "*.py" -exec sed -i '' 's/from browser_use\./from noesium.agents.browser_use./g' {} \;
find noesium/agents/browser_use -name "*.py" -exec sed -i '' 's/import browser_use/from noesium.agents import browser_use/g' {} \;
```

### 6. Remove Commercial Features

**In `agent/service.py`:**
- Remove imports from `cloud_events` and `telemetry`
- Remove `self.telemetry = ProductTelemetry()`
- Remove/comment `eventbus.dispatch()` calls for cloud events
- Remove skills-related code (`skill_ids`, `skills`, `skill_service`, `_register_skills_as_actions`, `_get_unavailable_skills_info`)

**In `agent/prompts.py`:**
- Keep `unavailable_skills_info` parameter for compatibility (passed as None)

**In `browser/session.py`:**
- Remove cloud browser imports (`CloudBrowserClient`, `CloudBrowserParams`, etc.)
- Remove cloud browser logic in `start()` method
- Remove `from_system_chrome()` and `list_chrome_profiles()` (requires skill_cli)
- Set `cloud_browser` property to return `False`
- Remove `_cloud_browser_client` private attribute

**In `browser/profile.py`:**
- Remove cloud browser imports
- Set `cloud_browser` property to return `False`
- Comment out `cloud_browser_params` field

### 7. Consolidate Adapters

**IMPORTANT**: All adapter code must be consolidated in the `adapters/` subdirectory to avoid circular imports.

**Remove main `llm_adapter.py`** if it exists (causes circular imports)

**Ensure `adapters/llm_adapter.py` contains:**
- LLM compatibility types: `ChatInvokeUsage`, `ChatInvokeCompletion`, `ImageURL`
- Message types: `UserMessage`, `SystemMessage`, `AssistantMessage`, `ContentPart*`
- `BaseChatModel` class (NOT Protocol - for Pydantic compatibility)
- `NoesiumLLMAdapter` class
- `create_llm_adapter()` function

**Ensure `adapters/agent_adapter.py` contains:**
- `NoesiumAgentAdapter` class (implements `BaseAgent`)
- `create_agent_adapter()` function

**Update `adapters/__init__.py`:**
- Import LLM adapter types directly
- Use lazy loading for `agent_adapter` to avoid circular imports

```python
def __getattr__(name: str):
    if name in ("NoesiumAgentAdapter", "create_agent_adapter"):
        from noesium.agents.browser_use.adapters import agent_adapter
        return getattr(agent_adapter, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

**Update all import references:**
```bash
find noesium/agents/browser_use -name "*.py" -exec sed -i '' 's/from \.\.llm_adapter import/from ..adapters.llm_adapter import/g' {} \;
find noesium/agents/browser_use -name "*.py" -exec sed -i '' 's/from \.\.\.llm_adapter import/from ...adapters.llm_adapter import/g' {} \;
```

**Update `__init__.py` lazy import:**
```python
_LAZY_IMPORTS = {
    "BaseChatModel": ("noesium.agents.browser_use.adapters.llm_adapter", "BaseChatModel"),
    ...
}
```

### 8. Fix Pydantic Compatibility

Ensure models with `BaseChatModel` fields have:
```python
model_config = ConfigDict(arbitrary_types_allowed=True)
```

Check: `agent/views.py` - `MessageCompactionSettings`, `AgentSettings`

### 9. Copy LICENSE File

```bash
cp /tmp/browser-use-community/LICENSE noesium/agents/browser_use/LICENSE
```

Ensures proper licensing compliance (MIT License, Copyright (c) 2024 Gregor Zunic).

### 10. Update Dependencies

**IMPORTANT**: Only include dependencies actually imported in adapted code.

**Analyze actual imports:**
```bash
grep -rh "^import \|^from " noesium/agents/browser_use --include="*.py" | \
  grep -E "^(import|from) (anyio|httpx|cloudpickle)" | sort -u
```

**Update `pyproject.toml`:**
```toml
[project.optional-dependencies]
browser-use = [
    "screeninfo>=0.8.1",        # Browser profile
    "uuid7>=0.1.0",             # Event IDs
    "authlib>=1.6.0",           # Cloud sync auth
    "pypdf>=5.7.0",             # PDF extraction
    "cdp-use>=1.4.4",           # Chrome DevTools
    "html2text>=2025.4.15",     # HTML to text
    "psutil>=7.0.0",            # Process utilities
    "pillow>=11.3.0",           # Image processing
    "anyio>=4.9.0",             # Async utilities
    "httpx>=0.28.1",            # HTTP client
    "cloudpickle>=3.1.1",       # Sandbox serialization
]
```

**Include package data for resources:**
```toml
[tool.setuptools.package-data]
noesium = [
    "agents/browser_use/**/*.md",
    "agents/browser_use/**/*.json",
]
```

### 11. Validate Update

Test basic imports:
```bash
python -c "from noesium.agents.browser_use import BrowserProfile, BrowserSession"
python -c "from noesium.agents.browser_use.adapters import NoesiumLLMAdapter, NoesiumAgentAdapter"
```

Run tests:
```bash
python -m pytest tests/ -k browser_use
```

## Edge Cases

### Circular Import Issues with Adapters

**Problem**: Main `llm_adapter.py` causes circular imports through `adapters/__init__.py` → `agent_adapter` → `agent.service` → `llm_adapter.py`

**Solution**: Remove main `llm_adapter.py`, consolidate in `adapters/`, use lazy loading

**Detection**: Import errors mentioning "partially initialized module" or "circular import"

### New Dependencies

Analyze actual imports in adapted code, add only required packages (see Step 10)

### Breaking API Changes

Check if `agent/__init__.py` wrapper needs updates for Agent/Browser API changes

## Cleanup

```bash
rm -rf /tmp/browser-use-community
```

## Noesium-Specific Modules (Preserve During Sync)

### `adapters/` (Noesium-only)
Replaces community's `llm/` directory with minimal adapter

### `agent/__init__.py` (Noesium-only)
Contains `BrowserUseAgent` wrapper implementing `BaseAgent`

### Key Differences

| Feature | Community | Noesium |
|---------|-----------|---------|
| LLM Support | Full `llm/` directory | `adapters/llm_adapter.py` |
| Agent Wrapper | None | `BrowserUseAgent` |
| Main `__init__.py` | Exports chat models | Exports `BrowserUseAgent`, `BaseChatModel` |
| `skills/`, `skill_cli/` | Present | Excluded |

### Excluded Commercial Features

- `telemetry/`, `browser/cloud/`, `agent/cloud_events.py`, `skills/`, `skill_cli/`

### Shared Modules (Update Carefully)

- `config.py`, `controller/`, `mcp/`, `sync/`, `logging_config.py`, `observability.py`

## Recent Updates (2026-02-23)

### Changes in Latest Community Version

**New Features Added:**
- Enhanced SessionManager integration with Target/CDPSession architecture
- Improved browser watchdogs with video/HAR recording
- Enhanced demo mode capabilities
- Token tracking and cost estimation (`tokens/` module)
- Variable detection in agent responses
- Message compaction for reducing prompt size

**Modified Files:**
- `agent/service.py`: ~4000 lines (major refactoring with cloud/telemetry/skills)
- `agent/prompts.py`: Enhanced system prompts with thinking/evaluation
- `agent/views.py`: New message compaction settings
- `browser/session.py`: ~3600 lines (Target/SessionManager integration)
- `browser/profile.py`: Cloud browser params, improved defaults
- `browser/watchdogs/*`: All updated with new features

**Key Changes to Handle:**
1. Removed `cloud_events` imports and usage
2. Removed `telemetry` module integration
3. Disabled skills integration (`skill_ids`, `skill_service`)
4. Disabled cloud browser support in session/profile
5. Removed `skill_cli` dependencies (`from_system_chrome`, `list_chrome_profiles`)
6. Fixed import paths from `browser_use.` to `noesium.agents.browser_use.`
7. Updated all watchdog files with correct imports

### Files Modified in This Upgrade

1. `agent/service.py` - Major update with cloud/telemetry/skills removed
2. `agent/prompts.py` - Updated system prompts
3. `agent/views.py` - Updated data models
4. `agent/variable_detector.py` - New variable detection
5. `browser/session.py` - Target/SessionManager integration, cloud removed
6. `browser/profile.py` - Cloud params removed
7. `browser/session_manager.py` - Session management
8. `browser/watchdogs/*` - All 14 watchdog files updated
9. `dom/service.py` - Added `child_ids` field
10. `tools/service.py` - Added helper methods

### Total Changes

- 22 files modified
- ~19,000 insertions
- ~15,700 deletions
- Net addition of ~3,300 lines of core functionality (excluding removed commercial features)