# StyleBridge - Secure 3D Fashion Virtual Try-On

## Project Overview

StyleBridge is a **production-ready, secure 3D web application** for virtual clothing try-ons. It combines modern web technologies with cutting-edge security practices.

### Key Features

✅ **3D Visualization** - Interactive Three.js scenes with realistic lighting and shadows  
✅ **Virtual Try-On** - Upload selfies and visualize clothing items  
✅ **Inventory Management** - Admin dashboard for product management  
✅ **User Accounts** - Secure registration and authentication  
✅ **Role-Based Access** - Granular permission system  
✅ **Audit Logging** - Complete action tracking  

---

## Security Highlights

🔒 **Enterprise-Grade Security**

- **HTTPS/TLS** - Encrypted all communications
- **OWASP Compliant** - Follows OWASP Top 10 protections
- **Rate Limiting** - Prevents brute force attacks
- **Input Validation** - XSS and injection prevention
- **CSRF Protection** - Secure forms with tokens
- **Security Headers** - HSTS, CSP, X-Frame-Options, etc.
- **Secure Cookies** - HTTPOnly, Secure, SameSite flags
- **Password Hashing** - PBKDF2 + SHA-256 encryption
- **Audit Trail** - IP logging and action tracking

**For detailed security information, see [SECURITY_GUIDE.md](SECURITY_GUIDE.md)**

---

## 3D Features

### Interactive 3D Scene

The home page features an interactive 3D preview built with **Three.js**:

```
┌─────────────────────────────────────┐
│         3D Preview Canvas           │
│                                     │
│      Rotating Cube & Torus          │
│    with Realistic Lighting          │
│                                     │
└─────────────────────────────────────┘
```

**Features:**
- ✨ **Realistic Lighting**: Ambient + directional lights with shadows
- 🎨 **PBR Materials**: Metallic and rough surface effects
- 🔄 **Animations**: Smooth rotations and scale transformations
- 📱 **Responsive**: Adapts to any canvas size
- ⚡ **Performance**: GPU-optimized rendering
- 🛡️ **Error Handling**: Graceful fallback for unsupported browsers

### Technical Implementation

**File**: `app/static/js/three_scene.js`

```javascript
// Full ES6 class-based architecture
class StyleBridgeScene {
  - Scene initialization with error handling
  - Advanced lighting setup (ambient + directional + point)
  - Mesh creation with shadows
  - Animation loop with requestAnimationFrame
  - Window resize responsive handling
  - Security measures (context menu prevention)
}
```

**Features:**
- Class-based OOP design
- Comprehensive error handling with fallback UI
- Performance optimization (antialiasing, shadow maps)
- Memory-safe animation loop
- Mobile-friendly rendering

---

## Architecture

```
stylebridge_final/
├── app/
│   ├── __init__.py              # Flask app factory with security
│   ├── config.py                # Configuration (secure defaults)
│   ├── models.py                # Database models (User, Item, etc.)
│   ├── security.py              # RBAC and audit logging
│   ├── routes/
│   │   ├── auth.py              # Login/Register (rate-limited)
│   │   └── main.py              # Upload/Admin (validated)
│   ├── static/
│   │   ├── js/
│   │   │   ├── three_scene.js   # 3D visualization (secure)
│   │   │   └── three.module.js  # Three.js library
│   │   └── uploads/             # User-uploaded files
│   └── templates/
│       ├── base.html            # Base template with CSP
│       ├── home.html            # Home with 3D canvas
│       ├── upload.html          # Selfie upload
│       └── admin/               # Admin dashboard
├── run.py                       # Secure server startup
├── requirements.txt             # Dependencies with security packages
├── .env.example                 # Configuration template
└── SECURITY_GUIDE.md            # Security documentation
```

---

## Quick Start

### 1. Clone & Setup

```bash
cd stylebridge_final
python -m venv venv
source venv/Scripts/activate  # Windows: venv\Scripts\activate
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env and set:
# - SECRET_KEY (generate with: python -c "import secrets; print(secrets.token_hex(32))")
# - ADMIN_KEY (generate with: python -c "import secrets; print(secrets.token_urlsafe(32))")
# - ADMIN_EMAIL / ADMIN_PASSWORD (optional bootstrap admin account)
```

### 3. Install & Initialize

```bash
pip install -r requirements.txt
python -c "from app import create_app, db; app=create_app(); app.app_context().push(); db.create_all(); print('✓ DB initialized')"
```

### 4. Run Application

```bash
# Development
export FLASK_ENV=development  # Windows: set FLASK_ENV=development
python run.py

# Visit: http://localhost:5000
```

### 5. Create Admin Account

Option A: Bootstrap one automatically with `.env`

```bash
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=use-a-strong-password
```

Start the app and that account will be created or updated as a `superadmin`.

Option B: Promote an existing account manually

1. Register at http://localhost:5000/auth/register
2. Go to http://localhost:5000/admin/grant
3. Enter your ADMIN_KEY
4. Access admin dashboard at http://localhost:5000/admin/inventory/upload

---

## Technologies Used

### Backend
- **Flask** - Lightweight Python web framework
- **SQLAlchemy** - ORM for database operations
- **Flask-Login** - User session management
- **Flask-WTF** - CSRF protection
- **Flask-Talisman** - Security headers
- **Flask-Limiter** - Rate limiting
- **Werkzeug** - Secure filename handling

### Frontend  
- **Three.js** - 3D graphics library
- **Tailwind CSS** - Utility-first styling
- **HTML5** - Semantic markup
- **ES6+ Modules** - Modern JavaScript

### Database
- **SQLite** (development, default)
- **PostgreSQL** (production recommended)
- **MySQL** (supported)

---

## API Endpoints

### Public
- `GET /` - Home page with 3D preview
- `GET /auth/login` - Login page
- `POST /auth/login` - Login (rate-limited: 10/hour)
- `GET /auth/register` - Register page
- `POST /auth/register` - Register (rate-limited: 5/hour)
- `POST /auth/logout` - Logout

### Authenticated
- `GET /upload` - Upload form
- `POST /upload` - Submit selfie (rate-limited: 10/hour)

### Admin
- `GET /admin/grant` - Grant admin role
- `POST /admin/grant` - Submit admin key
- `GET /admin/inventory/upload` - Inventory page
- `POST /admin/inventory/upload` - Upload items (rate-limited: 5/hour)
- `GET /admin/users` - User management
- `POST /admin/users/<id>/roles` - Assign roles

### Health
- `GET /health` - Health check

---

## Database Models

### User
```python
id: Integer (PK)
email: String (unique)
password_hash: String
is_admin: Boolean
roles: Relationship[Role]
created_at: DateTime
```

### Role
```python
id: Integer (PK)
name: String (unique, indexed)
created_at: DateTime
```

### Item
```python
id: Integer (PK)
external_id: String (unique, indexed)
title: String (sanitized)
price: Float (validated)
image_url: String (validated)
created_at: DateTime
```

### AuditLog
```python
id: Integer (PK)
actor_user_id: Integer (FK)
action: String (indexed)
target: String
meta_json: Text
ip: String
user_agent: String
created_at: DateTime (indexed)
```

---

## Performance Optimization

### Backend
- Connection pooling (SQLAlchemy)
- Query optimization (indexed fields)
- Caching (potentially with Redis)
- Async task support (Celery optional)

### Frontend (3D)
- GPU-accelerated rendering
- Texture optimization
- LOD (Level of Detail) support
- Memory-efficient animation loop

### Deployment
- Gunicorn WSGI server
- Nginx reverse proxy
- Redis session storage (optional)
- CDN for static assets

---

## Deployment

### Development
```bash
python run.py  # Ready for local development
```

### Production
```bash
export FLASK_ENV=production
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
gunicorn -w 4 -b 0.0.0.0:5000 wsgi:app  # See wsgi.py
```

**Recommendations:**
- Use Nginx as reverse proxy
- Enable HTTPS with Let's Encrypt
- Set up automatic backups
- Monitor with Datadog/New Relic
- Use CDN for static files
- Enable WAF (AWS WAF, Cloudflare)

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Code Standards
- Follow PEP 8 for Python
- Use type hints where possible
- Write docstrings for all functions
- Add unit tests for new features
- Security review before merge

---

## Security Policy

For vulnerability reports, please email: **security@stylebridge.com**

**Do not** open public issues for security vulnerabilities.

See [SECURITY_GUIDE.md](SECURITY_GUIDE.md) for complete security documentation.

---

## License

This project is proprietary. All rights reserved.

---

## Support

- 📧 Email: support@stylebridge.com
- 🐛 Issues: GitHub Issues (public repo only)
- 📚 Docs: See SECURITY_GUIDE.md and inline comments

---

## Changelog

### Version 1.0 (Current)
- ✅ 3D visualization with Three.js
- ✅ Secure authentication & authorization
- ✅ File upload with validation
- ✅ Inventory management
- ✅ Audit logging
- ✅ Security headers (Talisman)
- ✅ Rate limiting
- ✅ CSRF protection
- ✅ Input sanitization
- ✅ Error handling

### Future Enhancements
- 🔮 2FA (Two-Factor Authentication)
- 🔮 Real-time try-on preview
- 🔮 Mobile app
- 🔮 Advanced AR filters
- 🔮 Social sharing
- 🔮 AI-powered recommendations

---

**StyleBridge - Making fashion fitting safe and interactive.**

Last Updated: March 2026  
Status: Production Ready ✓
