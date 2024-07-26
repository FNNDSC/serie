FROM python:3.12.3-alpine

WORKDIR /app
COPY requirements.lock ./
RUN sed -i' ' -e '/-e file:\./d' requirements.lock \
    && env PYTHONDONTWRITEBYTECODE=1 pip install --no-cache-dir -r requirements.lock

COPY src .
CMD ["fastapi", "run", "main.py"]
