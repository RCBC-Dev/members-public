# Members Enquiries Application

A Django-based web application for managing council member enquiries with Azure AD authentication, email parsing, and some reporting tools.

## Features

### Enquiry Management
- **Create enquiries** - Manually create enquiries with member details, contacts, job types, and descriptions
- **Email integration** - Drag/Drop Emails from Outlook to automatically parse enquiry emails and create records with attachments
- **Edit enquiries** - Update enquiry details, reassign to different contacts, or change status
- **Reopen enquiries** - Reopen previously closed enquiries with updated information
- **Status tracking** - Track enquiry lifecycle: open, closed.
- **Service types** - Categorise enquiries by service type for reporting
- **Reference numbers** - Auto-generated unique references (e.g., MEM-26-0001) per enquiry

### Email & Attachment Handling
- **Automatic email parsing** - Extract enquiry information directly from email messages (supports .msg and .eml formats)
- **Attachment extraction** - Automatically extract and store images (JPG, PNG, GIF, WEBP, TIFF) and documents (PDF, DOC, DOCX) from emails
- **Image optimisation** - Automatically resize large images to optimise storage while maintaining quality
- **File management** - Store and retrieve all extracted documents and images with enquiries
- **Email conversation history** - Preserve full email conversation threads with enquiry records

### Enquiry Filtering & Search
- **Search by reference** - Find enquiries by their unique reference number
- **Filter by status** - View enquiries by status (open, pending, closed)
- **Filter by member** - Find all enquiries from a specific council member
- **Filter by ward** - View enquiries for a specific geographic ward
- **Filter by section** - Filter enquiries by responsible department section
- **Filter by job type** - Find enquiries by type of work (pothole repair, housing issue, etc.)
- **Filter by service type** - Categorise enquiries by service area
- **Filter by contact** - Find enquiries assigned to a specific contact
- **Date range filtering** - Search enquiries by creation date or custom date ranges
- **Overdue tracking** - Quickly identify enquiries exceeding response time targets
- **Search text** - Full-text search across enquiry titles and content

### Reporting & Analytics
- **Performance dashboard** - Overview of enquiry metrics and system health
- **Response time analysis** - Track average time to close enquiries by section and job type
- **Overdue enquiries** - Monitor enquiries that have exceeded expected response times
- **Enquiry distribution reports** - View enquiry counts by section, job type, member, and other attributes
- **Drilldown capability** - Click through reports to view detailed enquiry lists filtered by the selected attribute (member, job type, section, etc.)
- **Monthly trends** - Track enquiries created and resolved per month
- **Detailed reports** - Generate CSV exports for further analysis

### Administration & Data Management
- **Admin interface** - Django admin at `/admin/` for direct database management
- **Member management** - Add, edit, and manage council members with ward assignments and active/inactive status
- **Contact management** - Maintain contact details, link contacts to departments (sections), geographic areas, and job types
- **User management** - Create and manage admin users with appropriate permissions
- **Audit logging** - Track all user actions for security and compliance (who made changes, when, and what happened)
- **Data integrity** - Automatic enforcement of relationships between entities (no orphaned data)

### Security & Access Control
- **Azure AD integration** - Single sign-on with Azure Entra ID (formerly Azure AD)
- **Role-based access** - Users need to be in Admin group to create new enquiries (could allow Members Read Access)
- **Content Security Policy** - Strict CSP to prevent XSS and injection attacks
- **CSRF protection** - Built-in Django CSRF token protection
- **Secure headers** - HTTP security headers for production deployments
- **Input validation** - Validation of all user inputs

## Screenshots

### Welcome Page
![Welcome Page](screenshots/welcome.jpeg)
*Welcome page with Sign in with Microsoft*

### Enquiry Management
![Create Enquiry](screenshots/create_enquiry.jpeg)
*Create a new enquiry with member details, contacts, and attachments (member will be selected if their email matches)*

![Enquiry List](screenshots/enquiry_list.jpeg)
*Enquiries list with comprehensive filtering and search options*

![Enquiry Details](screenshots/enquiry_details.jpeg)
*Detailed enquiry view with history, attachments, and action buttons*

![Close Enquiry](screenshots/close_enquiry.jpeg)
*Close enquiry dialog with Service Type*

### Reporting & Analytics
![Performance Dashboard](screenshots/performance_dashboard.jpeg)
*Performance dashboard with key metrics and enquiry statistics*

![Enquiries Per Member Report](screenshots/enquires_per_member.jpeg)
*Report showing enquiries per member with drilldown capability to view detailed enquiry lists*

### Administration
![File Management](screenshots/file_management.jpeg)
*File management interface for organising enquiry attachments and documents  - removing orphaned documents, resizing images etc*

## Quick Start

### Prerequisites
- Python 3.13+
- Git
- pip (included with Python)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/RCBC-Dev/members-public.git
   cd members-public
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   ```

3. **Activate the virtual environment**

   **Windows (PowerShell):**
   ```powershell
   .\venv\Scripts\Activate.ps1
   ```

   **Windows (Command Prompt):**
   ```cmd
   venv\Scripts\activate.bat
   ```

   **Linux/macOS:**
   ```bash
   source venv/bin/activate
   ```

4. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

   **What does this do?** The `requirements.txt` file contains a list of Python libraries (called "packages") that this application needs to run. These include Django (the web framework), libraries for Azure authentication, database drivers, and many others. `pip install` downloads and installs all these packages so the application can use them.

5. **Run migrations**
   ```bash
   python manage.py migrate
   ```

   **What does this do?** Migrations create and update your database structure to match the application's data models. When you run migrate, Django creates all the necessary tables (members, enquiries, contacts, etc.) and fields in the database. This happens automatically - you only need to run it once when first setting up, or when you pull code changes that modify the database structure. Since this installation uses a flattened migration, it's a single step instead of applying 20+ individual migrations.

6. **Populate test data (optional, for development)**
   ```bash
   python manage.py populate_test_data
   ```

   **What does this do?** This creates sample data in the database so you can test the application without manually entering everything. It creates example members, wards, departments, contacts, and job types that you can use to create enquiries.

7. **Create a superuser**
   ```bash
   python manage.py createsuperuser
   ```

   **What does this do?** A superuser is an administrator account that has access to the Django admin interface at `/admin/`. This is useful for managing users and data directly. You will need at least one admin user, this admin user can adjust user accounts (to give them admin), to create/edit data such as members, departments, sections, job types. You can also use a superuser account to test the application in Development (prior to interfacing with Azure Entra).

8. **Start the development server**
   ```bash
   python manage.py runserver
   ```

   Access the application at `http://localhost:8000`

### Development Login Options

**Option 1: Using Azure AD (Recommended)**
Log in using your Azure AD account. You'll need to set up Azure AD first (see Azure AD Configuration below).

**Option 2: Using Django Admin (Development Only)**
If you want to test the application without Azure AD setup:

1. Create a Django superuser account:
   ```bash
   python manage.py createsuperuser
   ```
   Follow the prompts to create a username and password.

2. Log in at `http://localhost:8000/admin/` with your superuser credentials

3. Create an Admin record for your user:
   - Go to **Members App** → **Admins**
   - Click **Add Admin**
   - Select your user account
   - Save

**Important**: Whether you use Azure AD or Django admin login, you must add your account to Admin table, to have the ability to create new enquiries. Users not in Admin record can still view the application.

## Azure AD Configuration

This application uses Azure Active Directory for authentication. Follow these steps to set it up.

### Register an Application in Azure

1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to **Azure Active Directory** → **App registrations** → **New registration**
3. Enter application details:
   - **Name**: Members Enquiries Application
   - **Supported account types**: Choose based on your organisation's needs
4. Click **Register**

### Retrieve Credentials

After registration, you'll need three pieces of information:

- **App ID (Client ID)**: Found in the **Overview** section
- **Tenant ID**: Found in the **Overview** section
- **App Secret**: Create in **Certificates & secrets** → **Client secrets** → **New client secret**
  - Give it a meaningful description
  - Select an appropriate expiration (consider a yearly rotation policy)
  - Copy the secret value immediately (you won't be able to see it again)

### Configure Redirect URIs

1. Go to **Authentication** in your app registration
2. Add Redirect URIs for each environment:
   - **Development**: `http://localhost:8000/accounts/microsoft/login/callback/`
   - **Testing**: `https://your-test-domain.org/accounts/microsoft/login/callback/`
   - **Production**: `https://your-production-domain.org/accounts/microsoft/login/callback/`

**Important**: Use `localhost` (not `127.0.0.1`) for development mode. Azure AD will reject `127.0.0.1` as a security measure.

**Note**: Replace `your-test-domain.org` and `your-production-domain.org` with your actual domain names where the application will be hosted.

### Environment Configuration

1. **Copy the example file**:
   ```bash
   copy .env.example .env
   ```

2. **Edit `.env` with your credentials**:
   ```env
   DJANGO_SETTINGS_MODULE=project.settings.development
   ENVIRONMENT=DEVELOPMENT
   COUNCIL_NAME=Your Council Name
   DOMAIN=localhost

   # Azure Entra ID Configuration (optional for development)
   # AZURE_CLIENT_ID=your-app-id-here
   # AZURE_CLIENT_SECRET=your-app-secret-here
   # AZURE_TENANT_ID=your-tenant-id-here

   # Database Configuration (not required for development - uses SQLite)
   # DATABASE_NAME=members_db
   # DATABASE_USER=sa
   # DATABASE_PASSWORD=your-password
   # DATABASE_HOST=localhost
   # DATABASE_PORT=1433
   ```

**Security Note**: The `.env` file is already excluded from version control via `.gitignore`. Never commit the `.env` file as it contains sensitive credentials.

Remove the # to uncomment a line

## Environment-Specific Configuration

The application uses three settings files, one per environment:
- `project/settings/development.py` - Local development (SQLite, no HTTPS)
- `project/settings/test.py` - Test server
- `project/settings/production.py` - Production deployment

**You do not need to edit any settings file.** All environment-specific values — domain, database credentials, Azure credentials, secret key, and council name — are read from the `.env` file. The settings file to use is itself selected via `DJANGO_SETTINGS_MODULE` in `.env`.

### Setting Up an Environment

When cloning the project for a new environment, create a fresh `.env` file from the template:

```bash
copy .env.example .env
```

Then edit `.env` with the values for that environment. **Each environment (development, test, production) should have its own `.env` file** — never share or copy `.env` files between environments, as they contain unique secrets and domain values.

### Key `.env` Variables by Environment

| Variable | Development | Test | Production |
|---|---|---|---|
| `DJANGO_SETTINGS_MODULE` | `project.settings.development` | `project.settings.test` | `project.settings.production` |
| `ENVIRONMENT` | `DEVELOPMENT` | `TEST` | `PRODUCTION` |
| `DOMAIN` | `localhost` | `your-test-domain.org` | `your-production-domain.org` |
| `COUNCIL_NAME` | Your council name | Your council name | Your council name |
| `DJANGO_SECRET_KEY` | *(not required)* | Required | Required |
| `DATABASE_*` | *(not required — uses SQLite)* | Required | Required |
| `AZURE_CLIENT_ID` etc. | Optional | Required | Required |

**Generating a secret key** for test/production:
```bash
python manage.py shell -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### How Domain Configuration Works

Setting `DOMAIN` in `.env` automatically configures:
- `ALLOWED_HOSTS` — accepts requests for that domain
- `CSRF_TRUSTED_ORIGINS` — allows form submissions from `https://<DOMAIN>`
- `CORS_ALLOWED_ORIGINS` — restricts cross-origin requests to `https://<DOMAIN>`
- **CORS headers on static files** — `whitenoise_headers.py` reads `DOMAIN` and `ENVIRONMENT` from the environment and sets `Access-Control-Allow-Origin` accordingly (using `https` for test/production and `http` for development)

No manual changes to settings files or `whitenoise_headers.py` are needed.

### Content Security Policy (CSP)

The application implements a strict Content Security Policy to prevent security vulnerabilities like XSS attacks. When making changes:
- **Avoid inline CSS and JavaScript** where possible - use classes and external stylesheets instead
- If inline code is absolutely necessary, use `nonce="{{ request.csp_nonce }}"` in script/style tags:
  ```html
  <style nonce="{{ request.csp_nonce }}">
    /* inline styles here */
  </style>
  ```
- Move CSS to `static/custom.css` and apply using classes:
  ```html
  <div class="my-custom-class">Content</div>
  ```
- Use locally-hosted stylesheets and scripts, not external CDNs (unless explicitly allowed in CSP settings)

## Populating Test Data

To quickly set up a development environment with sample data:

```bash
python manage.py populate_test_data
```

This command creates:
- **Wards**: 7 sample wards (Civic Centre, Riverside, Hillside, etc.)
- **Areas**: 6 areas for organising enquiries geographically
- **Departments**: 7 departments (Planning, Highways, Housing, etc.)
- **Sections**: 8 sections within departments
- **Job Types**: 9 common job types (Pothole Repair, Planning Query, Housing Issue, etc.)
- **Contacts**: 6 contact records linked to sections
- **Members**: 12 sample council members with UK names (John Smith, Sarah Johnson, etc.)

This data allows you to immediately start creating and testing enquiries without manual data entry. You can run this command multiple times safely - it won't create duplicates.

## Running Tests

Run the test suite:
```bash
python -m pytest
```

Run specific test file:
```bash
python -m pytest tests/test_models.py -v
```

Run with coverage:
```bash
python -m pytest --cov=application --cov=project --cov-report=term-missing
```

## Code Quality - SonarQube

[![Quality Gate Status](screenshots/quality_gate.svg)](screenshots/quality_gate.svg)

[SonarQube](https://www.sonarsource.com/products/sonarqube/) is an open-source static analysis platform that inspects code for bugs, vulnerabilities, code smells, and test coverage. It provides a Quality Gate - a set of conditions a project must meet before it is considered production-ready.

This project was analysed using SonarQube Community Edition, running locally under WSL (Windows Subsystem for Linux).

### Quality Gate Results

The project passes the SonarQube Quality Gate with the following overall code metrics:

![SonarQube Quality Gate Passed](screenshots/sonarqube_pass_quality_gate.jpeg)

| Metric | Result | Rating |
|---|---|---|
| Security | 0 open issues | A |
| Reliability | 0 open issues | A |
| Maintainability | 0 open issues | A |
| Test Coverage | 80.5% (on 5.4k lines) | - |
| Duplications | 4.4% (on 24k lines) | - |
| Accepted Issues | 4 | - |

**Accepted Issues**: The 4 accepted issues are form views that handle both `GET` and `POST` requests - this is intentional Django patterns and expected behaviour rather than a security concern.

**Duplications**: The 4.4% duplication figure is primarily attributable to the copyright/licence header that appears on every `.py`, `.html`, `.js`, and `.css` file as required by the GNU AGPL v3.0 licence.

### Test Coverage by Module

![SonarQube Test Coverage](screenshots/sonarqube_test_coverage.jpeg)

| Module | Lines of Code | Coverage |
|---|---|---|
| application | 16,215 | 79.7% |
| project | 852 | 91.3% |
| **Total** | **17,067** | **80.5%** |

## Development Server Management

The development server is typically run in a separate terminal:
```bash
python manage.py runserver
```

**Note**: The server must be running separately. Don't start it in the background from scripts.

## Dependency Management

The project uses a three-tier dependency management system to balance stability with security updates:

### Understanding the Three Requirements Files

1. **`requirements.txt`** (Pinned versions with `==`)
   - Used for production and reproducible deployments
   - Ensures exact same versions run everywhere
   - Created by `pip freeze > requirements.txt`
   - Provides maximum stability but won't update automatically

2. **`update_requirements.txt`** (Compatible release with `~=`)
   - Used for conservative patch and minor version updates
   - `pillow~=12.1.0` allows 12.1.1, 12.1.2, but NOT 12.2.0
   - Safe for regular updates to get security patches without breaking changes

3. **`upgrade_requirements.txt`** (Permissive with `>=`)
   - Used for major version upgrades
   - Installs latest compatible versions of all dependencies
   - Useful for testing new features and resolving security vulnerabilities across major versions

### Regenerating the Update and Upgrade Files

`update_requirements.txt` and `upgrade_requirements.txt` are derived from `requirements.txt` and should be regenerated whenever `requirements.txt` changes (e.g. after adding a new package or running `pip freeze`).

```bash
python generate_requirements.py
```

This reads `requirements.txt` and writes both files, replacing `==` with the appropriate operator:
- `~=` in `update_requirements.txt` — allows patch updates within the same minor version (e.g. `Django~=5.2.11` permits 5.2.12 but not 5.3.0)
- `>=` in `upgrade_requirements.txt` — allows any newer version

Post-release suffixes such as `.post0` are stripped automatically so the `~=` operator remains valid (e.g. `python-dateutil==2.9.0.post0` becomes `python-dateutil~=2.9.0`).

**When to run it:**
- After installing a new package and freezing (`pip freeze > requirements.txt`)
- After running a major upgrade cycle and locking in the new versions
- Before committing dependency changes, so all three files stay in sync

### Updating Dependencies

**For regular security patches (recommended):**
```bash
pip install -r update_requirements.txt
```

**For major version upgrades (when needed):**
```bash
pip install -r upgrade_requirements.txt
```

**Validation steps (BEFORE freezing):**

1. **Check for configuration issues:**
   ```bash
   python manage.py check
   ```
   This validates your Django configuration and models for any compatibility issues or deprecation warnings.

2. **Run the full test suite:**
   ```bash
   python -m pytest
   ```
   Ensures all dependencies are compatible and there are no deprecated features in use.

**If validation passes, lock in the changes:**
```bash
pip freeze > requirements.txt
git add requirements.txt
git commit -m "Update dependencies"
```

**If validation fails, revert to the previous working state:**
```bash
pip install -r requirements.txt
```
This restores your last known good dependency set from the original `requirements.txt`.

**Important**: Always validate BEFORE freezing. This way, if something breaks, you can easily rollback by reinstalling from your current `requirements.txt` without needing to restore files from git.

## Database Migrations

Create a new migration after model changes:
```bash
python manage.py makemigrations
```

Apply migrations:
```bash
python manage.py migrate
```

For production deployments, a single consolidated migration is preferred to avoid running 20+ individual migrations.

### Database Indexes

The application includes carefully designed database indexes for optimal query performance:

**Primary Lookup Indexes:**
- `Area.name`, `Department.name`, `Section.name`, `Ward.name`, `JobType.name` - unique lookups
- `ReferenceSequence.year` - reference number generation
- `Contact.name` - contact lookups
- `Member.email` - member searches
- `Enquiry.reference` - unique enquiry references

**Common Query Indexes:**
- `Member`: (ward, is_active), (email), (first_name, last_name)
- `Enquiry`: Multiple indexes for status, created_at, member, section, admin, contact, job_type, and title lookups
- `EnquiryHistory`: (enquiry, created_at) for timeline queries
- `EnquiryAttachment`: (enquiry, uploaded_at) for attachment retrieval
- `Audit`: (user, action_datetime) and (enquiry, action_datetime) for audit trails
- `Contact`: (section) for section-based filtering

These indexes ensure that the most common queries run efficiently, particularly filtering enquiries by status, member, section, and retrieval of related records. The indexes were validated and added during setup.

## Git Hooks and Automatic Version Management

This project includes Git hooks that automatically validate code quality and update version numbers on commits.

### Setting Up Git Hooks

```bash
python setup_git_hooks.py
```

This script sets up two Git hooks:

1. **pre-commit hook** - Automatically runs all tests before allowing a commit. If any tests fail, the commit is rejected until you fix the issues.
2. **commit-msg hook** - Automatically updates the version number in `project/version.py` based on your commit message

### Using commit.bat (Recommended)

The easiest way to commit changes is using the `commit.bat` script:

```bash
commit.bat "Your descriptive commit message here"
```

**What it does:**
- Stages all changes with `git add .`
- Runs tests via the pre-commit hook
- If tests pass, creates the commit with your message
- Automatically updates the version number in `project/version.py`
- Amends the commit to include the version update (without running tests again)

**Benefits over `git commit -m`:**
- ✅ Ensures tests pass before committing
- ✅ Automatically increments version numbers (patch, minor, or major based on commit message)
- ✅ Version history is tracked automatically - no manual version bumping needed
- ✅ Cleaner workflow - one command does everything
- ✅ Prevents broken code from being committed
- ✅ Cross-platform (Windows, Mac, Linux)

### Manual Commit Process

If you prefer manual control, you can still use `git commit`:

```bash
git add .
git commit -m "Your commit message"
```

The hooks will still run automatically. If you want to skip version updates, include `[skip version]` in your message:

```bash
git commit -m "Your message [skip version]"
```

## Static Files

Collect static files for production:
```bash
python manage.py collectstatic --noinput
```

## Troubleshooting

### "Apps aren't loaded yet" Error
Ensure the `DJANGO_SETTINGS_MODULE` environment variable is set or pytest-django is properly configured in `pytest.ini`.

### Azure Authentication Failures
- Verify redirect URIs in Azure AD match exactly (including protocol and trailing slash)
- Use `localhost` not `127.0.0.1` in development
- Check that App Secret hasn't expired
- Ensure environment variables are correctly set in `.env`

### Database Connection Issues
- Verify database credentials in `.env`
- Ensure SQL Server is running and accessible
- For SQLite (development): check file permissions
- Run `python manage.py dbshell` to test connection

## Security Considerations

1. **Secret Key**: Change `DJANGO_SECRET_KEY` in `.env` for each deployment
2. **Debug Mode**: Set `DEBUG=False` in production
3. **HTTPS**: Always use HTTPS in production
4. **CORS**: Keep CORS origins as restrictive as possible
5. **CSP**: Review and maintain Content Security Policy headers
6. **Dependencies**: Regularly update packages to patch security vulnerabilities - see [Dependency Management](#dependency-management) section
7. **Azure Secrets**: Rotate Azure App Secrets annually
8. **Environment Variables**: Never commit `.env` to version control

## Deployment

### Hosting Options

This application can be deployed to various hosting environments:

**Current Setup: IIS (Windows Server)**
- Uses IIS with **HTTPPlatformHandler**
- Runs **Waitress** WSGI server as the application server
- Supports large file uploads (up to 100MB for email processing)
- Includes security headers (HSTS, CSP, etc.)

**Alternative Hosting**
- **Azure App Service** - Native Azure hosting with integrated monitoring
- **Cloud Providers** - AWS, Google Cloud, DigitalOcean, or other cloud platforms
- **Docker** - Containerize the application for any Docker-compatible platform
- **Linux Servers** - Deploy using gunicorn or other Python WSGI servers

### IIS Configuration (Windows Server)

1. **Create web.config from template**:
   ```bash
   copy webconfig.template web.config
   ```

2. **Update paths in web.config**:
   - Replace `C:\path\to\members-public` with your actual installation path
   - Update `processPath` to point to your virtual environment's `python.exe`
   - Update `arguments` to point to your `serve.py` file
   - Update `stdoutLogFile` path for logs
   - Set correct `DJANGO_SETTINGS_MODULE` (test, production, etc.)

3. **Key configuration parameters**:
   - `maxAllowedContentLength="104857600"` - 100MB limit for email attachments
   - `startupTimeLimit="120"` - 2 minute startup timeout
   - Security headers for HTTPS and protection against common attacks

4. **Install prerequisites**:
   - IIS with URL Rewrite and Application Request Routing (ARR) modules
   - Python 3.13 (or compatible version)
   - All packages from `requirements.txt`

### Database Configuration

The application supports multiple database backends. All connection details — including the engine — are set in `.env`. No changes to settings files are needed to switch databases.

**Development** (Default)
- SQLite — no configuration needed, uses `db.sqlite3` automatically

**Test / Production** — set these in `.env`:

```env
DATABASE_ENGINE=mssql
DATABASE_NAME=your_database_name
DATABASE_USER=your_database_user
DATABASE_PASSWORD=your_database_password
DATABASE_HOST=your.sql.server.address
DATABASE_PORT=1433
```

To use a different backend, change `DATABASE_ENGINE`:

| Backend | `DATABASE_ENGINE` value | Driver package |
|---|---|---|
| Microsoft SQL Server | `mssql` | `mssql-django` (included) |
| PostgreSQL | `django.db.backends.postgresql` | `pip install psycopg2-binary` |
| MySQL | `django.db.backends.mysql` | `pip install mysqlclient` |

When `DATABASE_ENGINE=mssql`, the settings automatically include the required ODBC options (`ODBC Driver 17 for SQL Server`). If you have ODBC Driver 18 installed, update the `driver` value in `project/settings/test.py` or `production.py`.

### Environment Variables for Deployment

Ensure these are set on your production server:

```env
DJANGO_SETTINGS_MODULE=project.settings.production
ENVIRONMENT=PRODUCTION
COUNCIL_NAME=Your Council Name
DOMAIN=your-production-domain.org
DJANGO_SECRET_KEY=your-secret-key-here

# Database
DATABASE_ENGINE=mssql
DATABASE_NAME=enquiries_db
DATABASE_USER=db_user
DATABASE_PASSWORD=secure-password
DATABASE_HOST=db-server.example.com
DATABASE_PORT=1433

# Azure AD
AZURE_CLIENT_ID=your-app-id
AZURE_CLIENT_SECRET=your-secret
AZURE_TENANT_ID=your-tenant-id
```

### Deployment Checklist

- [ ] Copy `webconfig.template` to `web.config` (IIS only)
- [ ] Update all paths in web.config for IIS deployment
- [ ] Create `.env` from `.env.example` with production values
- [ ] Set `DJANGO_SETTINGS_MODULE=project.settings.production` in `.env`
- [ ] Set `DOMAIN=your-production-domain.org` in `.env`
- [ ] Set `DJANGO_SECRET_KEY` to a new generated key in `.env`
- [ ] Set database credentials in `.env`
- [ ] Set Azure AD credentials in `.env`
- [ ] Run `python manage.py collectstatic --noinput`
- [ ] Run `python manage.py migrate` on production database
- [ ] Test Azure AD login (if configured)
- [ ] Verify logs folder has write permissions
- [ ] Set up log rotation for production logging

## License

This software is licensed under the GNU Affero General Public License v3.0.
Copyright © 2026 Redcar & Cleveland Borough Council.

For the full license terms, see [LICENSE.md](LICENSE.md).

This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, version 3.

This program is distributed in the hope that it will be useful, but without any warranty; without even the implied warranty of merchantability or fitness for a particular purpose. See the GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License along with this program. If not, see <https://www.gnu.org/licenses/>.

Should you need to contact the copyright holder, you can email [shawn.carter@redcar-cleveland.gov.uk](mailto:shawn.carter@redcar-cleveland.gov.uk).

If you need clarification on the above licensing you can email [legalservices@rcbcgov.onmicrosoft.com](mailto:legalservices@rcbcgov.onmicrosoft.com).

## Contributing

We welcome contributions from councils, developers, and the open source community! Whether it's bug fixes, security improvements, documentation, or new features, your help is appreciated.

**Before you start:** Please read [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to contribute, what we accept, and how to submit pull requests.

**Discuss first:** For new features or major changes, please open an issue to discuss before coding.

**Contact:** shawn.carter@redcar-cleveland.gov.uk

## Security

If you discover a security vulnerability, please **do not open a public issue**. Instead, email:
**shawn.carter@redcar-cleveland.gov.uk**

For full details, see [SECURITY.md](SECURITY.md).

## Support

For deployment support or questions about configuration, contact your internal IT department or the development team.

**Repository**: https://github.com/RCBC-Dev/members-public
