FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends pandoc git curl ca-certificates nodejs npm && rm -rf /var/lib/apt/lists/* \
 && npm install -g @anthropic-ai/claude-code
WORKDIR /app
COPY pyproject.toml README.md ./
COPY sethread ./sethread
RUN pip install --no-cache-dir . && mkdir -p /data
ENV SETHREAD_DATA=/data SETHREAD_SECRET=change-me
# ANTHROPIC_API_KEY and SETHREAD_INVITE are passed at run time
EXPOSE 8765
CMD ["sh", "-c", "launch serve --data $SETHREAD_DATA --host 0.0.0.0 --port 8765"]
