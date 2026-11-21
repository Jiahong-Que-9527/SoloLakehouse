# Report Freshness Service

Second workload onboarded through the D07 template (see
`../07-devops-platform-factory/template/ONBOARDING.md`). Reads one
configured snapshot document, validates it and reports its age against
`MAX_AGE_HOURS`. A stale snapshot is a valid data-quality answer served
with HTTP 200; missing, unreadable or invalid input answers with a
structured availability error.
