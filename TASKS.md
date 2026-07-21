# GuardianX Development Tasks

## Current Version

**v0.0.5**

---

# Sprint 1 - Project Foundation

## Completed ✅

* [x] Create GitHub repository
* [x] Create project documentation (PRD, SAD, DDD, API, ROADMAP)
* [x] Configure Git workflow (`main` and `develop`)
* [x] Initialize React (Vite + TypeScript)
* [x] Configure ESLint
* [x] Initialize FastAPI backend
* [x] Verify Swagger documentation
* [x] Create root `.gitignore`
* [x] Create `AGENTS.md`
* [x] Configure PostgreSQL
* [x] Configure SQLAlchemy 2.0
* [x] Configure Alembic
* [x] Configure environment variables (`.env`)
* [x] Configure database session management
* [x] Implement startup database connectivity check
* [x] Create User database model
* [x] Create initial Alembic migration
* [x] Configure security package
* [x] Implement Argon2 password hashing
* [x] Create authentication schemas (Pydantic)
* [x] Create user service
* [x] Implement JWT authentication
* [x] Create authentication service
* [x] Create Register API
* [x] Create Login API (OAuth2 Password Flow)
* [x] Implement authentication dependencies
* [x] Implement protected routes
* [x] Implement current user endpoint (`GET /auth/me`)
* [x] Verify complete authentication flow using Swagger

---

## In Progress 🔄

### Device Management

* [ ] Design device registration architecture
* [ ] Create Device database model
* [ ] Create Device schemas
* [ ] Create Device service
* [ ] Implement Device Registration API

---

## Pending ⏳

### Device Management

* [ ] Heartbeat service
* [ ] Device inventory collection
* [ ] Online/Offline status tracking
* [ ] Device dashboard APIs

### Dashboard

* [ ] Dashboard layout
* [ ] Sidebar
* [ ] Header
* [ ] Status cards
* [ ] API integration

### Endpoint Agent

* [ ] Windows service
* [ ] Secure device registration
* [ ] Process monitoring
* [ ] File monitoring
* [ ] Registry monitoring
* [ ] Network monitoring

### Threat Intelligence

* [ ] Event normalization
* [ ] Threat Graph engine
* [ ] Risk scoring
* [ ] AI behavior analysis

### Autonomous Response

* [ ] Process termination
* [ ] File quarantine
* [ ] Policy engine

### Recovery Vault

* [ ] Backup engine
* [ ] Restore engine
* [ ] Version history

### Reporting

* [ ] Incident reports
* [ ] Dashboard analytics
* [ ] PDF generation

---

# Development Rules

* Complete one task at a time.
* Every completed task must compile and run.
* Verify functionality before committing.
* Commit after every completed milestone.
* Do not implement features outside the current sprint.
* Keep GuardianX lightweight and maintainable.
* Review every major code change before merging.
* Keep business logic separate from API routes.
* Use dependency injection throughout the application.
* Use Alembic for every database schema change.
* Keep API routes thin and place business logic in services.

---

# Completed Milestones

* ✅ **v0.0.1** - Project initialization
* ✅ **v0.0.2** - Repository setup and project documentation
* ✅ **v0.0.3** - Database foundation, migrations, security package, and password hashing
* ✅ **v0.0.4** - Authentication foundation (schemas, user service, JWT authentication, and authentication service)
* ✅ **v0.0.5** - Complete authentication module (Register API, Login API, OAuth2 Password Flow, JWT authentication, protected routes, `/auth/me`, and Swagger verification)

---

# Current Focus

🎯 **Next Task:**

**Implement the Device Registration module, beginning with the Device model, service layer, schemas, and registration API. This will establish the foundation for heartbeats, inventory collection, and endpoint management.**
