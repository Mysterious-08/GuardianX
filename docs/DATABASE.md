# GuardianX Database Design Document (DDD)

# 1. Purpose

This document defines the database schema for GuardianX. The database stores users, endpoints, alerts, threat graphs, recovery metadata, reports, audit logs, and system policies. Actual backup files are stored in the encrypted Recovery Vault; only metadata is stored in the database.

---

# 2. Database Technologies

## Central Database

* PostgreSQL

Stores:

* Users
* Endpoints
* Alerts
* Threat Graphs
* Reports
* Recovery metadata
* Policies
* Audit logs

## Local Agent Database

* SQLite

Stores:

* Cached events
* Offline alerts
* Event queue
* Synchronization status

---

# 3. Tables

## Users

Purpose:
Stores administrator and analyst accounts.

Fields:

* user_id (Primary Key)
* username
* email
* password_hash
* role
* created_at
* last_login

---

## Endpoints

Purpose:
Stores registered computers.

Fields:

* endpoint_id
* hostname
* operating_system
* agent_version
* status
* last_seen
* registered_at

---

## Threat Events

Purpose:
Stores individual security events received from agents.

Fields:

* event_id
* endpoint_id
* event_type
* source
* severity
* timestamp
* raw_data

---

## Threat Graphs

Purpose:
Groups related events into a single attack chain.

Fields:

* graph_id
* endpoint_id
* threat_score
* confidence
* classification
* start_time
* end_time
* status

---

## Threat Graph Nodes

Purpose:
Stores events belonging to a Threat Graph.

Fields:

* node_id
* graph_id
* event_id
* sequence_number

---

## Alerts

Purpose:
Stores generated security alerts.

Fields:

* alert_id
* graph_id
* endpoint_id
* alert_level
* title
* description
* action_taken
* created_at

---

## Recovery Metadata

Purpose:
Tracks backed-up files.

Fields:

* backup_id
* endpoint_id
* original_path
* encrypted_path
* file_hash
* backup_time
* version

---

## Reports

Purpose:
Stores generated incident reports.

Fields:

* report_id
* graph_id
* report_type
* generated_at
* file_location

---

## Policies

Purpose:
Stores configurable security rules.

Fields:

* policy_id
* policy_name
* description
* enabled
* configuration

---

## Audit Logs

Purpose:
Stores administrative actions.

Fields:

* audit_id
* user_id
* action
* timestamp
* details

---

# 4. Relationships

Users
↓
Audit Logs

Endpoints
↓
Threat Events
↓
Threat Graphs
↓
Alerts

Endpoints
↓
Recovery Metadata

Threat Graphs
↓
Reports

Policies
↓
Threat Assessment Engine

---

# 5. Storage Strategy

The PostgreSQL database stores metadata only.

Large files such as backups are stored in the encrypted Recovery Vault.

SQLite stores temporary local data when offline and synchronizes it with PostgreSQL once connectivity is restored.

---

# 6. Design Principles

* Normalize data where practical.
* Avoid storing duplicate information.
* Store metadata in the database and large binary files on disk.
* Use indexed timestamps for efficient querying.
* Encrypt sensitive information.
* Design tables to support future scalability.

---

GuardianX Version 1.0 Database Design
