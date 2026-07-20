# GuardianX Development Tasks

## Current Version

**v0.0.3**

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

---

## In Progress 🔄

### Authentication Foundation

* [ ] Create authentication schemas (Pydantic)
* [ ] Create user service (CRUD)
* [ ] Implement JWT authentication
* [ ] Create Register API
* [ ] Create Login API
* [ ] Authentication dependencies
* [ ] Protected routes

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
* Commit after every completed milestone.
* Do not implement features outside the current sprint.
* Keep GuardianX lightweight and maintainable.
* Review every major code change before merging.
* Keep business logic separate from API routes.
* Use Alembic for every database schema change.

---

# Completed Milestones

* ✅ **v0.0.1** - Project initialization
* ✅ **v0.0.2** - Repository setup and project documentation
* ✅ **v0.0.3** - Database foundation, migrations, security package, and password hashing

---

# Current Focus

🎯 **Next Task:**

**Design and implement authentication schemas (Pydantic models) before building the authentication service and APIs.**
