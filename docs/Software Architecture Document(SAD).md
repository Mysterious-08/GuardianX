# GuardianX Software Architecture Document (SAD)

## 1. Purpose

This document defines the software architecture of GuardianX, a lightweight AI-powered Endpoint Detection and Response (EDR) platform for Windows. It explains the system structure, component responsibilities, data flow, communication, scalability, and design principles.

## 2. Architecture Principles

* Lightweight endpoint agent.
* Offline-first operation.
* Modular plugin-based design.
* Event-driven processing.
* AI-assisted behavioral detection.
* Automatic prevention and recovery.
* Optional cloud intelligence.
* Secure-by-design communication.

## 3. High-Level Components

### Endpoint Agent

* Collects Windows events.
* Performs lightweight monitoring.
* Executes local response actions.
* Maintains an offline event queue.

### Event Processor

* Receives normalized events.
* Filters duplicate events.
* Sends events to the Threat Graph Builder.

### Threat Graph Builder

* Correlates related events into attack chains.
* Groups process, file, registry, and network activities.
* Produces a complete attack timeline.

### Local AI Engine

* Performs behavior analysis.
* Detects anomalies.
* Assigns a threat score.
* Generates explainable security decisions.

### Risk Assessment Engine

* Calculates overall attack severity.
* Applies configurable security policies.
* Determines the required response level.

### Autonomous Response Engine

* Terminates malicious processes.
* Quarantines suspicious files.
* Initiates protected file backup.
* Blocks configured malicious activity where supported.

### Recovery Vault

* Stores encrypted backup copies.
* Maintains file version history.
* Restores files after attacks.

### Backend Server

* Provides REST APIs.
* Manages authentication, endpoints, alerts, reports, and policies.
* Synchronizes with endpoint agents.

### Dashboard

* Displays endpoint health.
* Visualizes Threat Graphs and timelines.
* Shows alerts, recovery history, and analytics.

## 4. Data Flow

Windows Event → Event Processor → Threat Graph Builder → Local AI Engine → Risk Assessment → Response Engine → Recovery Vault → Backend API → Dashboard

## 5. Performance Goals

* Agent RAM: 40–80 MB
* Agent CPU (Idle): <1%
* Event-driven architecture to minimize polling.
* AI activated only for suspicious activity.

## 6. Security

* Encrypted communication between agent and backend.
* Encrypted Recovery Vault.
* Secure authentication and authorization.
* Audit logging for security actions.

## 7. Extensibility

GuardianX supports plugin-based monitoring modules and optional cloud intelligence without affecting offline protection.

## 8. Version 1 Scope

Windows support, local AI, web dashboard, recovery vault, reporting, and modular architecture.
