<div align="center">
  <img width="300" alt="SoloLakehouse_icon2"  src="https://github.com/user-attachments/assets/de7c68f4-9c9a-4c9e-867e-bb8a20df302f" />

  <img width="300" alt="SoloLakehouse_icon" src="https://github.com/user-attachments/assets/f7499da8-f064-4dfc-91b9-c11a152eb24a" />
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

```text
solo-lakehouse/
├── .github/                   # GitHub Actions (CI/CD 自动化检查)
├── assets/                    # 存放架构图、截图、演示 GIF
├── config/                    # 各个组件的配置文件 (关键！)
│   ├── spark/
│   │   └── spark-defaults.conf
│   ├── trino/
│   │   └── catalog/
│   │       └── nessie.properties
│   └── prometheus/            # (可选) 监控配置
├── data/                      # 本地映射的数据目录 (在 .gitignore 中忽略)
├── docker/                    # Docker 相关文件
│   ├── Dockerfile.spark       # 如果有自定义构建
│   ├── Dockerfile.serving     # 模型服务的镜像定义
│   └── .env.example           # 环境变量模板
├── notebooks/                 # Jupyter Notebooks (你的核心演示代码)
│   ├── 01_ingestion.ipynb     # ETL 演示
│   ├── 02_mlops_flow.ipynb    # MLflow 训练演示
│   └── 03_nessie_git.ipynb    # 数据版本控制演示
├── scripts/                   # 辅助脚本
│   ├── init_buckets.sh        # 初始化 MinIO 桶
│   └── start.sh               # 一键启动脚本
├── apps/                      # 应用层代码
│   └── streamlit_app.py       # 前端演示应用
├── docker-compose.yml         # 核心编排文件
├── Makefile                   # 快捷命令 (如 make up, make down)
├── LICENSE                    # MIT or Apache 2.0
├── README.md                  # 项目门面 (最重要的文件)
└── requirements.txt           # Python 依赖
```




