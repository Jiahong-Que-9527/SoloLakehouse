<div align="center">
  <img width="500" alt="SoloLakehouse_icon2"  src="https://github.com/user-attachments/assets/de7c68f4-9c9a-4c9e-867e-bb8a20df302f" />
</div>

# SoloLakehouse

**SoloLakehouse** is a personal, Databricks-inspired Lakehouse platform designed and implemented by a single machine learning engineer.

It is **not another model training notebook**.

It is a **from-scratch reconstruction of a modern Lakehouse + MLOps system**, built with minimal cost, open tools, and maximum engineering depth — to truly understand how enterprise ML platforms work under the hood.

## Architecture Overview

SoloLakehouse follows a **Lakehouse-style ML lifecycle**:

<img width="3840" height="1590" alt="Untitled-2026-01-03-2343" src="https://github.com/user-attachments/assets/55882569-6e29-492f-9b75-a3beffa2f8f4" />




## Why SoloLakehouse?

In real-world ML roles, training a model is only the beginning.

What actually matters is whether you can:

- Design a **reproducible ML lifecycle**
- Manage **features as reusable, versioned assets**
- Track **experiments, decisions, and data lineage**
- Perform **point-in-time correct training**
- Explain and audit models over time
- Deploy models in a controlled, observable way

Enterprise platforms like :contentReference[oaicite:0]{index=0} solve these problems at scale.

**SoloLakehouse is my way of learning and rebuilding those ideas from first principles — as an individual engineer.**




## Core Design Principles

- **Solo-first**  
  Designed for one ML engineer, not a large platform team.

- **Cost-aware**  
  Uses free or low-cost services where possible (Databricks Free, self-hosted components, Colab).

- **System-level thinking**  
  Focuses on data, features, experiments, models, and deployment — not isolated notebooks.

- **Databricks-aligned**  
  Concepts and lifecycle align with enterprise Lakehouse standards, even if implementations differ.

- **Explicit over magic**  
  No hidden automation. Every step is visible, inspectable, and explainable.

## Project Structure

solo-lakehouse/
├── .github/                   # GitHub Actions (CI/CD automation workflows)
├── assets/                    # Static assets (architecture diagrams, screenshots, GIFs)
├── config/                    # Configuration files for services (Crucial!)
│   ├── spark/
│   │   └── spark-defaults.conf
│   ├── trino/
│   │   └── catalog/
│   │       └── nessie.properties
│   └── prometheus/            # (Optional) Prometheus monitoring config
├── data/                      # Local data volume mappings (ignored in .gitignore)
├── docker/                    # Docker-related resources and builds
│   ├── Dockerfile.spark       # Custom Spark image build definition
│   ├── Dockerfile.serving     # Image definition for model serving
│   └── .env.example           # Environment variable template
├── notebooks/                 # Jupyter Notebooks (Core demonstration code)
│   ├── 01_ingestion.ipynb     # ETL process demonstration
│   ├── 02_mlops_flow.ipynb    # MLflow training pipeline demo
│   └── 03_nessie_git.ipynb    # Data versioning demo with Nessie
├── scripts/                   # Helper/Utility scripts
│   ├── init_buckets.sh        # MinIO bucket initialization script
│   └── start.sh               # One-click startup script
├── apps/                      # Application layer code
│   └── streamlit_app.py       # Frontend demonstration app (Streamlit)
├── docker-compose.yml         # Main Docker Compose orchestration file
├── Makefile                   # Shortcut commands (e.g., make up, make down)
├── LICENSE                    # MIT or Apache 2.0
├── README.md                  # Project documentation and entry point
└── requirements.txt           # Python dependencies
```




