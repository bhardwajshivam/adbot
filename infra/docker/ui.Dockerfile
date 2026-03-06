FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY apps/ui /app/apps/ui

WORKDIR /app/apps/ui

EXPOSE 8501
CMD ["streamlit", "run", "Home.py", "--server.address=0.0.0.0", "--server.port=8501"]
