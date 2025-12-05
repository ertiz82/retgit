# Laravel Plugin

Laravel framework plugin for intelligent file grouping and Laravel-specific commit prompts.

## Overview

The Laravel plugin automatically detects Laravel projects and provides:
- Laravel version detection
- Framework file identification
- Optimized prompts for Laravel file grouping
- Separation of framework files from custom code

## Auto-Detection

The plugin automatically activates when:
1. `artisan` file exists in project root
2. `composer.json` contains `laravel/framework` dependency

## Features

### Version Detection

Automatically detects Laravel version from:
1. `composer.lock` (most accurate)
2. `composer.json` version constraint

```bash
rg propose
# Detected: Laravel 11.x project
```

### Framework File Identification

The plugin identifies default Laravel files:

**Root Files:**
- `artisan`, `composer.json`, `package.json`
- `vite.config.js`, `webpack.mix.js`
- `phpunit.xml`, `.env.example`

**Bootstrap:**
- `bootstrap/app.php`
- `bootstrap/providers.php`

**Config:**
- All files in `config/` directory

**Database:**
- Default migrations (users, cache, jobs, sessions)
- `DatabaseSeeder.php`, `UserFactory.php`

**Routes:**
- `routes/web.php`, `routes/api.php`
- `routes/console.php`, `routes/channels.php`

**Resources:**
- `welcome.blade.php`
- `resources/css/app.css`, `resources/js/app.js`

**App:**
- `app/Models/User.php`
- `app/Http/Controllers/Controller.php`
- Default middleware files
- `app/Providers/AppServiceProvider.php`

### Smart Grouping

Framework files are grouped separately from your custom code:

```
Group 1: "chore: add Laravel framework/scaffold files"
  - artisan
  - composer.json
  - config/app.php
  - routes/web.php
  - ...

Group 2: "feat: add user authentication"
  - app/Http/Controllers/AuthController.php
  - app/Models/User.php (modified)
  - resources/views/auth/login.blade.php
  - ...
```

## Configuration

Enable/disable via config:

```yaml
# .redgit/config.yaml
plugins:
  laravel:
    enabled: true
```

Or force Laravel plugin:

```bash
rg propose -p laravel
```

## Laravel Version Specific Notes

### Laravel 11+

- Simplified directory structure
- No `app/Http/Kernel.php` (middleware in `bootstrap/app.php`)
- Fewer default service providers
- Config files published on demand

### Laravel 10

- Traditional app structure
- Service providers in `app/Providers/`
- Middleware in `app/Http/Middleware/`

## Usage Examples

### Initial Laravel Project Setup

```bash
# Create new Laravel project
composer create-project laravel/laravel my-app
cd my-app

# Initialize redgit
rg init

# Propose commits for initial setup
rg propose
```

Output:
```
🔍 Detected Laravel 11.x project
📁 Found 87 files

Proposed groups:
  1. chore: add Laravel framework/scaffold files (72 files)
  2. chore: add project configuration (15 files)
```

### Adding New Feature

```bash
# After adding authentication feature
rg propose
```

Output:
```
Proposed groups:
  1. feat(auth): add user authentication
     - app/Http/Controllers/AuthController.php
     - app/Http/Requests/LoginRequest.php
     - resources/views/auth/login.blade.php
     - routes/auth.php
```

## Excluded Files

The plugin respects security exclusions:

**Always Excluded:**
- `.env` (sensitive data)
- `vendor/` (dependencies)
- `node_modules/` (dependencies)
- `storage/oauth-*.key` (private keys)
- `database/database.sqlite` (local database)

**Safe to Include:**
- `.env.example` (template)
- Custom migrations
- Test files

## Prompt Template

The Laravel plugin uses a specialized prompt:

```markdown
# Laravel {version} Project Commit Grouping

## CRITICAL RULES

1. **YOU MUST INCLUDE EVERY FILE**
2. **Framework/default files should be grouped together**
3. **Custom application code should be grouped by feature**

## File Categories

### Framework/Default Files (group together as "chore"):
- artisan, composer.json, package.json, vite.config.js
- bootstrap/app.php, bootstrap/providers.php
- config/*.php (default configs)
- ...

### Custom Application Files (group by feature):
- Custom models in app/Models/
- Custom controllers in app/Http/Controllers/
- Custom migrations, views, routes, tests
- ...
```

## Troubleshooting

### Plugin Not Detected

1. Ensure `artisan` file exists
2. Check `composer.json` has `laravel/framework`
3. Force with `-p laravel`:
   ```bash
   rg propose -p laravel
   ```

### Files Being Skipped

1. Check if files are in excluded patterns
2. Run with verbose mode:
   ```bash
   rg propose -v
   ```

### Wrong Version Detected

1. Run `composer update` to refresh `composer.lock`
2. Check version constraint in `composer.json`

## See Also

- [Plugins Overview](../plugins.md)
- [Version Plugin](version.md)
- [Changelog Plugin](changelog.md)