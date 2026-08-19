# GuardianX Development Tasks

## Current Version

**v0.0.9**

---

# Sprint 1 - Project Foundation

## Completed ✅

### Project Foundation

* [x] Create GitHub repository
* [x] Create project documentation (PRD, SAD, DDD, API, ROADMAP)
* [x] Configure Git workflow (`main` and `develop`)
* [x] Initialize React (Vite + TypeScript)
* [x] Configure ESLint
* [x] Initialize FastAPI backend
* [x] Verify Swagger documentation
* [x] Create root `.gitignore`
* [x] Create `AGENTS.md`

### Database & Backend Foundation

* [x] Configure PostgreSQL
* [x] Configure SQLAlchemy 2.0
* [x] Configure Alembic
* [x] Configure environment variables (`.env`)
* [x] Configure database session management
* [x] Implement startup database connectivity check
* [x] Create User database model
* [x] Create initial Alembic migration

### Security & Authentication

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

### Device Management Foundation

* [x] Design device registration architecture
* [x] Create Device database model
* [x] Create Device schemas
* [x] Create Device service
* [x] Implement Device Registration API
* [x] Verify Device Registration using Swagger
* [x] Create Heartbeat schemas
* [x] Implement Heartbeat service
* [x] Implement Heartbeat API
* [x] Implement centralized exception handling
* [x] Verify complete Heartbeat flow using Swagger
* [x] Verify authorization (403) and not-found (404) scenarios

### Device Inventory

* [x] Create Device Inventory database model
* [x] Create Device Inventory schemas
* [x] Create Device Inventory service
* [x] Implement Device Inventory API
* [x] Implement inventory create/update behavior
* [x] Implement inventory ownership validation
* [x] Verify Device Inventory using API/Swagger
* [x] Create Device Inventory service tests
* [x] Verify Device Inventory tests

### Security Events

* [x] Create Security Event database model
* [x] Create Security Event database migration
* [x] Create Security Event schemas
* [x] Create Security Event service
* [x] Implement Security Event ingestion API
* [x] Implement Security Event retrieval API
* [x] Implement Security Event ownership validation
* [x] Implement Security Event not-found handling
* [x] Verify Security Event schemas
* [x] Verify Security Event service
* [x] Verify Security Event API routes
* [x] Verify Security Event ingestion and retrieval using API
* [x] Create Security Event tests
* [x] Verify complete backend test suite

---

## In Progress 🔄

### Device Management

* [x] Device inventory collection
* [x] Automatic online/offline status monitoring
* [ ] Device dashboard APIs

---

## Pending ⏳

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
* Add automated tests for every major backend feature.
* Verify important API flows using Swagger or an equivalent API client.
* Update this `task.md` after every completed milestone.

---

# Completed Milestones

* ✅ **v0.0.1** - Project initialization
* ✅ **v0.0.2** - Repository setup and project documentation
* ✅ **v0.0.3** - Database foundation, migrations, security package, and password hashing
* ✅ **v0.0.4** - Authentication foundation (schemas, user service, JWT authentication, and authentication service)
* ✅ **v0.0.5** - Complete authentication module (Register API, Login API, OAuth2 Password Flow, JWT authentication, protected routes, `/auth/me`, and Swagger verification)
* ✅ **v0.0.6** - Device Management Foundation (Device registration, heartbeat endpoint, centralized exception handling, device ownership validation, Swagger verification, and end-to-end testing)
* ✅ **v0.0.7** - Endpoint Visibility & Security Event Foundation (Device inventory collection, inventory ownership validation, security event ingestion/retrieval, security event ownership validation, API testing, and end-to-end verification)
* ✅ **v0.0.8** - Device Inventory Collection (inventory model, migration, schemas, service, API endpoints, ownership validation, and automated testing)
* ✅ **v0.0.9** - Automatic Online/Offline Status Monitoring (heartbeat-based online transition, 90-second stale-device detection, query-time offline status evaluation, protected device states, device list API, API testing, and Swagger verification)

---

# Current Focus

✅ **Completed Task:**

**Device Inventory Collection**

Includes:

- Device inventory database model
- Inventory schema validation
- Inventory persistence service
- Create/update inventory behavior
- Device ownership validation
- GET inventory API
- POST inventory API
- API integration tests
- Full backend verification

✅ **Completed Task:**

**Automatic Online/Offline Status Monitoring**

Includes:

- Heartbeat-based online status transition
- `last_seen` tracking
- 90-second offline threshold
- Query-time stale-device detection
- Persisted `OFFLINE` status for stale devices
- Preservation of `REGISTERED` devices without heartbeat
- Preservation of `ISOLATED`, `QUARANTINED`, and `UNINSTALLED` states
- Authenticated `GET /devices` endpoint
- Dedicated device status tests
- Full backend test verification
- Swagger verification

🎯 **Next Task:**

**Device Dashboard APIs**

The dashboard APIs should expose device inventory, device status, heartbeat activity, and endpoint visibility data required by the GuardianX dashboard.