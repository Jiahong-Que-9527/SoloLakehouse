# DevOps Delivery Engineering

<!-- [房玄龄·2026-11-17] Make the DevOps project self-contained. -->

<!-- [房玄龄·2026-11-17] Initialize DevOps delivery project planning. -->

<!-- [GLM·2026-11-20] Implement D01 (service) and D02 (image and compose); record local evidence. -->

Build the delivery and operating path for one small data service. The **Energy Data Quality Service** will expose quality results for synthetic energy snapshots while each phase adds a verifiable delivery or operating capability.

**Status:** D01 and D02 implemented locally (owner acceptance runs pending). D03 is next. Remaining phases are planned and their acceptance evidence is pending.

## Service and environment

- This project owns its application, data contract, test inputs, release assets and acceptance evidence within `Devops-engineering/`. D01–D07 build on one another inside this project.
- The [reference service](reference-service/README.md) defines the response contract and the synthetic audit fixtures used throughout the roadmap.
- WSL2 Ubuntu is the development and deployment environment. GitHub-hosted Actions and GHCR are planned for CI and image distribution. Releases and incidents demonstrate local engineering behavior and measured recovery in WSL.

## Projects

1. [D01 · Reproducible development](01-reproducible-development/README.md) — bring up and test the service from a fresh checkout.
2. [D02 · Containerized application](02-containerized-application/README.md) — run the service from a container image with external inputs.
3. [D03 · Continuous integration](03-continuous-integration/README.md) — verify changes and publish a traceable image.
4. [D04 · Continuous delivery](04-continuous-delivery/README.md) — deploy an approved image and prove rollback.
5. [D05 · Kubernetes and GitOps](05-kubernetes-gitops/README.md) — reconcile the deployment from Git and exercise drift handling.
6. [D06 · Observability and reliability](06-observability-reliability/README.md) — detect and recover from controlled incidents.
7. [D07 · DevOps platform factory](07-devops-platform-factory/README.md) — use the established delivery path to onboard a second service.

Read the [delivery plan](docs/delivery-plan.md) for sequencing and open decisions, and the [evidence guide](docs/evidence-guide.md) before recording a phase result.

## Layout

The numbered projects own phase-specific designs and delivery assets. The service source, fixtures and tests live in one place under `reference-service/`. At D03, a dedicated GitHub Actions workflow under `.github/workflows/` will run this project's own checks, build its image and publish its artifacts. Empty `.gitkeep` files mark directories reserved for implementation.
