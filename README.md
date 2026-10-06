# Secure Exchange Connectivity - LAB
Self learning of an exchange connectivity lab, exploring API security, security monitoring, disaster recovery, and tenant-scope authorization.

## Why this project exists?

This project was built to demonstrate the implementations of security architecture in a system inspired by public exchnage-connectivity concepts 

## What this project demonstrates:

- Secure API design
- Tenant-scoped authorization
- Structured JSON logging
- Alert generation and triage
- Backup and restore workflow
- Security-focused documentation

## System Architecture

![Secure Exchange Connectivity Lab System Architecture](Board.png)

This diagram illustrates the major trust zones and service interactions in the lab. It demonstrates how client traffic is automated, processed, logged, monitored, and recoverable, in a segmented system. 

## Understanding the Diagram

- **External client zone** contains the user-facing entry points: a simulated member client and an administrative portal.
- **Core application zone** contains the transaction-processing services: order gateway, identity/RBAC, matching simulator, and market-data publishing.
- **Security monitoring zone** contains the logging and alerting pipeline.
- **Disaster recovery zone** contains backup export and restoration components.
- **PostgreSQL** stores execution and audit-relevant data.

### Request flow

1. A simulated member client sends a request to the **Order Gateway**.
2. The gateway checks identity and permissions through the **Identity & RBAC Service**.
3. Approved requests are passed to the **Matching Simulator**.
4. Execution-related records are written to **PostgreSQL**.
5. Displayed events are sent to the **Market-Data Publisher** and then to the **Market-Data Consumer**.
6. Security-relevant activity is forwarded to **Structured Security Logs**.
7. Logs are analyzed by the **SIEM-style Analysis** service, which can generate alerts for the **Incident Triage Queue**.
8. Database data can be exported through **Encrypted Backup Export** and restored into the **DR Restore Environment**.
