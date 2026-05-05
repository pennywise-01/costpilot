"""Per-provider advisor ingestors.

Each ingestor calls a single bulk advisor API and emits a list of
`NormalizedAdvisorFinding`. Persistence and rule-mapping live in
`app.advisor_findings.service`, not here.
"""
