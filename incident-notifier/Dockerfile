FROM python:3.12-slim

RUN useradd --system --home /app --shell /usr/sbin/nologin notifier

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY notifier/ notifier/
COPY run.py .
COPY templates/ templates/

RUN mkdir -p /data && chown -R notifier:notifier /app /data

USER notifier

ENV INCIDENT_NOTIFIER_CONFIG=/config/config.yaml

EXPOSE 5080

CMD ["python", "run.py"]
