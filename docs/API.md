# GuardianX API Specification

## Purpose

This document defines the REST APIs used for communication between the GuardianX Endpoint Agent, Backend Server, and Web Dashboard.

---

# Base URL

/api/v1

---

# Authentication

## POST /auth/login

Purpose:
Authenticate a user.

Request:

* email
* password

Response:

* JWT Token
* User Information

---

## POST /auth/logout

Purpose:
Logout user.

---

## GET /auth/profile

Purpose:
Fetch logged-in user information.

---

# Endpoint Management

## POST /endpoints/register

Registers a new GuardianX Agent.

Request:

* Hostname
* OS Version
* Agent Version
* Device ID

Response:

* Endpoint ID
* Registration Status

---

## GET /endpoints

Returns all registered endpoints.

---

## GET /endpoints/{id}

Returns endpoint details.

---

# Event APIs

## POST /events

Receives normalized security events from an endpoint.

Request:

* Endpoint ID
* Event Type
* Timestamp
* Event Data

Response:

* Success Status

---

# Threat Graph

## GET /threat-graphs

Returns all threat graphs.

---

## GET /threat-graphs/{id}

Returns one Threat Graph with timeline.

---

# Alerts

## GET /alerts

Returns all alerts.

---

## GET /alerts/{id}

Returns alert details.

---

# Recovery

## POST /recovery/backup

Creates a backup entry.

---

## POST /recovery/restore

Restores selected files.

---

## GET /recovery/history

Returns backup history.

---

# Reports

## POST /reports/generate

Generates a PDF incident report.

---

## GET /reports

Returns generated reports.

---

# Policies

## GET /policies

Returns active policies.

---

## PUT /policies/{id}

Updates a policy.

---

# Dashboard

## GET /dashboard/overview

Returns:

* Total Endpoints
* Active Alerts
* Threat Count
* Recovery Status
* System Health Score

---

# Health

## GET /health

Returns backend health status.

---

GuardianX API Version 1.0
