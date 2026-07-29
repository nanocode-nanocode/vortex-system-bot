FROM python:3.12-slim

WORKDIR /app

RUN pip install flask flask-limiter flask-cors gunicorn cryptography bcrypt

COPY main.py .
COPY templates/ templates/
COPY _run_vortex_web.py .
RUN mkdir -p data bots sites logs

EXPOSE 8080

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--timeout", "120", "main:app"]
