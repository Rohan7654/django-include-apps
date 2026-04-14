# Command Reference

Complete reference for every `django-include-apps` command with all flags and sample output.

> **Tip:** Run `django-include-apps --help` to see all available commands, or `django-include-apps <command> --help` for details on a specific command.

---

## Table of Contents

- [Global Options](#global-options)
- [Core Commands](#core-commands)
  - [add-app](#add-app)
  - [remove-app](#remove-app)
  - [install-requirements](#install-requirements)
- [Information Commands](#information-commands)
  - [status](#status)
  - [doctor](#doctor)
  - [show-config](#show-config)
  - [view-mappings](#view-mappings)
  - [diff](#diff)
  - [sync](#sync)
  - [update-configs](#update-configs)
  - [graph](#graph)
  - [profile](#profile)
- [Setup Commands](#setup-commands)
  - [init-env](#init-env)
  - [secure-settings](#secure-settings)
  - [rollback](#rollback)
  - [setup-hooks](#setup-hooks)
  - [docker-init](#docker-init)
  - [tutorial](#tutorial)
  - [completion](#completion)
- [Mapping Subcommands](#mapping-subcommands)
  - [mapping list](#mapping-list)
  - [mapping add](#mapping-add)
  - [mapping update](#mapping-update)
  - [mapping remove](#mapping-remove)
- [Profile Subcommands](#profile-subcommands)
  - [profile save](#profile-save)
  - [profile apply](#profile-apply)
  - [profile list](#profile-list)
  - [profile export](#profile-export)

---

## Global Options

| Flag        | Description                |
| ----------- | -------------------------- |
| `--version` | Show tool version and exit |
| `--help`    | Show help message and exit |

```bash
$ django-include-apps --version
django-include-apps v1.1.0
```

---

## Core Commands

### `add-app`

Add one or more Django apps to `INSTALLED_APPS`.

```
django-include-apps add-app <package-name...> [OPTIONS]
```

| Option        | Short | Description                                                        |
| ------------- | ----- | ------------------------------------------------------------------ |
| `--start-dir` | `-d`  | Directory to search for `settings.py` (default: current directory) |

**Variants:**

```bash
# Single package
django-include-apps add-app djangorestframework

# Multiple packages
django-include-apps add-app djangorestframework django-cors-headers django-filter

# With version specifiers
django-include-apps add-app djangorestframework==3.14.0 django-filter>=2.0 django-cors-headers~=4.0

# Custom project directory
django-include-apps add-app djangorestframework -d /path/to/project
```

**Sample Output (single package):**

```
Installing package 'djangorestframework'...
Package 'djangorestframework' has been installed.
? Do you want to use the same name or a different one? Use same
Using 'rest_framework' package name as the App name to be added in INSTALLED_APPS.
App 'rest_framework' has been added to INSTALLED_APPS.
? Add 'djangorestframework==3.14.0' to requirements.txt? Yes
Added 'djangorestframework==3.14.0' to requirements.txt
```

**Sample Output (with extended config):**

```
 IMPORTANT: Configurations applied are based on the latest package documentation.

✅ djangorestframework installed via pip
✅ Added 'rest_framework' to INSTALLED_APPS

Configuration for: djangorestframework
  • URL Pattern: path('api-auth/', include('rest_framework.urls', namespace='rest_framework'))
  • Settings:
      REST_FRAMEWORK = {
          "DEFAULT_AUTHENTICATION_CLASSES": [
              "rest_framework.authentication.SessionAuthentication",
              "rest_framework.authentication.BasicAuthentication"
          ],
          "DEFAULT_PERMISSION_CLASSES": [
              "rest_framework.permissions.IsAuthenticated"
          ],
          "DEFAULT_RENDERER_CLASSES": [
              "rest_framework.renderers.JSONRenderer",
              "rest_framework.renderers.BrowsableAPIRenderer"
          ],
          "DEFAULT_PARSER_CLASSES": [
              "rest_framework.parsers.JSONParser",
              "rest_framework.parsers.FormParser",
              "rest_framework.parsers.MultiPartParser"
          ],
          "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
          "PAGE_SIZE": 10
      }

? Found additional configuration for package 'djangorestframework' (Space to toggle):
  [x] URL Patterns
  [x] Required Settings

Selected actions:
  - URL Patterns
  - Required Settings
? Proceed? Yes, apply changes

Applying extended configuration for 'djangorestframework'...
✅ Added URL pattern 'api-auth/'
✅ Added REST_FRAMEWORK settings
✅ Added djangorestframework==3.15.2 to requirements.txt

⚠️  The following package(s) require database migrations: djangorestframework
? Run 'python manage.py migrate' now? Yes
Running migrations...
✅ Migrations applied successfully.
```

**Sample Output (multiple packages):**

```
 IMPORTANT: Configurations applied are based on the latest package documentation.

Installing package 'djangorestframework'...
App 'rest_framework' has been added to INSTALLED_APPS.

Configuration for: djangorestframework
  • URL Pattern: path('api-auth/', include('rest_framework.urls', namespace='rest_framework'))
  • Settings:
      REST_FRAMEWORK = {
          "DEFAULT_AUTHENTICATION_CLASSES": [
              "rest_framework.authentication.SessionAuthentication",
              "rest_framework.authentication.BasicAuthentication"
          ],
          "DEFAULT_PERMISSION_CLASSES": [
              "rest_framework.permissions.IsAuthenticated"
          ],
          "DEFAULT_RENDERER_CLASSES": [
              "rest_framework.renderers.JSONRenderer",
              "rest_framework.renderers.BrowsableAPIRenderer"
          ],
          "DEFAULT_PARSER_CLASSES": [
              "rest_framework.parsers.JSONParser",
              "rest_framework.parsers.FormParser",
              "rest_framework.parsers.MultiPartParser"
          ],
          "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
          "PAGE_SIZE": 10
      }

? Found additional configuration for package 'djangorestframework' (Space to toggle):
  [x] URL Patterns
  [x] Required Settings
? Proceed? Yes, apply changes

✅ Added URL pattern 'api-auth/'
✅ Added REST_FRAMEWORK settings

Installing package 'django-cors-headers'...
App 'corsheaders' has been added to INSTALLED_APPS.

Configuration for: django-cors-headers
  • Middleware: corsheaders.middleware.CorsMiddleware (position: before CommonMiddleware)
  • Settings:
      CORS_ALLOWED_ORIGINS = []
      CORS_ALLOW_CREDENTIALS = False
      CORS_ALLOW_ALL_ORIGINS = False

? Found additional configuration for package 'django-cors-headers' (Space to toggle):
  [x] Middleware
  [x] Required Settings
? Proceed? Yes, apply changes

✅ Added 'corsheaders.middleware.CorsMiddleware' to MIDDLEWARE
✅ Added CORS_ALLOWED_ORIGINS, CORS_ALLOW_CREDENTIALS, CORS_ALLOW_ALL_ORIGINS to settings

Installing package 'django-filter'...
App 'django_filters' has been added to INSTALLED_APPS.

Configuration for: django-filter
  • Settings:
      FILTERS_EMPTY_CHOICE_LABEL = "All"

? Found additional configuration for package 'django-filter' (Space to toggle):
  [x] Required Settings
? Proceed? Yes, apply changes

✅ Added FILTERS_EMPTY_CHOICE_LABEL to settings

? Add all packages to requirements.txt? Yes
Added 3 packages to requirements.txt

⚠️  The following package(s) require database migrations: djangorestframework, django-filter
? Run 'python manage.py migrate' now? Yes
Running migrations...
✅ Migrations applied successfully.
```

**Sample Output (unmapped package):**

```
Package 'my-custom-package' has been installed.
? Do you want to use the same name or a different one?
  > Use same
    Use different
    None/Skip
Package 'my-custom-package' not found in mappings.
Enter app name to add to INSTALLED_APPS: my_custom_app
App 'my_custom_app' has been added to INSTALLED_APPS.
? Save this mapping (my-custom-package → my_custom_app) for future use? Yes
Saved mapping: my-custom-package → my_custom_app
```

---

### `remove-app`

Remove one or more apps from `INSTALLED_APPS`, or scan for unused apps.

```
django-include-apps remove-app [app-name...] [OPTIONS]
```

| Option        | Short | Description                               |
| ------------- | ----- | ----------------------------------------- |
| `--start-dir` | `-d`  | Directory to search for `settings.py`     |
| `--ignore`    | `-i`  | Apps to protect from removal (repeatable) |

**Variants:**

```bash
# Scan for unused apps (interactive)
django-include-apps remove-app

# Remove specific app
django-include-apps remove-app rest_framework

# Remove multiple apps
django-include-apps remove-app rest_framework corsheaders django_filters

# Remove with protected apps
django-include-apps remove-app rest_framework corsheaders --ignore my_auth -i admin_custom

# Custom directory
django-include-apps remove-app -d /path/to/project
```

**Sample Output (scan unused):**

```
Scanning project for unused apps...

Found 3 unused app(s):
  • rest_framework
  • corsheaders
  • debug_toolbar

? Select apps to remove (use space to select, enter to confirm)
  ◉ rest_framework
  ◯ corsheaders
  ◉ debug_toolbar

App 'rest_framework' has been removed from INSTALLED_APPS.
App 'debug_toolbar' has been removed from INSTALLED_APPS.

? Remove selected packages from requirements.txt? Yes
Removed 2 packages from requirements.txt
```

**Sample Output (with extended config removal):**

```
The following apps will be removed:
  • rest_framework
  • corsheaders

Note: If any removed apps have database migrations, you will be prompted to run them.

? Are you sure you want to remove these 2 apps from INSTALLED_APPS? Yes

? Remove configuration for 'rest_framework'? (Settings) Yes
? Remove configuration for 'corsheaders'? (Middleware, Settings) Yes

App 'rest_framework' has been removed from INSTALLED_APPS.
App 'corsheaders' has been removed from INSTALLED_APPS.

⚠️  The following removed package(s) had database migrations: djangorestframework
? Run 'python manage.py migrate' now to clean up? Yes
Running migrations...
✅ Migrations applied successfully.
```

---

### `install-requirements`

Install packages from `requirements.txt` and add Django apps to `INSTALLED_APPS`.

```
django-include-apps install-requirements [OPTIONS]
```

| Option           | Short | Description                           |
| ---------------- | ----- | ------------------------------------- |
| `--requirements` | `-r`  | Path to `requirements.txt` (required) |
| `--start-dir`    | `-d`  | Directory to search for `settings.py` |

**Variants:**

```bash
# Standard usage
django-include-apps install-requirements -r requirements.txt

# Custom paths
django-include-apps install-requirements -r /path/to/requirements.txt -d /path/to/project
```

**Sample Output:**

```
Found 15 package(s) in requirements.txt
Installing packages from requirements.txt...
Successfully installed packages from requirements.txt

Detecting Django-related packages...
Found 5 Django package(s):
  • djangorestframework → rest_framework
  • django-cors-headers → corsheaders
  • django-filter → django_filters
  • django-allauth → allauth
  • celery (not mapped)

? Select packages to add to INSTALLED_APPS (use space to select, enter to confirm)
  [x] djangorestframework (rest_framework)
  [x] django-cors-headers (corsheaders)
  [ ] django-filter (django_filters)
  [x] django-allauth (allauth)
  [ ] celery (unmapped - will prompt for app name)

Adding selected packages to INSTALLED_APPS...

 IMPORTANT: Configurations applied are based on the latest package documentation.

✓ Added 'rest_framework' to INSTALLED_APPS
✓ Added 'corsheaders' to INSTALLED_APPS
✓ Added 'allauth' to INSTALLED_APPS

Done! 3 package(s) added to INSTALLED_APPS.

⚠️  The following package(s) require database migrations: djangorestframework, django-allauth
? Run 'python manage.py migrate' now? Yes
Running migrations...
✅ Migrations applied successfully.
```

---

## Information Commands

### `status`

Show current project configuration status.

```
django-include-apps status [OPTIONS]
```

| Option        | Short | Description                           |
| ------------- | ----- | ------------------------------------- |
| `--start-dir` | `-d`  | Directory to search for `settings.py` |

**Sample Output:**

```
┌──────────────────────────────────────────────────────────┐
│  Django Project Status                                   │
├──────────────────────────────────────────────────────────┤
│  Django Apps: 6                                          │
│  Third-party Apps: 5                                     │
└──────────────────────────────────────────────────────────┘

Third-party apps:
  ✓ rest_framework
  ✓ corsheaders
  ✓ django_filters
  ✓ allauth
  ✓ debug_toolbar

  requirements.txt: 12 packages
  Backups available: 3
```

---

### `doctor`

Run health checks on your Django project.

```
django-include-apps doctor [OPTIONS]
```

| Option        | Short | Description                           |
| ------------- | ----- | ------------------------------------- |
| `--start-dir` | `-d`  | Directory to search for `settings.py` |

**Sample Output:**

```
🏥 Doctor — Health Check
──────────────────────────

Environment:
  Python:    3.12.1
  Django:    5.1.4
  Tool:      1.1.0
  OS:        Windows 10

✅ settings.py found
✅ requirements.txt found
✅ package_configs.json: 76 packages

Passed:
   ✓ INSTALLED_APPS defined
   ✓ MIDDLEWARE defined
   ✓ ALLOWED_HOSTS configured

⚠️  Warnings:
   ! DEBUG is True (not safe for production)
   ! SECRET_KEY appears hardcoded (use env variable)
```

---

### `show-config`

Display the extended configuration available for a package.

```
django-include-apps show-config <package-name> [OPTIONS]
```

| Option   | Short | Description                   |
| -------- | ----- | ----------------------------- |
| `--json` |       | Output raw JSON configuration |

**Variants:**

```bash
# Human-readable format
django-include-apps show-config djangorestframework

# Raw JSON
django-include-apps show-config djangorestframework --json
```

**Sample Output (default):**

```
📦 djangorestframework Configuration
──────────────────────────────────────────────────

INSTALLED_APPS: rest_framework

Settings:
   REST_FRAMEWORK: {
       "DEFAULT_PERMISSION_CLASSES": [...]
   }

Dependencies: markdown, django-filter

Requires migrations: Yes
```

**Sample Output (`--json`):**

```json
{
  "installed_apps": "rest_framework",
  "middleware": null,
  "required_settings": {
    "REST_FRAMEWORK": {
      "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"]
    }
  }
}
```

---

### `view-mappings`

View all package-to-app-name mappings.

```
django-include-apps view-mappings [OPTIONS]
```

| Option        | Short | Description                                                 |
| ------------- | ----- | ----------------------------------------------------------- |
| `--filter`    | `-f`  | Filter packages by name (supports `django-*` wildcards)     |
| `--null-only` |       | Show dependency-only packages (not added to INSTALLED_APPS) |
| `--apps-only` |       | Show only packages that have app names                      |

**Variants:**

```bash
# View all
django-include-apps view-mappings

# Filter Django packages
django-include-apps view-mappings --filter "django-*"

# Only dependency packages
django-include-apps view-mappings --null-only

# Only packages with app names
django-include-apps view-mappings --apps-only
```

**Sample Output:**

```
Package Mappings (77 total)

Package Name              INSTALLED_APPS Name    Config
────────────────────────────────────────────────────────────
djangorestframework       rest_framework         [M, S, U]
django-cors-headers       corsheaders            [M, S]
django-filter             django_filters         -
django-environ            (not added)            [I]
gunicorn                  (not added)            -

Legend: [M]iddleware, [S]ettings, [U]rls, [I]mports
```

---

### `diff`

Preview changes that `add-app` would make — dry run, no files modified.

```
django-include-apps diff <package-name> [OPTIONS]
```

| Option        | Short | Description                           |
| ------------- | ----- | ------------------------------------- |
| `--start-dir` | `-d`  | Directory to search for `settings.py` |

**Sample Output:**

```
📋 Diff Preview — djangorestframework
──────────────────────────────────

settings.py:
  + 'rest_framework' → INSTALLED_APPS
  + REST_FRAMEWORK = {
  +     'DEFAULT_PERMISSION_CLASSES': [...],
  +     'DEFAULT_AUTHENTICATION_CLASSES': [...]
  + }

requirements.txt:
  + djangorestframework==3.15.2

No changes applied (dry-run).
```

---

### `sync`

Compare `INSTALLED_APPS` with `requirements.txt` and highlight mismatches.

```
django-include-apps sync [OPTIONS]
```

| Option        | Short | Description                           |
| ------------- | ----- | ------------------------------------- |
| `--start-dir` | `-d`  | Directory to search for `settings.py` |

**Sample Output:**

```
🔄 Sync Check
──────────────

In INSTALLED_APPS but not in requirements.txt:
  ⚠ rest_framework (djangorestframework)

In requirements.txt but not in INSTALLED_APPS:
  ⚠ django-filter (django_filters)

✓ 4 packages in sync
```

---

### `update-configs`

Check for updated package configurations and tool updates.

```
django-include-apps update-configs [OPTIONS]
```

| Option        | Short | Description                           |
| ------------- | ----- | ------------------------------------- |
| `--start-dir` | `-d`  | Directory to search for `settings.py` |

**Sample Output:**

```
Configuration Status
────────────────────────────────────────

package_configs.json: 76 packages, 73 mappings
  Location: .../django_include_apps/package_configs.json

To update to the latest configurations:
  pip install --upgrade django-include-apps
```

---

### `graph`

Visualize package dependency relationships.

```
django-include-apps graph [OPTIONS]
```

| Option        | Short | Description                           |
| ------------- | ----- | ------------------------------------- |
| `--start-dir` | `-d`  | Directory to search for `settings.py` |

**Sample Output:**

```
📈 Dependency Graph
──────────────────────

djangorestframework
  └─ (no dependencies)

channels
  ├─ daphne
  └─ channels-redis
       └─ channels
```

---

### `profile`

Save, apply, list, or export configuration profiles. See [Profile Subcommands](#profile-subcommands) for details.

```
django-include-apps profile <subcommand> [OPTIONS]
```

---

## Setup Commands

### `init-env`

Create a Python virtual environment.

```
django-include-apps init-env [OPTIONS]
```

| Option        | Short | Description                                         |
| ------------- | ----- | --------------------------------------------------- |
| `--python`    |       | Python version to use (e.g., `3.11`)                |
| `--name`      |       | Virtual environment directory name (default: `env`) |
| `--start-dir` | `-d`  | Directory to create the environment in              |

**Variants:**

```bash
# Default (creates ./env)
django-include-apps init-env

# Specific Python version
django-include-apps init-env --python 3.11

# Custom name
django-include-apps init-env --name .venv

# All options
django-include-apps init-env --python 3.11 --name .venv -d /path/to/project
```

**Sample Output:**

```
📄 Creating virtual environment...
✅ Created virtual environment at ./env
✅ Added 'env/' to .gitignore

To activate:
  Windows:  env\Scripts\activate
  Linux:    source env/bin/activate
```

---

### `secure-settings`

Move sensitive settings (`SECRET_KEY`, `DEBUG`, database passwords) to a `.env` file.

```
django-include-apps secure-settings [OPTIONS]
```

| Option        | Short | Description                           |
| ------------- | ----- | ------------------------------------- |
| `--start-dir` | `-d`  | Directory to search for `settings.py` |

**Sample Output:**

```
🔒 Securing sensitive settings...
✅ Created backup at .django-include-apps/backups/settings_20260221_120000.py.bak
✅ Moved SECRET_KEY to .env
✅ Moved DEBUG to .env
✅ Updated settings.py to read from environment
```

---

### `rollback`

Restore `settings.py` from a previous backup.

```
django-include-apps rollback [OPTIONS]
```

| Option        | Short | Description                           |
| ------------- | ----- | ------------------------------------- |
| `--start-dir` | `-d`  | Directory to search for `settings.py` |

**Sample Output:**

```
📂 Available Backups
──────────────
  1. settings_20260221_120000.py.bak  (2 minutes ago)
  2. settings_20260221_115500.py.bak  (7 minutes ago)

? Select backup to restore:  1
✅ Restored settings.py from backup
```

---

### `setup-hooks`

Set up pre-commit hooks for code quality.

```
django-include-apps setup-hooks [OPTIONS]
```

| Option        | Short | Description                     |
| ------------- | ----- | ------------------------------- |
| `--start-dir` | `-d`  | Directory to configure hooks in |

**Sample Output:**

```
🪝 Setting up pre-commit hooks...
✅ Created .pre-commit-config.yaml
✅ Installed pre-commit hooks

Hooks configured:
  • black (code formatting)
  • flake8 (linting)
  • isort (import sorting)
```

---

### `docker-init`

Generate Docker configuration files for your Django project.

```
django-include-apps docker-init [OPTIONS]
```

| Option        | Short | Description                         |
| ------------- | ----- | ----------------------------------- |
| `--start-dir` | `-d`  | Directory to create Docker files in |

**Sample Output:**

```
🐳 Docker initialization...
✅ Created Dockerfile
✅ Created docker-compose.yml
✅ Created .dockerignore
```

---

### `tutorial`

Interactive step-by-step guide to using django-include-apps.

```
django-include-apps tutorial
```

**Sample Output:**

```
📖 Interactive Tutorial
──────────────────────

Step 1/5: Adding Your First Package
  Run: django-include-apps add-app djangorestframework
  This will install the package, add it to INSTALLED_APPS,
  and offer to apply its recommended settings.

  Press Enter to continue...
```

---

### `completion`

Generate shell completion scripts.

```
django-include-apps completion [SHELL] [OPTIONS]
```

| Argument | Description                          |
| -------- | ------------------------------------ |
| `SHELL`  | Shell type: `bash`, `zsh`, or `fish` |

| Option      | Description                                |
| ----------- | ------------------------------------------ |
| `--install` | Install completion for the specified shell |

**Variants:**

```bash
# Show setup instructions
django-include-apps completion

# Install for bash
django-include-apps completion bash --install

# Install for zsh
django-include-apps completion zsh --install

# Install for fish
django-include-apps completion fish --install

# View script (manual install)
django-include-apps completion bash
```

**Sample Output:**

```
Shell completion setup:

Bash:
  django-include-apps completion bash --install
  Or manually: django-include-apps completion bash >> ~/.bashrc

Zsh:
  django-include-apps completion zsh --install
  Or manually: django-include-apps completion zsh >> ~/.zshrc

Fish:
  django-include-apps completion fish --install
  Or manually: django-include-apps completion fish > ~/.config/fish/completions/django-include-apps.fish
```

---

## Mapping Subcommands

Manage the package-to-app-name mapping database.

### `mapping list`

List all package mappings (same as `view-mappings`).

```
django-include-apps mapping list [OPTIONS]
```

| Option        | Short | Description                       |
| ------------- | ----- | --------------------------------- |
| `--filter`    | `-f`  | Filter packages by name           |
| `--null-only` |       | Show dependency-only packages     |
| `--apps-only` |       | Show only packages with app names |

---

### `mapping add`

Add a new package mapping.

```
django-include-apps mapping add <package-name> <app-name>
django-include-apps mapping add <package-name> --null
```

| Option   | Description                                           |
| -------- | ----------------------------------------------------- |
| `--null` | Mark as dependency-only (not added to INSTALLED_APPS) |

**Variants:**

```bash
# Add mapping
django-include-apps mapping add my-custom-package my_custom_app

# Add dependency-only
django-include-apps mapping add redis --null
```

**Sample Output:**

```
✅ Added mapping: my-custom-package → my_custom_app
```

---

### `mapping update`

Update an existing mapping.

```
django-include-apps mapping update <package-name> <new-app-name>
django-include-apps mapping update <package-name> --null
```

| Option   | Description               |
| -------- | ------------------------- |
| `--null` | Change to dependency-only |

**Sample Output:**

```
✅ Updated mapping: my-custom-package
  Old: my_custom_app
  New: new_app_name
```

---

### `mapping remove`

Remove a package mapping.

```
django-include-apps mapping remove <package-name> [OPTIONS]
```

| Option    | Short | Description              |
| --------- | ----- | ------------------------ |
| `--force` | `-f`  | Skip confirmation prompt |

**Variants:**

```bash
# With confirmation
django-include-apps mapping remove my-custom-package

# Skip confirmation
django-include-apps mapping remove my-custom-package --force
```

**Sample Output:**

```
Current mapping: my-custom-package → my_custom_app
? Remove this mapping? Yes
✅ Removed mapping: my-custom-package
```

---

## Profile Subcommands

Save and manage configuration profiles.

### `profile save`

Save current `INSTALLED_APPS` as a named profile.

```
django-include-apps profile save <name> [OPTIONS]
```

| Option        | Short | Description                           |
| ------------- | ----- | ------------------------------------- |
| `--start-dir` | `-d`  | Directory to search for `settings.py` |

**Sample Output:**

```
✅ Saved profile 'production' with 11 apps
```

---

### `profile apply`

Apply a saved profile to `INSTALLED_APPS`.

```
django-include-apps profile apply <name> [OPTIONS]
```

| Option        | Short | Description                           |
| ------------- | ----- | ------------------------------------- |
| `--start-dir` | `-d`  | Directory to search for `settings.py` |

**Sample Output:**

```
✅ Applied profile 'production'
  Added: 2 apps
  Removed: 1 app
```

---

### `profile list`

List all saved profiles.

```
django-include-apps profile list
```

**Sample Output:**

```
📋 Saved Profiles
──────────────
  production   (11 apps)   saved 2 days ago
  development  (14 apps)   saved 1 week ago
```

---

### `profile export`

Export a profile to a file.

```
django-include-apps profile export <name> [OPTIONS]
```

| Option     | Short | Description      |
| ---------- | ----- | ---------------- |
| `--output` | `-o`  | Output file path |

**Sample Output:**

```
✅ Exported profile 'production' to production_profile.json
```
