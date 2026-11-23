FROM python:3.12-slim@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90
RUN pip install --no-cache-dir google-cloud-bigquery==3.36.0 google-cloud-storage==3.5.0
COPY main.py /app/main.py
CMD ["python", "/app/main.py"]
