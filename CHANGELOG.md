# Changelog

All notable changes to the Noesium project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Monorepo workspace structure with three subprojects
- Root workspace configuration for unified dependency management
- Comprehensive project documentation and contributing guidelines

## [noesium-v0.3.4] - 2026-03-05

### Added
- Browser-Use subagent integration with event-watchdog framework
- Askura conversational agent for information extraction
- Tacitus agent for persistent memory management
- Multiple LLM provider support (OpenAI, Anthropic, Google, Ollama, LM Studio)
- Comprehensive toolkit system (arxiv, gmail, github, bash, etc.)
- MCP (Model Context Protocol) integration
- Event-sourced memory system
- Vector store support (Weaviate, PgVector)
- Message bus (bubus) integration

### Changed
- Restructured to src layout with setuptools build system
- Improved agent coordination and task planning
- Enhanced configuration system with migration support

### Fixed
- Various bug fixes in memory management
- Performance optimizations in tool execution
- Improved error handling across modules

## [noeagent-v0.1.0] - 2026-03-05

### Added
- Initial release of NoeAgent
- Interactive TUI with rich progress display
- Dual-mode operation: Ask and Agent modes
- Built-in task planning and subagent coordination
- Multi-provider LLM support
- Configuration file support (noesium.toml)

### Features
- Real-time task execution with progress tracking
- Subagent orchestration for complex tasks
- Integration with Noesium framework
- Support for local and cloud LLMs

## [voyager-v0.1.0] - 2026-03-05

### Added
- Initial release of Voyager
- FastAPI backend with WebSocket support
- React + TypeScript frontend with Tailwind CSS
- Task management system
- Git integration
- Real-time progress updates
- Repository browser

### Features
- Create and manage coding tasks
- Live task progress via WebSocket
- Multi-repository support
- Agent-powered task execution
- Modern responsive UI

## Release History

### v0.3.x Series (Framework Development)

**v0.3.4** (2026-03-05)
- Browser automation with Browser-Use
- Enhanced toolkit ecosystem
- Performance improvements

**v0.3.3** (2026-02-28)
- Memory system improvements
- Additional LLM providers
- Bug fixes

**v0.3.2** (2026-02-20)
- Subagent framework
- Event-sourced architecture
- Configuration migration

**v0.3.1** (2026-02-15)
- Initial toolkit system
- Vector store integration
- Message bus support

**v0.3.0** (2026-02-10)
- Core framework architecture
- LangGraph integration
- Basic agent capabilities

### v0.2.x Series (Experimental)

**v0.2.0** (2026-01-15)
- Experimental agent implementation
- Basic tool support
- Proof of concept

### v0.1.x Series (Prototype)

**v0.1.0** (2025-12-01)
- Initial prototype
- Basic cognitive architecture
- Simple agent behaviors

---

## Version Scheme

The project uses independent versioning for each package:

- **noesium**: Core framework (follows semantic versioning)
- **noeagent**: Application versioning
- **voyager**: Backend API versioning

### Version Format

- **MAJOR**: Breaking changes
- **MINOR**: New features, backward compatible
- **PATCH**: Bug fixes, backward compatible

## Upcoming Changes

See [GitHub Milestones](https://github.com/mirasoth/noesium/milestones) for planned releases.

---

For detailed changes, see [GitHub Releases](https://github.com/mirasoth/noesium/releases).