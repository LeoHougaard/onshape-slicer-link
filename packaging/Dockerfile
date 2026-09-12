FROM python:3.12-slim-bookworm
WORKDIR /app
COPY pyproject.toml LICENSE ./
COPY slicer_link ./slicer_link
COPY packaging/requirements-server.txt ./requirements-server.txt
RUN pip install --no-cache-dir --require-hashes -r requirements-server.txt \
    && pip install --no-cache-dir --no-deps . && useradd --create-home --uid 10001 slicerlink \
    && mkdir /data && chown slicerlink:slicerlink /data
USER slicerlink
ENV OSL_DATA_DIR=/data PYTHONUNBUFFERED=1
EXPOSE 8767
CMD ["python", "-m", "uvicorn", "slicer_link.asgi:app", "--host", "0.0.0.0", "--port", "8767", "--no-access-log", "--no-proxy-headers"]
