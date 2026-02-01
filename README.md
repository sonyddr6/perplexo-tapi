# Perplexo Bot 🌀

Bot integrado com Perplexity AI para Telegram e WhatsApp.

## 🚀 Deploy Rápido no VPS (Hostinger)

### 1. Preparar o VPS

Conecte via SSH e instale Docker:

```bash
sudo apt update
sudo apt install -y docker.io docker-compose
sudo systemctl enable docker
sudo systemctl start docker
```

### 2. Clonar o Repositório

```bash
cd /root
git clone https://github.com/sonyddr666/perplexo-tapi.git
cd perplexo-tapi
```

### 3. Configurar Variáveis de Ambiente

```bash
cp .env.example .env
nano .env
```

Preencha com seus tokens:

```env
PERPLEXITY_SESSION_TOKEN=seu_token_aqui
TELEGRAM_TOKEN=seu_bot_token_aqui
```

**Como obter o PERPLEXITY_SESSION_TOKEN:**
1. Faça login em [perplexity.ai](https://perplexity.ai)
2. Abra DevTools (F12)
3. Vá em **Application > Cookies**
4. Copie o valor do cookie de sessão

**Como obter o TELEGRAM_TOKEN:**
1. Fale com [@BotFather](https://t.me/BotFather) no Telegram
2. Digite `/newbot` e siga as instruções
3. Copie o token fornecido

### 4. Criar Diretórios

```bash
mkdir -p logs config auth_info_baileys
```

### 5. Subir os Containers

```bash
docker-compose up -d
```

### 6. Verificar Status

```bash
docker-compose logs -f perplexo-bot
```

## 📦 Deploy via Painel Web Docker (Portainer)

### Usando Stack

1. Acesse o painel web
2. Vá em **Stacks > Add Stack**
3. Cole o conteúdo do `docker-compose.yml`
4. Adicione as variáveis de ambiente no formulário
5. Clique em **Deploy**

### Criando .env no VPS antes

```bash
cd /caminho/do/projeto
cp .env.example .env
nano .env
# Preencha os tokens
mkdir -p logs config auth_info_baileys
```

## 🤖 Comandos do Bot

- `/start` - Menu principal
- `/modelos` - Escolher modelo AI
- `/busca` - Configurar modo de busca (Focus)
- `/normal` - Conversa casual sem citações
- `/config` - Configurações avançadas
- `/ajuda` - Guia de uso

## 🔧 Troubleshooting

### Container não inicia

```bash
# Verificar logs
docker-compose logs perplexo-bot

# Rebuild da imagem
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Erro de conexão com MCP

Verifique se a variável `MCP_API_URL` está correta:
- Dentro do Docker: `http://perplexo-bot:5000`
- Fora do Docker: `http://127.0.0.1:5000`

### Erro "PERPLEXITY_SESSION_TOKEN inválido"

O token expira. Obtenha um novo:
1. Faça login novamente em perplexity.ai
2. Abra DevTools > Application > Cookies
3. Copie o novo token
4. Atualize o `.env` e reinicie:
   ```bash
   docker-compose restart
   ```

## 📝 Estrutura do Projeto

```
perplexo-tapi/
├── src/
│   ├── perplexity_mcp.py    # Servidor MCP/Flask
│   ├── telegram_bot.py      # Bot do Telegram
│   └── whatsapp_bot.js      # Bot do WhatsApp (opcional)
├── config/
│   └── nginx.conf.example   # Configuração Nginx (opcional)
├── Dockerfile               # Container Python
├── Dockerfile.whatsapp      # Container Node.js
├── docker-compose.yml       # Orquestração
├── .env.example             # Template de variáveis
└── README.md
```

## ⚙️ Variáveis de Ambiente

| Variável | Descrição | Obrigatória |
|----------|------------|-------------|
| `PERPLEXITY_SESSION_TOKEN` | Token de sessão do Perplexity | Sim |
| `TELEGRAM_TOKEN` | Token do bot do Telegram | Sim |
| `MCP_PORT` | Porta do servidor MCP (padrão: 5000) | Não |
| `TELEGRAM_PORT` | Porta do webhook Telegram (padrão: 8000) | Não |
| `MCP_API_URL` | URL da API MCP (padrão: http://perplexo-bot:5000) | Não |
| `FLASK_ENV` | Ambiente Flask (production/development) | Não |
| `WEBHOOK_URL` | URL do webhook (opcional, usa polling se vazio) | Não |

## 📚 Recursos

- **Modelos suportados:** GPT-5.2, Claude 4.5, Gemini 3, Grok 4.1, Sonar, Deep Research
- **Focus Modes:** Web, Academic, Writing, YouTube, Reddit, Wolfram
- **Análise de imagens:** Envie fotos para análise visual
- **Resumo de arquivos:** Envie .txt para resumir
- **Citações:** Fontes automáticas com links

## 📄 Licença

MIT
