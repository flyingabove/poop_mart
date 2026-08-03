FROM python:3.11-slim

ENV PYTHONPATH=/srv
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /srv

COPY backend/  /srv/backend/
COPY frontend/ /srv/frontend/
COPY tests/    /srv/tests/
COPY pytest.ini /srv/pytest.ini

RUN pip install --no-cache-dir -r /srv/backend/requirements.txt

# Build-time test gate: a failing test aborts the build, so Railway never
# deploys a broken image. Override with RUN_TESTS=0 to skip (e.g. hotfixes).
RUN if [ "${RUN_TESTS:-1}" != "0" ]; then \
      python -m pytest /srv/tests --disable-warnings --tb=short -ra; \
    else \
      echo "RUN_TESTS=0 -> skipping build-time tests"; \
    fi

EXPOSE 8000

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
