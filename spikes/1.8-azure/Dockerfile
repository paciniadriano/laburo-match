# Spike 1.8 image. Base pinned by digest (python:3.14-slim, linux/amd64), as the project requires.
FROM python@sha256:9aaa474097d094040649f2162a627c0049b408f52138d980916788d80f04802f

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN useradd --create-home --uid 10001 app
WORKDIR /app
RUN pip install "fastmcp>=3.4.7,<4"
COPY server.py .
USER app
EXPOSE 8000
CMD ["python", "server.py"]
