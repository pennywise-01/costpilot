# CostPilot Enterprise Feature Backlog

> Tracking file for advanced enterprise features. All features have stub endpoints
> in `backend/app/enterprise/router.py` returning 501 Not Implemented.

## Status Legend

| Symbol | Meaning        |
|--------|----------------|
| -      | Not started    |
| ~      | In progress    |
| x      | Complete       |
| !      | Blocked        |

---

## E01 — Chargeback / Showback

- **Endpoint:** `GET /enterprise/chargeback`
- **Status:** - Not started
- **Priority:** P1
- **Description:** Allocate and report cloud costs back to business units, teams, or projects with full showback and chargeback workflows.
- **Scope:**
  - [ ] Cost allocation rules engine (percentage, proportional, fixed)
  - [ ] Showback dashboards per business unit / team
  - [ ] Chargeback invoice generation (PDF/CSV)
  - [ ] Integration with pool hierarchy for org mapping
  - [ ] Scheduled email delivery of chargeback reports

---

## E02 — Allocation Engine

- **Endpoint:** `GET /enterprise/allocation`
- **Status:** - Not started
- **Priority:** P1
- **Description:** Distribute shared and untagged cloud costs across organizational entities using configurable allocation rules.
- **Scope:**
  - [ ] Shared cost splitting rules (even, weighted, proportional to usage)
  - [ ] Untagged cost allocation via heuristic or manual mapping
  - [ ] Tag propagation and inheritance policies
  - [ ] Allocation audit trail
  - [ ] Re-allocation simulation (what-if analysis)

---

## E03 — Audit Logging & Regulatory Reporting

- **Endpoints:** `GET /enterprise/audit-logs`, `GET /enterprise/regulatory-reports`
- **Status:** - Not started
- **Priority:** P2
- **Description:** Tamper-proof audit trail for every configuration change, user action, and system event. Compliance reports for SOC 2, ISO 27001, and similar frameworks.
- **Scope:**
  - [ ] Immutable audit log storage (append-only)
  - [ ] Filterable audit log UI (user, action, entity, date range)
  - [ ] Pre-built regulatory report templates (SOC 2, ISO 27001)
  - [ ] Scheduled compliance report generation
  - [ ] Log export to SIEM (Splunk, ELK, Datadog)

---

## E04 — Approval Workflow

- **Endpoint:** `GET /enterprise/approvals`
- **Status:** - Not started
- **Priority:** P2
- **Description:** Route cost-impacting changes through configurable multi-level approval chains with escalation policies and SLA tracking.
- **Scope:**
  - [ ] Approval chain builder (sequential, parallel, conditional)
  - [ ] Threshold-based auto-approval rules
  - [ ] Escalation policies with SLA deadlines
  - [ ] Slack / email notifications for pending approvals
  - [ ] Approval history and audit integration (E03)

---

## E05 — Spend Forecasting

- **Endpoint:** `GET /enterprise/forecasting`
- **Status:** - Not started
- **Priority:** P1
- **Description:** Project future cloud spend using historical trends, seasonality detection, and ML-based forecasting models.
- **Scope:**
  - [ ] Time-series forecasting (linear, ARIMA, Prophet)
  - [ ] Seasonality and trend decomposition
  - [ ] Budget vs. forecast comparison view
  - [ ] Forecast alerts (projected overspend warnings)
  - [ ] Per-service and per-account forecast drill-down

---

## E06 — Commitment Tracker

- **Endpoint:** `GET /enterprise/commitments`
- **Status:** - Not started
- **Priority:** P1
- **Description:** Monitor Reserved Instance and Savings Plan utilization, coverage gaps, and upcoming expirations across all cloud providers.
- **Scope:**
  - [ ] RI/SP inventory dashboard (AWS, Azure, GCP)
  - [ ] Utilization and coverage metrics with heatmap
  - [ ] Expiration timeline with renewal recommendations
  - [ ] Purchase recommendation engine (break-even analysis)
  - [ ] Commitment vs. on-demand cost comparison

---

## E08 — FX / Tax Conversion

- **Endpoint:** `GET /enterprise/fx-tax`
- **Status:** - Not started
- **Priority:** P2
- **Description:** Convert cloud costs between currencies and apply region-specific tax rules for accurate financial reporting.
- **Scope:**
  - [ ] Multi-currency support with daily exchange rates
  - [ ] Organization-level base currency setting
  - [ ] Tax rule engine (VAT, GST, sales tax by region)
  - [ ] Historical FX rate lookups for retroactive reporting
  - [ ] Currency conversion in all export formats

---

## E09 — Anomaly Detection

- **Endpoint:** `GET /enterprise/anomalies`
- **Status:** - Not started
- **Priority:** P1
- **Description:** Detect unexpected cost spikes and usage anomalies in near-real-time using statistical and ML-based detection algorithms.
- **Scope:**
  - [ ] Statistical anomaly detection (z-score, IQR, moving average)
  - [ ] ML-based detection (isolation forest, autoencoders)
  - [ ] Per-service and per-account anomaly monitoring
  - [ ] Alert channels (email, Slack, PagerDuty, webhook)
  - [ ] Anomaly investigation view with root-cause hints

---

## E10 — FinOps Maturity Assessment

- **Endpoint:** `GET /enterprise/maturity`
- **Status:** - Not started
- **Priority:** P3
- **Description:** Assess and track your organization's FinOps maturity level with actionable recommendations aligned to the FinOps Foundation framework.
- **Scope:**
  - [ ] Maturity scorecard (Crawl / Walk / Run per capability)
  - [ ] Self-assessment questionnaire mapped to FinOps Foundation domains
  - [ ] Progress tracking over time with trend charts
  - [ ] Actionable next-step recommendations per domain
  - [ ] Benchmarking against anonymized industry averages

---

## E11 — Collaboration

- **Endpoint:** `GET /enterprise/notes`
- **Status:** - Not started
- **Priority:** P3
- **Description:** Attach contextual notes, comments, and discussion threads to any cost entity for cross-team collaboration and knowledge sharing.
- **Scope:**
  - [ ] Notes and comments on resources, pools, recommendations
  - [ ] @mention support with notification delivery
  - [ ] Threaded discussions with resolution tracking
  - [ ] Attachment support (screenshots, documents)
  - [ ] Activity feed across all entities

---

## E12 — Enterprise Connectors

- **Endpoint:** `GET /enterprise/connectors`
- **Status:** - Not started
- **Priority:** P2
- **Description:** Integrate with enterprise systems such as ServiceNow, Jira, Slack, and custom webhooks for end-to-end cost management workflows.
- **Scope:**
  - [ ] ServiceNow integration (tickets, CMDB sync)
  - [ ] Jira integration (issue creation from recommendations)
  - [ ] Slack integration (alerts, interactive approvals)
  - [ ] Custom webhook connector builder
  - [ ] Connector health monitoring and retry policies

---

## E13 — Data Export

- **Endpoint:** `GET /enterprise/export`
- **Status:** - Not started
- **Priority:** P2
- **Description:** Export cost data, reports, and dashboards in CSV, JSON, Parquet, and PDF formats with scheduled delivery.
- **Scope:**
  - [ ] On-demand export (CSV, JSON, Parquet, PDF)
  - [ ] Scheduled export jobs with cron configuration
  - [ ] Delivery to S3, GCS, Azure Blob, or email
  - [ ] Customizable report templates
  - [ ] Export history and re-download

---

## E14 — Platform Health

- **Endpoint:** `GET /enterprise/health`
- **Status:** - Not started
- **Priority:** P3
- **Description:** Monitor the health, uptime, and performance metrics of all CostPilot platform components and connected cloud integrations.
- **Scope:**
  - [ ] System health dashboard (API, workers, database, cache)
  - [ ] Cloud integration connectivity status
  - [ ] Data ingestion pipeline latency and freshness
  - [ ] Uptime SLA tracking with incident history
  - [ ] Alerting on degraded components

---

## E15 — Advanced RBAC

- **Endpoint:** `GET /enterprise/{org_id}/rbac`
- **Status:** x Complete
- **Priority:** P2
- **Description:** Fine-grained role-based access control with custom roles, attribute-based policies, and organization-wide permission inheritance.
- **Scope:**
  - [x] Custom role builder (permissions matrix)
  - [x] Attribute-based access control (ABAC) policies
  - [x] Permission inheritance through org hierarchy
  - [x] Access review and certification workflows
  - [x] SSO/SAML/OIDC integration for enterprise identity providers

---

## E16 — Invitation Email Flow

- **Status:** - Not started
- **Priority:** P1
- **Description:** Send invitation emails when a user is invited to an organization, supporting both existing users and new users who have not yet registered.
- **Scope:**
  - [ ] Wire frontend invite modal to call backend `POST /organizations/{org_id}/employees/invite` API
  - [ ] Send invitation email via the notification system when an employee is invited
  - [ ] Support inviting unregistered users with a registration link containing an invitation token
  - [ ] Build accept-invitation frontend page and backend endpoint for token validation
  - [ ] Add authorization checks so only org admins/managers can invite users
  - [ ] Pass role field from frontend to backend and persist on the Employee record
  - [ ] Replace hardcoded mock data in the Users page with real employee data from the API
