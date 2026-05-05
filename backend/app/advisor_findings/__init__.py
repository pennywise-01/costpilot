"""Advisor findings module.

Ingests pre-scored recommendations from cloud-provider advisor APIs
(AWS Compute Optimizer / Trusted Advisor / Cost Optimization Hub,
Azure Advisor, GCP Recommender) and persists them as a single
normalized table that built-in recommendation rules can query.

See plans/rule-data-source-strategy.md for the full design rationale.
"""
