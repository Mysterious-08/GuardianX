# GuardianX AI Development Guide

## Project

GuardianX is a lightweight AI-powered Endpoint Detection and Response (EDR) platform for Windows.

## Core Principles

* Follow the PRD, SAD, DDD, API, and Roadmap documents.
* Never redesign the architecture unless explicitly approved.
* Build incrementally.
* Keep the endpoint agent lightweight.
* Prefer event-driven architecture.
* Avoid unnecessary dependencies.
* Prioritize maintainability over cleverness.
* Every feature must compile before moving to the next.
* Do not modify unrelated files.
* Explain major implementation decisions before coding.
* Generate production-quality code.
* Include tests where practical.

## Development Order

1. Project initialization
2. Authentication
3. Dashboard
4. Endpoint Agent
5. Threat Graph
6. AI Engine
7. Response Engine
8. Recovery Vault
9. Reports
10. Testing & Optimization

## Performance Targets

* Agent RAM: 40–80 MB
* Agent CPU (Idle): <1%
* Event-driven monitoring
* Offline-first operation

## Rule

If a requested feature conflicts with the architecture, explain the conflict before implementing it.
