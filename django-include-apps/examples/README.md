# Django Include Apps — Example Project

This demo project shows how to use `django-include-apps` to manage a Django project's `INSTALLED_APPS` and settings.

## Setup

```bash
# 1. Install the tool
pip install django-include-apps

# 2. Navigate to the demo project
cd examples/demo_project

# 3. Try any command
django-include-apps add-app djangorestframework
django-include-apps add-app django-cors-headers
django-include-apps status
```

## What's Inside

| File                                 | Purpose                     |
| ------------------------------------ | --------------------------- |
| `demo_project/manage.py`             | Standard Django entry point |
| `demo_project/requirements.txt`      | Sample dependencies         |
| `demo_project/myproject/settings.py` | Minimal Django settings     |
| `demo_project/myproject/urls.py`     | URL configuration           |
| `demo_project/myproject/wsgi.py`     | WSGI application            |

## Quick Tour

### 1. Add a Package

```bash
django-include-apps add-app djangorestframework
```

This will:

- Install the package via pip
- Add `rest_framework` to `INSTALLED_APPS`
- Offer to apply extended config (middleware, settings, etc.)
- Update `requirements.txt`

### 2. View Mappings

```bash
django-include-apps view-mappings
```

See all 76+ supported package-to-app mappings.

### 3. Check Project Health

```bash
django-include-apps doctor
```

Run environment checks, verify configuration files, and detect issues.

### 4. See All Commands

```bash
django-include-apps --help
```

For detailed sample outputs, see the [Command Reference](../COMMANDS.md).
