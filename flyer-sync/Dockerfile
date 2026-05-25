FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Playwright browsers already installed in base image — just ensure chromium
RUN playwright install chromium
COPY ht_flyer_sync_job.py .
CMD ["python3", "ht_flyer_sync_job.py"]
