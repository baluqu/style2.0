# StyleBridge Security Guide

## Overview

StyleBridge is a **secure 3D fashion virtual try-on web application** built with Flask. This guide covers all security features and best practices.

---

## Security Features

### 1. **Security Headers (Flask-Talisman)**

All responses include these security headers:

- **HSTS (Strict-Transport-Security)**: Enforces HTTPS for 1 year  
- **CSP (Content-Security-Policy)**: Prevents XSS attacks, restricts script sources
- **X-Frame-Options**: `DENY` - prevents clickjacking
- **X-Content-Type-Options**: `nosniff` - prevents MIME-type sniffing
- **X-XSS-Protection**: Enables browser XSS filters
- **Referrer-Policy**: `strict-origin-when-cross-origin`
- **Frame-Ancestors**: Prevents embedding in iframes

### 2. **Session & Cookie Security**

All cookies are protected with:

- **HTTPOnly**: Prevents JavaScript access (XSS protection)
- **Secure**: Only transmitted over HTTPS (dev: False for localhost)
- **SameSite=Lax**: Prevents CSRF attacks
- **Unique Names**: `__Secure-Session` and `__Secure-Remember` prefixes
- **Timeout**: 1 hour default (configurable via `PERMANENT_SESSION_LIFETIME`)

### 3. **CSRF Protection (Flask-WTF)**

All forms automatically include CSRF tokens. POST requests require valid tokens.

### 4. **Rate Limiting (Flask-Limiter)**

Prevents brute force and spam attacks:

- **Login**: 10 attempts per hour
- **Registration**: 5 attempts per hour  
- **File Upload**: 10 uploads per hour
- **Admin Operations**: 5 operations per hour

### 5. **Input Validation & Sanitization**

All user inputs are validated:

- **File Uploads**: 
  - Whitelist: PNG, JPG, JPEG, GIF, WebP only
  - Size limit: 8 MB (configurable)
  - Filenames secured with `secure_filename()`

- **Text Inputs**:
  - HTML escaping to prevent XSS
  - Length limits enforced
  - Whitespace trimmed

- **URLs**:
  - Must start with `http://` or `https://`
  - Length limits enforced
  - Validated before storage

- **Numeric Inputs**:
  - Price validation: 0 to 999,999
  - Type checking
  - Default to safe values on error

- **CSV/JSON Imports**:
  - File type validation
  - Proper error handling
  - All values sanitized before insertion

### 6. **Authentication & Authorization**

- **Password Hashing**: Werkzeug's strong hashing (PBKDF2 + SHA-256)
- **Role-Based Access Control (RBAC)**:
  - `user`: Basic user role
  - `inventory_manager`: Can manage inventory
  - `admin`: Full admin privileges  
  - `superadmin`: System administrator

- **Permission-Based Decorators**: Routes check permissions before execution
- **Audit Logging**: All sensitive actions logged with IP, user-agent, timestamp

### 7. **3D Scene Security**

The Three.js 3D scene includes:

- **Error Handling**: Graceful fallback if WebGL unavailable
- **Context Menu Prevention**: Prevents right-click exploitation
- **Performance Optimization**: GPU-friendly rendering settings
- **Memory Safe**: Proper cleanup and garbage collection

### 8. **HTTPS/TLS Configuration**

- **Development**: HTTP on localhost (or HTTPS if certs exist)
- **Production**: HTTPS enforced, session cookies secure
- **Certificate Support**: 
  - Self-signed certificates (development)
  - Production certificates (Let's Encrypt recommended)

### 9. **Database Security**

- **SQL Injection Prevention**: SQLAlchemy ORM with parameterized queries
- **Prepared Statements**: All queries use ORM, no raw SQL
- **Connection Security**: HTTPS connection strings enforced

### 10. **Open Redirect Prevention**

- **Safe Redirect**: Login redirect only to internal URLs
- **URL Validation**: No external redirects allowed

---

## Setup Instructions

### 1. Generate Secure Secrets

```bash
# Generate SECRET_KEY
python -c "import secrets; print(secrets.token_hex(32))"

# Generate ADMIN_KEY  
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 2. Create .env File

```bash
cp .env.example .env
# Edit .env with your values
```

### 3. Generate SSL Certificates (Optional, for HTTPS)

```bash
# Self-signed certificate (valid 365 days)
openssl req -x509 -newkey rsa:4096 -nodes -out cert.pem -keyout key.pem -days 365

# Production: Use Let's Encrypt
# certbot certonly --standalone -d yourdomain.com
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Initialize Database

```bash
python -c "from app import create_app, db; app=create_app(); app.app_context().push(); db.create_all(); print('✓ Database initialized')"
```

### 6. Run Application

```bash
# Development (HTTP on localhost)
export FLASK_ENV=development
python run.py

# Production (HTTPS required)
export FLASK_ENV=production
python run.py
```

---

## Environment Variables

### Required

- **`SECRET_KEY`**: Flask session encryption key (32+ bytes)
- **`ADMIN_KEY`**: Bootstrap admin key (random string)

### Optional

- **`FLASK_ENV`**: `development` or `production` (default: production)
- **`DATABASE_URL`**: Database connection string (default: SQLite)
- **`UPLOAD_FOLDER`**: Upload directory (default: `app/static/uploads`)
- **`MAX_UPLOAD_MB`**: Max upload size (default: 8)
- **`SSL_CERT_FILE`**: SSL certificate path (default: `cert.pem`)
- **`SSL_KEY_FILE`**: SSL key path (default: `key.pem`)
- **`FORCE_HTTPS`**: Enforce HTTPS (default: True in production)
- **`PERMANENT_SESSION_LIFETIME`**: Session timeout seconds (default: 3600)

---

## Best Practices

### For Administrators

1. **Generate Strong Keys**: Use cryptographically secure random generators
2. **Rotate Secrets**: Changes SECRET_KEY quarterly
3. **Monitor Logs**: Review audit logs for suspicious activity
4. **Update Dependencies**: Run `pip install --upgrade -r requirements.txt` regularly
5. **Backup Database**: Regular encrypted backups of the database
6. **HTTPS in Production**: Always use valid SSL/TLS certificates
7. **Firewall**: Restrict access to admin endpoints by IP

### For Developers

1. **Never Commit Secrets**: .env is in .gitignore
2. **Input Validation**: Always validate user input
3. **SQL Injection Prevention**: Use SQLAlchemy ORM (never raw SQL)
4. **CSRF Protection**: Always include CSRF tokens in forms
5. **CORS Security**: Configure CORS carefully in production
6. **Dependency Scanning**: Check for vulnerable packages
7. **Code Review**: Security reviews before production deployment

### For Users

1. **Strong Passwords**: Use 8+ character passwords with mixed case and numbers
2. **Never Share Admin Keys**: Keep bootstrap admin key secret
3. **Report Vulnerabilities**: Contact security team for any issues
4. **Browser Updates**: Keep your web browser updated
5. **Session Management**: Logout after each session

---

## Security Checklist

Before deployment, verify:

- [ ] `SECRET_KEY` is strong and random
- [ ] `ADMIN_KEY` is set and secure
- [ ] `FLASK_ENV=production` is set
- [ ] SSL certificates are valid and installed
- [ ] Database backups are configured
- [ ] Rate limiting is active
- [ ] Audit logging is enabled
- [ ] Dependencies are up-to-date
- [ ] No secrets in .gitignore violations
- [ ] Firewall rules configured
- [ ] HTTPS redirect working
- [ ] Security headers verified with online tool (securityheaders.com)

---

## Incident Response

### Suspected Breach

1. **Immediate Actions**:
   - Revoke all active sessions
   - Regenerate `SECRET_KEY` and `ADMIN_KEY`
   - Review audit logs
   - Notify affected users

2. **Investigation**:
   - Check database for unauthorized changes
   - Review access logs
   - Scan for malicious uploads
   - Check for SQL injection attempts

3. **Recovery**:
   - Restore from clean backup if needed
   - Update passwords policy
   - Re-verify all admin accounts
   - Document incident

---

## Security Testing

### Manual Testing

```bash
# Test HSTS headers
curl -i https://stylebridge.example.com | grep -i strict

# Test CSP headers
curl -i https://stylebridge.example.com | grep -i content-security

# Test CORS headers
curl -i -X OPTIONS https://stylebridge.example.com | grep -i access-control
```

### Automated Tools

- **Security Headers**: https://securityheaders.com
- **SSL Labs**: https://www.ssllabs.com/ssltest
- **OWASP ZAP**: https://www.zaproxy.org/
- **Burp Suite Community**: https://portswigger.net/burp

---

## Known Limitations

1. **File Upload Scanning**: Implement antivirus scanning for production
2. **Rate Limiting**: IP-based; proxy scenarios may need custom key functions
3. **2FA**: Not currently implemented; consider for production
4. **WAF**: Web Application Firewall recommended for production
5. **DDoS Protection**: Consider CDN/DDoS protection service

---

## Additional Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Flask Security](https://flask-security.readthedocs.io/)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
- [CWE Top 25](https://cwe.mitre.org/top25/)

---

## Support

For security concerns or vulnerability reports, contact the security team immediately.

**Last Updated**: March 2026  
**Version**: 1.0  
**Status**: Production Ready ✓
