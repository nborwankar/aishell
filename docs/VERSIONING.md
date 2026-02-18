# AIShell Versioning Guidelines

## Version Format

We follow [Semantic Versioning](https://semver.org/): **MAJOR.MINOR.PATCH**

- **MAJOR**: Breaking changes that require users to modify their workflows
- **MINOR**: New features that are backward compatible
- **PATCH**: Bug fixes and minor improvements

## When to Create a New Version

### MAJOR Version (1.0.0 → 2.0.0)
- Breaking CLI syntax changes (like our recent refactoring)
- Removal of features or commands
- Major architectural changes
- Changes to default behavior that break existing scripts

### MINOR Version (1.0.0 → 1.1.0)
- New commands or features
- New LLM provider support
- New configuration options
- Performance improvements
- Enhanced functionality that doesn't break existing usage

### PATCH Version (1.0.0 → 1.0.1)
- Bug fixes
- Documentation updates
- Dependency updates (security patches)
- Minor UI/UX improvements
- Configuration default updates

## Version History

### v0.3.0 (Current - 2025-06-23)
**Breaking Changes:**
- Refactored CLI commands: `query` → `llm`, new `collate` syntax
- Removed `--model` parameter from CLI

**Features:**
- Environment-based model configuration
- MCP awareness for LLMs
- Configurable default models

### v0.2.0 (2025-06-21)
**Features:**
- Complete Phase 2 implementation
- LLM integration (4 providers)
- MCP protocol support
- Interactive transcript logging
- Environment management system

### v0.1.0 (2025-06-20)
**Features:**
- Initial Phase 1 release
- Web search functionality
- Intelligent shell
- File system search
- macOS Spotlight integration

## Release Process

### 1. Update Version Number
```python
# aishell/__init__.py
__version__ = "0.3.0"  # Update this
```

### 2. Create Changelog Entry
```markdown
# CHANGELOG.md
## [0.3.0] - 2025-06-23
### Breaking Changes
- Description of breaking changes

### Added
- New features

### Fixed
- Bug fixes
```

### 3. Create Git Tag
```bash
git tag -a v0.3.0 -m "Release version 0.3.0: CLI refactoring"
git push origin v0.3.0
```

### 4. Create GitHub Release
- Go to GitHub releases page
- Create release from tag
- Include changelog in description
- Attach any necessary artifacts

## Guidelines for Version Bumps

### Group Related Changes
- Don't version every commit
- Bundle related features/fixes into meaningful releases
- Aim for releases every 2-4 weeks during active development

### Consider User Impact
- **High Impact** (MAJOR): Users must change their scripts/workflows
- **Medium Impact** (MINOR): New capabilities users can adopt
- **Low Impact** (PATCH): Transparent improvements

### Development vs. Stable
- Use `0.x.x` for pre-1.0 development (current state)
- `1.0.0` signals production-ready with stable API
- Consider `-alpha`, `-beta`, `-rc` suffixes for pre-releases

### Examples of Version-Worthy Changes

**Worth a PATCH:**
- Fixed bug in web search timeout handling
- Updated Claude model from 3.5 to 3.7
- Improved error messages
- Documentation typo fixes

**Worth a MINOR:**
- Added new `export` command to shell
- Support for new LLM provider (e.g., Cohere)
- Added `--json` output format option
- New file search filters

**Worth a MAJOR:**
- Changed `llm` command to require provider first (our recent change)
- Removed Python 3.8 support
- Changed configuration file format
- Restructured package organization

## Best Practices

1. **Batch Changes**: Accumulate several related changes before releasing
2. **Release Notes**: Always write clear, user-focused release notes
3. **Migration Guides**: For breaking changes, provide migration instructions
4. **Deprecation Warnings**: Warn users before removing features
5. **Testing**: Ensure comprehensive tests pass before releasing

## Current Recommendation

Based on recent changes, AIShell should be tagged as **v0.3.0**:
- Breaking change: CLI command syntax refactoring
- New features: Configurable models, MCP awareness
- Still in pre-1.0 development phase

Next steps:
1. Update `__version__` in `__init__.py`
2. Create `CHANGELOG.md` with full history
3. Tag and release v0.3.0