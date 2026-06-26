# GuardianX Product Requirements Document (PRD)

## Project Name

GuardianX

## Tagline

Predict. Prevent. Protect. Recover.

---

# Vision

"GuardianX is an AI-powered autonomous endpoint defense platform that not only detects threats but predicts, explains, prevents, and recovers from cyber attacks while remaining lightweight enough for everyday computers."

---

# Problem Statement

Traditional antivirus solutions mainly rely on signatures and often detect attacks only after malicious activity has begun. Many solutions consume significant system resources or require constant cloud connectivity.

GuardianX aims to provide intelligent behavior-based protection while remaining lightweight enough to run on consumer hardware.

---

# Objectives

* Detect suspicious behavior before damage occurs.
* Automatically prevent malicious actions.
* Protect important user data through secure backups.
* Recover files after ransomware or destructive attacks.
* Provide AI-generated explanations for security decisions.
* Maintain low CPU and memory usage.
* Continue operating even without internet connectivity.

---

# Target Users

* Individual Windows users
* Students
* Small businesses
* Educational institutions

---

# Functional Requirements

## Authentication

* Secure login
* Role-based access
* Session management

## Dashboard

* Live endpoint status
* Threat statistics
* Resource usage
* Recent alerts

## Endpoint Agent

* Process monitoring
* File monitoring
* Registry monitoring
* USB monitoring
* Network monitoring

## AI Detection Engine

* Behavioral analysis
* Threat scoring (0–100)
* Anomaly detection
* Explainable AI

## Prevention Engine

* Kill malicious process
* Quarantine files
* Block suspicious IPs
* Isolate endpoint (future)

## Recovery Engine

* Automatic backup
* Version history
* Restore deleted files
* Restore encrypted files

## Reporting

* Incident reports
* Threat timeline
* AI explanations
* Export PDF

---

# Non-Functional Requirements

* Lightweight (<100 MB RAM target for the agent)
* CPU usage below 1% during idle monitoring
* Secure encrypted communication
* Modular architecture
* High maintainability
* Extensible plugin system

---

# Technology Stack

Frontend:

* React
* Tailwind CSS
* Vite
* shadcn/ui

Backend:

* FastAPI
* Python

AI:

* scikit-learn
* Isolation Forest
* Rule-based Engine

Database:

* PostgreSQL
* SQLite (Agent)

Storage:

* Encrypted Recovery Vault

---

# Version 1 Scope

Included:

* Dashboard
* Endpoint Agent
* AI Threat Detection
* Automatic Prevention
* Recovery Vault
* Reporting

Excluded:

* Linux support
* Mobile application
* Kernel-level drivers
* Enterprise cloud deployment

---

# Success Criteria

* Detect suspicious behaviors.
* Prevent simulated attacks.
* Recover backed-up files.
* Display real-time dashboard updates.
* Maintain low resource usage.
* Demonstrate a complete attack lifecycle from detection to recovery.

---

# Future Roadmap

Version 2:

* Linux support
* Threat intelligence feeds
* Cloud synchronization
* Email alerts
* AI model updates
* Mobile dashboard
* Enterprise endpoint management

---

GuardianX Version 1.0

AI-Powered Endpoint Detection, Prevention & Recovery Platform.
