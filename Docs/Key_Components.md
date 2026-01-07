
---

## Key Components

### 1. Lakehouse Storage

- Bronze / Silver / Gold tables
- Delta Lake format
- ACID transactions & time travel
- Batch-oriented design

**Purpose:**  
Single source of truth for raw data, cleaned data, and analytical datasets.

---

### 2. Feature Engineering

- Spark SQL / PySpark pipelines
- Deterministic, repeatable transformations
- Feature timestamps (`feature_ts`) explicitly stored

**Purpose:**  
Turn raw data into reusable, explainable features.

---

### 3. Offline Feature Store (Delta-based)

- Feature tables stored as Delta tables
- Versioned via data & code
- No online serving layer (no Feast, no Redis)

**Why offline only?**  
For learning, research, and batch ML systems, an offline feature store captures **90% of real-world complexity** with **10% of the cost**.

---

### 4. Point-in-Time Correct Training

- Explicit joins between labels and features
- Prevents data leakage
- Aligns with production ML best practices

**This is a first-class concept in SoloLakehouse.**

---

### 5. Training & Experiments

- PySpark / Pandas
- XGBoost / PyTorch / Scikit-learn
- GPU training via Google Colab Pro+
- Deterministic experiment configs

**Goal:**  
Reproducible experiments that can be traced back to exact data and feature versions.

---

### 6. MLflow (Self-hosted)

- Experiment tracking
- Metrics & artifacts
- Model registry
- Stage transitions (Staging / Production)

MLflow acts as the **control plane** of the ML lifecycle.

---

## What This Project Is (and Is Not)

### ✅ This project **is**

- A **learning-oriented Lakehouse platform**
- A **portfolio-grade MLOps system**
- A **Databricks-aligned mental model**
- A foundation for research, demos, and teaching

### ❌ This project is **not**

- A production SaaS
- A fully managed enterprise platform
- A plug-and-play AutoML solution

---

## Who Is This For?

- ML / AI Engineers preparing for **enterprise ML roles**
- Engineers studying **Databricks ML / AI certifications**
- Researchers who want **reproducible ML systems**
- Solo developers who want **system-level ML experience**
- Anyone tired of “just training another model”

---

## Learning Goals

By building and using SoloLakehouse, you will understand:

- How a Lakehouse differs from a traditional data warehouse
- Why feature stores exist and how to design one
- How point-in-time joins prevent data leakage
- How experiments, data, and models connect
- How enterprise ML systems are structured conceptually

---

## Roadmap (High-Level)

- [ ] End-to-end reference pipeline (data → model → registry)
- [ ] Feature versioning strategies
- [ ] Batch inference pipeline
- [ ] Model evaluation & drift analysis
- [ ] Lightweight model serving
- [ ] Documentation & diagrams (Excalidraw-style)

---

## Status

🚧 **Actively evolving**

This repository reflects an ongoing learning and engineering journey.  
Expect iteration, refactoring, and continuous improvement.

---

## License

MIT License — use, adapt, and learn from it freely.

---

## Final Note

> *“Enterprise ML is not about training better models.  
> It’s about building systems you can trust.”*

SoloLakehouse is my attempt to internalize that lesson — one component at a time.
