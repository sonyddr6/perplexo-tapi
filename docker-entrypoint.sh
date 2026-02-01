#!/bin/bash
set -e

echo "🌀 Iniciando Perplexo Bot..."

# Inicia MCP Server em background
echo "🔌 Iniciando MCP Server na porta ${MCP_PORT:-5000}..."
python src/perplexity_mcp.py &

# Aguarda MCP iniciar
sleep 3

# Inicia Telegram Bot
echo "🤖 Iniciando Telegram Bot..."
python src/telegram_bot.py
