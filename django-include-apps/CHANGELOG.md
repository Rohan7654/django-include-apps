# Changelog

All notable changes to django-include-apps will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-01-24

### Major Release - Stable Version

This is the first stable release of django-include-apps with comprehensive features for Django package management.

### Added
- **Smart Package Mapping**: Pre-configured mappings for 75+ popular Django packages
  - Automatically detects correct INSTALLED_APPS names (e.g., `djangorestframework` → `rest_framework`)
  - Includes packages like Django REST Framework, CORS headers, filters, allauth, debug toolbar, and many more
  - Handles dependency-only packages (marked as `null`) like `pillow`, `psycopg2`, `gunicorn`, `mysqlclient`
  - Complete mapping file: `package_mappings.json`

- **Dynamic Mapping Updates**: Users can save custom package-to-app mappings
  - Prompts to save new mappings when adding unmapped packages
  - Mappings persist in `package_mappings.json` for future use
  - Alphabetically sorted for easy maintenance
  - Enables community-driven mapping improvements

- **requirements.txt Management**: Automatic synchronization with installed packages
  - Prompts to add newly installed packages to requirements.txt with version pinning
  - Updates package versions if already present in requirements.txt
  - Prompts to remove packages from requirements.txt when apps are removed
  - Can generate complete requirements.txt from INSTALLED_APPS by scanning the project
  - Handles both existing and new requirements.txt files
  - Three options when requirements.txt doesn't exist:
    - Create with current package only
    - Create with all project packages
    - None/Skip

- **Unused App Detection**: Intelligent scanning to find unused apps
  - Scans all `.py` files in the project for import statements
  - Identifies apps in INSTALLED_APPS that are never imported anywhere
  - Interactive checkbox selection for batch removal
  - Skips virtual environments (`venv`, `env`, `.venv`), migrations, and other non-project directories
  - Protects default Django apps from removal
  - Uses reverse mapping to detect packages by their app names

- **Enhanced CLI Commands**:
  - `add-app`: Enhanced with mapping support and requirements.txt management
  - `add-apps`: Batch processing with individual prompts for each package
  - `remove-app`: Without parameters, detects and suggests unused apps for removal
  - `remove-apps`: Without parameters, detects and suggests unused apps for removal
  - **`install-requirements`**: NEW command to install from requirements.txt and auto-add Django packages
  - **`view-mappings`**: NEW command to view all package mappings in table format
  - **`mapping`**: NEW subcommand group for managing mappings (add/update/remove/list)
  - **`completion`**: NEW command for shell completion (bash/zsh/fish)
  - **`--version`**: Show tool version and exit
  - All commands support custom directory via `--start-dir` or `-d` option

- **Version Specifier Support**: Install specific package versions
  - Support for all pip version specifiers (==, >=, <=, >, <, ~=, !=)
  - Examples: `djangorestframework==3.14.0`, `django-filter>=2.0`
  - Automatically extracts package name for mapping lookups
  - Uses full specification for pip installation
  - Adds to requirements.txt with specified version
  - Works with both `add-app` and `add-apps` commands

- **Shell Completion**: Auto-completion for better UX
  - Support for bash, zsh, and fish shells
  - Easy installation with `--install` flag
  - Tab completion for all commands and options
  - Manual installation option for advanced users

- **Install from requirements.txt**: Streamlined project setup
  - Install all packages from requirements.txt with `-r` flag
  - Automatically detect Django-related packages
  - Interactive checkbox selection for packages to add to INSTALLED_APPS
  - Uses smart package mapping for known packages
  - Prompts for app names for unmapped packages
  - Saves new mappings for future use
  - Perfect for setting up new projects or onboarding team members

- **Mapping Management**: Full control over package mappings
  - **Confirm before updating**: Shows current vs new mapping before overwriting
  - **view-mappings command**: Display all 77+ mappings in organized table format
  - **Filter options**: Filter by package name, show null-only, or apps-only
  - **mapping add**: Add new package mappings via CLI
  - **mapping update**: Update existing mappings with confirmation
  - **mapping remove**: Remove mappings with confirmation prompt
  - **mapping list**: Alias for view-mappings with same filter options
  - Color-coded table output for better readability

- **Improved User Experience**:
  - Interactive prompts using inquirer library
  - **None/Skip option**: Users can skip any operation at any time
  - **Mapping confirmation**: Prevents accidental overwriting of existing mappings
  - Color-coded output messages (success in green, errors in red, warnings in yellow)
  - Clear confirmation prompts to prevent accidental changes
  - Detailed feedback for every operation
  - Better error handling and user guidance
  - Flexible control over all operations

### Changed

- **Improved Package Detection**:
  - Better handling of package names with hyphens vs underscores
  - More accurate Django-related package verification via PyPI
  - Checks both keywords and classifiers on PyPI

- **Enhanced Interactive Flow**:
  - "Use same" option now checks mapping first, prompts if not found
  - "Use different" option allows custom app names
  - **"None/Skip" option** allows users to cancel operations at any time
  - Option to save custom mappings for future use
  - More descriptive prompts and messages

### Fixed
- Improved handling of apps with dots in names (e.g., `sorl.thumbnail`)
- Better detection of package installation status
- Fixed regex patterns to handle both single and double quotes in INSTALLED_APPS

### Technical Details
- **Dependencies**: typer, requests, inquirer
- **Python Support**: 3.8, 3.9, 3.10, 3.11, 3.12
- **Framework**: Django (all versions)
- **Mappings**: 75+ Django packages pre-configured
- **Build System**: Modern pyproject.toml (PEP 621)

---

## [0.1.3] - 2025-12-27

### Added
- `add-apps` command for batch adding multiple packages
- Improved Django package detection via PyPI

### Changed
- Enhanced interactive prompts using inquirer
- Better package installation flow

---

## [0.1.2] - 2025-12-20

### Added
- Basic package installation prompts
- Django-related package verification

### Fixed
- Issues with settings.py file detection

---

## [0.1.1] - 2025-12-15

### Added
- `add-app` command to add single apps to INSTALLED_APPS
- Automatic package installation option
- Custom directory support with `--start-dir` option

### Changed
- Improved settings.py file search

---

## [0.1.0] - 2025-12-10

### Added
- Initial release
- Basic CLI structure with typer
- Simple app addition to INSTALLED_APPS
- Settings.py file detection

---

## Version Comparison

### v1.0.0 vs v0.1.3

**Major Improvements:**
- **75+ package mappings** (vs 0 in v0.1.3)
- **Automatic requirements.txt management** (new feature)
- **Unused app detection** (new feature)
- **Dynamic mapping updates** (new feature)
- **None/Skip option** for flexible user control (new feature)
- **Enhanced user experience** with better prompts and feedback
- **Comprehensive documentation** with examples and changelog
- **Modern build system** with pyproject.toml (PEP 621)

**Features:**
- v0.1.3: 4 basic commands (add-app, add-apps, remove-app, remove-apps)
- v1.0.0: Same 4 commands with significantly enhanced functionality + unused app detection

**Package Mappings:**
- v0.1.3: Manual entry required for every package
- v1.0.0: 75+ pre-configured mappings with option to add more

**requirements.txt:**
- v0.1.3: No management
- v1.0.0: Full automatic management (add/update/remove/generate)

**User Control:**
- v0.1.3: Limited options
- v1.0.0: None/Skip option available at all prompts

**Code Quality:**
- v0.1.3: Basic implementation
- v1.0.0: Production-ready with comprehensive error handling, type hints, and documentation

---

[1.0.0]: https://github.com/Rohan7654/django-include-apps/releases/tag/v1.0.0
[0.1.3]: https://github.com/Rohan7654/django-include-apps/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/Rohan7654/django-include-apps/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/Rohan7654/django-include-apps/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/Rohan7654/django-include-apps/releases/tag/v0.1.0
