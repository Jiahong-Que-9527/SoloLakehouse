# M09 · ML platform factory

<!-- [魏征·2026-11-21] Initialize stage planning. -->

**Status:** planned · [Roadmap](../README.md) · [Delivery plan](../docs/delivery-plan.md)

Prove the system is a platform: extract the template from what actually runs, onboard a second model with it, and measure the onboarding.

## Deliverables

- The template: feature scaffold, train/eval CLI skeleton, CI workflow, manifest and model-card patterns — carrying delivery assets only; domain contracts stay with each workload (the [D07 rule](../../Devops-engineering/07-devops-platform-factory/README.md)).
- The second workload selected in the [delivery plan](../docs/delivery-plan.md) (station outage or low-balance classification, or a district-aggregate forecaster), onboarded through the template into its own package, workflow and release path.
- The onboarding runbook updated with the measured effort and the friction list that feeds back into the template.

## Acceptance

1. The second model delivers its own dataset contract, feature contract, baseline report, release manifest and model card through the template, without editing the first workload.
2. Onboarding effort is measured and recorded; every template gap found during onboarding becomes a recorded template change or an accepted limitation.
3. The two workloads' releases, scoring outputs and monitoring metrics coexist without collision in one project tree.

This closes the portfolio loop: a mid-to-senior ML engineer can point at a system that was framed, built, productionized, observed, orchestrated and reused.
