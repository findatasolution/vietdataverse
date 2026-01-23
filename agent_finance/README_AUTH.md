# Agent Finance Authentication System

This document describes the authentication system implemented for the Agent Finance application using Neon database and JWT tokens.

## Overview

The authentication system provides:
- User registration and login
- JWT-based authentication
- Role-based access control
- Protected API endpoints
- Frontend forms for user interaction

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   FastAPI       │    │   Neon Database │
│   (HTML/JS)     │◄──►│   Backend       │◄──►│   (PostgreSQL)  │
│                 │    │                 │    │                 │
│ • register.html │    │ • /api/register │    │ • neon_users    │
│ • login.html    │    │ • /api/login    │    │ • user data     │
│ • index.html    │    │ • /api/protected│    │                 │
└─────────────────┘    │ • /api/dashboard│    └─────────────────┘
                       └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │   JWT Tokens    │
                       │                 │
                       │ • Access tokens │
                       │ • Expiration    │
                       │ • User claims   │
                       └─────────────────┘
```

## Components

### Backend Components

1. **Database Models** (`back/neon_models.py`)
   - `NeonUser` model with fields: id, email, password_hash, phone, type, membership_level, create_date

2. **Authentication** (`back/neon_auth.py`)
   - Password hashing with bcrypt
   - JWT token creation and verification
   - Token expiration handling

3. **Database** (`back/neon_database.py`)
   - Neon database connection configuration
   - SQLAlchemy engine setup

4. **Middleware** (`back/middleware.py`)
   - Authentication middleware for protected endpoints
   - Token validation and user context injection

5. **API Routes** (`back/main.py`)
   - `/api/register` - User registration
   - `/api/login` - User login
   - `/api/protected` - Example protected endpoint
   - `/api/dashboard` - User dashboard data

### Frontend Components

1. **Registration Form** (`front/register.html`)
   - Email, password, and phone input
   - Client-side validation
   - Registration submission

2. **Login Form** (`front/login.html`)
   - Email and password input
   - Client-side validation
   - Login submission and token storage

## Setup Instructions

### 1. Environment Configuration

Create a `.env` file in the project root:

```bash
NEON_DB_URL=postgresql://username:password@ep-quiet-credit-123456.us-east-1.aws.neon.tech/neondb?sslmode=require
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

### 2. Install Dependencies

```bash
pip install fastapi uvicorn sqlalchemy psycopg2-binary python-jose bcrypt python-dotenv
```

### 3. Database Setup

Run the migration script to create the users table:

```bash
python back/migrate_neon.py
```

### 4. Start the Server

```bash
cd back
python main.py
```

The server will start on `http://localhost:8000`

### 5. Test the System

Run the test script to verify the complete flow:

```bash
python test_auth_flow.py
```

## API Endpoints

### Public Endpoints

#### POST /api/register
Register a new user.

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "password123",
  "phone": "1234567890"
}
```

**Response:**
```json
{
  "message": "User registered successfully"
}
```

#### POST /api/login
Login a user and receive JWT token.

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

**Response:**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer",
  "email": "user@example.com",
  "user_id": 1
}
```

### Protected Endpoints

All protected endpoints require a valid JWT token in the Authorization header:

```
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
```

#### GET /api/protected
Example protected endpoint that returns user information.

**Response:**
```json
{
  "message": "This is a protected endpoint",
  "user": {
    "email": "user@example.com",
    "user_id": 1,
    "type": "basic",
    "membership_level": "free"
  },
  "timestamp": "2024-01-01T12:00:00"
}
```

#### GET /api/dashboard
User dashboard with personalized data.

**Response:**
```json
{
  "user": {
    "email": "user@example.com",
    "type": "basic",
    "membership_level": "free"
  },
  "dashboard_data": {
    "total_users": 1000,
    "active_sessions": 50,
    "last_login": "2024-01-01T12:00:00"
  },
  "timestamp": "2024-01-01T12:00:00"
}
```

## Security Features

### Password Security
- Passwords are hashed using bcrypt with salt
- No plain text passwords are stored in the database

### JWT Security
- Tokens use HS256 algorithm for signing
- Tokens have configurable expiration time
- Token validation includes expiration checking

### CORS Protection
- CORS middleware configured to allow specific origins
- Credentials are enabled for cross-origin requests

### Input Validation
- Pydantic models validate all incoming data
- Email format validation
- Password length requirements

## Frontend Usage

### Registration
1. Open `front/register.html` in a browser
2. Fill in email, password, and optional phone
3. Submit the form
4. User is redirected to login page

### Login
1. Open `front/login.html` in a browser
2. Enter email and password
3. Submit the form
4. Token is stored in localStorage
5. User is redirected to dashboard

### Dashboard
The main dashboard (`front/index.html`) checks for authentication:
- If logged in, shows user-specific content
- If not logged in, shows login/register links

## Testing

### Manual Testing
1. Start the server: `python back/main.py`
2. Open browser and navigate to:
   - Registration: `http://localhost:8000/register.html`
   - Login: `http://localhost:8000/login.html`
   - Dashboard: `http://localhost:8000/`

### Automated Testing
Run the test script:
```bash
python test_auth_flow.py
```

This will test:
- User registration
- User login
- Protected endpoint access
- Dashboard access
- Health check

## Troubleshooting

### Common Issues

1. **Database Connection Error**
   - Check Neon database URL in `.env`
   - Verify database credentials
   - Ensure Neon project is running

2. **JWT Token Issues**
   - Check SECRET_KEY in `.env`
   - Verify token expiration time
   - Ensure proper Authorization header format

3. **CORS Errors**
   - Check CORS origins in `main.py`
   - Verify frontend is served from allowed origin

4. **Password Hashing Issues**
   - Ensure bcrypt is installed
   - Check password hash format in database

### Debug Mode
Enable debug logging by modifying the logging configuration in `main.py`:

```python
logging.basicConfig(level=logging.DEBUG)
```

## Production Considerations

### Security
- Use strong, unique SECRET_KEY
- Set appropriate token expiration time
- Configure CORS for production domains only
- Use HTTPS for all communications

### Performance
- Consider database connection pooling
- Implement token blacklisting for logout
- Add rate limiting for authentication endpoints

### Monitoring
- Log authentication events
- Monitor failed login attempts
- Track user registration metrics

## Future Enhancements

1. **Password Reset**
   - Email-based password reset functionality
   - Password reset tokens with expiration

2. **Email Verification**
   - Email verification during registration
   - Verified user status tracking

3. **Role-Based Access**
   - Different user roles with varying permissions
   - Role-based endpoint access control

4. **OAuth Integration**
   - Google, Facebook, or other OAuth providers
   - Social login functionality

5. **Two-Factor Authentication**
   - SMS or authenticator app integration
   - Additional security layer for sensitive operations

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with appropriate tests
4. Submit a pull request

## License

This project is licensed under the MIT License.
