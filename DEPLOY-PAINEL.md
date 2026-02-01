# Deploy via Painel Docker (Hostinger VPS)

## Passo a Passo Completo

### 1️⃣ Preparar VPS via SSH

Conecte no VPS e execute:

```bash
cd /root
git clone https://github.com/sonyddr666/perplexo-tapi.git
cd perplexo-tapi

# Criar diretórios
mkdir -p logs config auth_info_baileys

# Criar arquivo .env
cp .env.example .env
nano .env
```

Preencha o `.env` com seus tokens:

```env
PERPLEXITY_SESSION_TOKEN=seu_token_real_aqui
TELEGRAM_TOKEN=seu_bot_token_aqui
MCP_PORT=5000
TELEGRAM_PORT=8000
MCP_API_URL=http://perplexo-bot:5000
FLASK_ENV=production
```

Salve: `Ctrl+O`, Enter, `Ctrl+X`

### 2️⃣ Importar no Painel Docker

#### Opção A: Via Stacks (RECOMENDADO)

1. Abra o painel Docker (Portainer ou similar)
2. Vá em **Stacks** (ou **Pilhas**)
3. Clique em **Add Stack** (ou **Adicionar Stack**)
4. Cole o conteúdo do arquivo `docker-compose.yml` completo:

```yaml
services:
  perplexo-bot:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: perplexo-bot
    restart: unless-stopped
    env_file:
      - .env
    environment:
      - MCP_PORT=5000
      - TELEGRAM_PORT=8000
      - MCP_API_URL=http://perplexo-bot:5000
    ports:
      - "5000:5000"
      - "8000:8000"
    volumes:
      - ./logs:/app/logs
      - ./config:/app/config
      - ./auth_info_baileys:/app/auth_info_baileys
    networks:
      - perplexo-net

networks:
  perplexo-net:
    driver: bridge
```

5. Configure **Working Directory**: `/root/perplexo-tapi`
6. Clique em **Deploy**

#### Opção B: Via Container Individual

Se o painel não tem Stacks, configure manualmente:

**Nome do Container:**
```
perplexo-bot
```

**Imagem:**
```
sonyddr666/perplexo-tapi:latest
```
(Ou faça build local)

**Portas:**
```
5000:5000
8000:8000
```

**Volumes** (clique em "+ Volume" para cada):
```
/root/perplexo-tapi/logs:/app/logs
/root/perplexo-tapi/config:/app/config
/root/perplexo-tapi/auth_info_baileys:/app/auth_info_baileys
```

**Variáveis de Ambiente** (adicione uma por vez):
```
PERPLEXITY_SESSION_TOKEN=seu_token_aqui
TELEGRAM_TOKEN=seu_bot_token
MCP_PORT=5000
TELEGRAM_PORT=8000
MCP_API_URL=http://perplexo-bot:5000
FLASK_ENV=production
```

**Rede:**
```
perplexo-net
```

**Restart Policy:**
```
unless-stopped
```

### 3️⃣ Verificar Funcionamento

1. No painel, abra os **Logs** do container
2. Procure por:
   ```
   🚀 MCP Server iniciando na porta 5000
   ✅ Scraper disponível: True
   ✅ Cliente inicializado: True
   ```

3. Teste o bot no Telegram enviando `/start`

### 4️⃣ Troubleshooting

#### Container não inicia

- Verifique se o arquivo `.env` existe no VPS
- Confira se os diretórios `logs`, `config`, `auth_info_baileys` existem
- Veja os logs do container no painel

#### Erro "PERPLEXITY_SESSION_TOKEN não configurado"

1. SSH no VPS:
   ```bash
   cd /root/perplexo-tapi
   cat .env  # Verificar se tem conteúdo
   ```

2. Se vazio, edite:
   ```bash
   nano .env
   # Adicione os tokens
   ```

3. Reinicie o container no painel

#### Erro "Erro de conexão com MCP"

- Verifique se `MCP_API_URL=http://perplexo-bot:5000` (use o nome do container, não `127.0.0.1`)
- Confirme que o container está na rede `perplexo-net`

#### Como obter PERPLEXITY_SESSION_TOKEN

1. Acesse [perplexity.ai](https://perplexity.ai) e faça login
2. Pressione F12 para abrir DevTools
3. Vá em **Application** (ou **Aplicação**)
4. Clique em **Cookies** > `https://www.perplexity.ai`
5. Procure por um cookie de sessão (geralmente começa com `__Secure-` ou similar)
6. Copie o **Value** completo
7. Cole no `.env`

#### Como obter TELEGRAM_TOKEN

1. Abra o Telegram e fale com [@BotFather](https://t.me/BotFather)
2. Digite `/newbot`
3. Siga as instruções (escolha um nome e username)
4. Copie o token fornecido (formato: `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`)
5. Cole no `.env`

### 🎯 Checklist Final

- [ ] `.env` criado com tokens reais
- [ ] Diretórios `logs`, `config`, `auth_info_baileys` criados
- [ ] Container configurado com todos os volumes
- [ ] Todas as variáveis de ambiente adicionadas
- [ ] Portas 5000 e 8000 expostas
- [ ] Container na rede `perplexo-net`
- [ ] Restart policy: `unless-stopped`
- [ ] Logs mostram inicialização bem-sucedida
- [ ] Bot responde `/start` no Telegram

### 🔄 Atualizar para Nova Versão

Quando houver atualizações no GitHub:

```bash
# SSH no VPS
cd /root/perplexo-tapi
git pull
```

Depois no painel:
1. Pare o container
2. Clique em **Recreate** ou **Rebuild**
3. Inicie novamente

---

**Dúvidas?** Verifique os logs do container no painel ou rode `docker-compose logs -f` via SSH.
