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

# Cria TODOS os diretórios necessários
RUN mkdir -p \
    /app/logs \
    /app/config \
    /app/auth_info_baileys \
    /app/data/tokens \
    /app/data/conversations \
    /app/data/tasks

# Copia código fonte
COPY src/ ./src/

# Copia scripts de refresh
COPY scripts/ ./scripts/

# Copia arquivos de dados (tokens e cookies do GitHub)
COPY data/tokens/*.json ./data/tokens/

# Variáveis de ambiente
ENV PYTHONUNBUFFERED=1
ENV FLASK_ENV=production
ENV MCP_PORT=5000
ENV TELEGRAM_PORT=8000
ENV TOKENS_DIR=/app/data/tokens

# Expõe portas
EXPOSE 5000 8000

# Script de entrada
COPY docker-entrypoint.sh .
RUN chmod +x docker-entrypoint.sh

CMD ["./docker-entrypoint.sh"]
