# Security Policy

## Reporting Security Vulnerabilities

If you discover a security vulnerability in Members Enquiries, **please do not open a public GitHub issue**. Instead, please report it privately to:

**Email:** shawn.carter@redcar-cleveland.gov.uk
**Name:** Shawn Carter, Digital Services Development Lead
**Organisation:** Redcar & Cleveland Borough Council

## What to Include

When reporting a vulnerability, please provide:
1. Description of the vulnerability
2. Steps to reproduce (if possible)
3. Potential impact (what could an attacker do?)
4. Suggested fix (if you have one)
5. Your name and contact information (optional, for credit)

## Response Timeline

We aim to:
- **Acknowledge** receipt within 48 hours
- **Confirm** the vulnerability within 7 days
- **Provide** a fix or mitigation plan within 30 days (depending on severity)
- **Release** a patched version as soon as possible

For critical security issues affecting active deployments, we will prioritise fixes and notify users immediately.

## Scope

This security policy covers vulnerabilities in:
- ✅ Python code in the `application/` and `project/` directories
- ✅ JavaScript code in the `static/` directory
- ✅ HTML templates in the `application/templates/` directory
- ✅ CSS stylesheets in the `static/css/` directory
- ✅ Configuration and deployment files

Out of scope:
- ❌ Third-party vendor libraries (contact the library maintainers)
- ❌ Issues in virtual environments or dependencies
- ❌ Vulnerabilities in deployment infrastructure (report to your hosting provider)

## Dependency Security

This project uses **Dependabot** to automatically track security updates for Python and JavaScript dependencies. Most security vulnerabilities will be identified and patched automatically.

For vulnerabilities not caught by Dependabot, or for security concerns about the application code itself, please use the reporting process above.

## Security Best Practices

### For Deployers

1. **Keep dependencies updated** - Run `pip install --upgrade -r requirements.txt` regularly
2. **Use environment variables** - Never commit `.env` files
3. **Enable HTTPS** - Always use HTTPS in production
4. **Set DEBUG=False** - Never deploy with `DEBUG=True`
5. **Use strong secrets** - Generate unique `DJANGO_SECRET_KEY` for each deployment
6. **Monitor logs** - Check application logs for suspicious activity
7. **Update Django/Python** - Apply security patches promptly

### For Contributors

1. **Validate all inputs** - Never trust user input
2. **Avoid SQL injection** - Use Django ORM, not raw SQL
3. **Prevent XSS attacks** - Use Django templates for rendering HTML
4. **Use CSRF tokens** - Built-in to Django forms
5. **Protect sensitive data** - Use environment variables for secrets
6. **Review CSP headers** - Content Security Policy prevents many attacks
7. **Test security** - Include security tests in test suite

## Azure AD Security Notes

- **Rotate secrets annually** - Set calendar reminders for App Secret rotation
- **Use strong redirect URIs** - Never use `127.0.0.1` in production (only `localhost` in dev)
- **Verify tenant ID** - Ensure Azure AD is configured for your organisation only
- **Monitor failed logins** - Check Azure AD logs for suspicious activity

## Known Issues

None currently documented. If you discover a vulnerability, please report it using the process above.

## Appreciation

We appreciate security researchers and developers who report vulnerabilities responsibly. We're committed to working with you to resolve issues and will give credit to reporters (with their permission).

---

**Last updated:** February 2026
**Policy version:** 1.0
