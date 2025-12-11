# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.x.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

We take security seriously. If you discover a security vulnerability in RedGit, please report it responsibly.

### How to Report

1. **Do NOT open a public issue** for security vulnerabilities
2. Email the maintainers directly or use GitHub's private vulnerability reporting
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

### What to Expect

- **Acknowledgment**: Within 48 hours
- **Initial assessment**: Within 1 week
- **Resolution timeline**: Depends on severity

### Scope

Security issues we care about:

- Command injection vulnerabilities
- Credential exposure (API tokens, secrets)
- Arbitrary code execution
- Path traversal attacks
- Dependency vulnerabilities

### Out of Scope

- Issues requiring physical access
- Social engineering attacks
- Denial of service (DoS)

## Best Practices for Users

1. **Never commit API tokens** to config files
   ```yaml
   # Bad
   integrations:
     jira:
       token: "your-actual-token"

   # Good - use environment variables
   integrations:
     jira:
       token: ${JIRA_API_TOKEN}
   ```

2. **Use environment variables** for sensitive data
   ```bash
   export JIRA_API_TOKEN="your-token"
   export GITHUB_TOKEN="your-token"
   ```

3. **Review custom integrations** before installing from untrusted sources

4. **Keep RedGit updated** to get security patches
   ```bash
   pip install --upgrade redgit
   ```

## Security Features

RedGit includes these security measures:

- API tokens are never logged or displayed
- Secrets are masked in verbose output
- No telemetry or data collection
- All network requests use HTTPS

## Acknowledgments

We thank the security researchers who help keep RedGit safe. Contributors will be acknowledged here (with permission).