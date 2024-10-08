FROM python:3.12.6-alpine3.20

WORKDIR /app
ARG REQUIREMENTS_FILE=requirements.lock
COPY ${REQUIREMENTS_FILE} ./requirements.txt
RUN --mount=type=cache,sharing=locked,target=/root/.cache/pip \
    sed -i' ' -e '/-e file:\./d' requirements.txt \
    && env PYTHONDONTWRITEBYTECODE=1 pip install -r requirements.txt

COPY src .
CMD ["fastapi", "run", "main.py"]
