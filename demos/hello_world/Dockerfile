FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --only-binary=:all: -r requirements.txt

RUN groupadd --gid 10001 agent \
    && useradd --uid 10001 --gid agent --no-create-home --home-dir /tmp agent

COPY demos/ ./demos/

USER 10001:10001
EXPOSE 8080
CMD ["python", "-m", "uvicorn", "demos.hello_world.app:app", "--host", "0.0.0.0", "--port", "8080"]
