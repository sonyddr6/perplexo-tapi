# =====================
# Perplexo Bot - Python
# =====================
# MCP Server + Telegram Bot

FROM python:3.11-slim

WORKDIR /app

# Dependências do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copia requirements
COPY requirements.txt .

# Instala dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Instala o scraper do Perplexity
RUN pip install --no-cache-dir git+https://github.com/henrique-coder/perplexity-webui-scraper

# Cria diretórios necessários
RUN mkdir -p /app/logs /app/config /app/auth_info_baileys

# Copia código fonte
COPY src/ ./src/

# Copia configurações (se existirem)
COPY config/ ./config/ 2>/dev/null || true

# Variáveis de ambiente
ENV PYTHONUNBUFFERED=1
ENV FLASK_ENV=production
ENV MCP_PORT=5000
ENV TELEGRAM_PORT=8000

# Expõe portas
EXPOSE 5000 8000

# Script de entrada
COPY docker-entrypoint.sh .
RUN chmod +x docker-entrypoint.sh

CMD ["./docker-entrypoint.sh"]
