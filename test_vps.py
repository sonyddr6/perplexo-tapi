#!/usr/bin/env python3
"""
Teste de diagnóstico do Perplexity na VPS
Rode dentro do container: python /app/test_vps.py
"""
import os
import sys

print("=" * 50)
print("🔍 DIAGNÓSTICO PERPLEXITY VPS")
print("=" * 50)

# 1. Verifica token
token = os.getenv('PERPLEXITY_SESSION_TOKEN', '')
print(f"\n1️⃣ Token encontrado: {'✅ Sim' if token else '❌ Não'}")
if token:
    print(f"   Tamanho: {len(token)} caracteres")
    print(f"   Início: {token[:30]}...")
    print(f"   Fim: ...{token[-30:]}")

# 2. Testa importação
print("\n2️⃣ Testando importação do scraper...")
try:
    from perplexity_webui_scraper import Perplexity, ConversationConfig, Models
    print("   ✅ Importação OK")
except Exception as e:
    print(f"   ❌ Erro: {e}")
    sys.exit(1)

# 3. Testa inicialização do cliente
print("\n3️⃣ Testando inicialização do cliente...")
try:
    client = Perplexity(session_token=token)
    print("   ✅ Cliente criado")
except Exception as e:
    print(f"   ❌ Erro: {e}")
    sys.exit(1)

# 4. Testa criar conversa
print("\n4️⃣ Testando criar conversa...")
try:
    config = ConversationConfig(model=Models.SONAR, language="pt-BR")
    conversation = client.create_conversation(config)
    print("   ✅ Conversa criada")
except Exception as e:
    print(f"   ❌ Erro: {e}")
    sys.exit(1)

# 5. Testa busca REAL
print("\n5️⃣ Testando busca real (pode demorar)...")
print("   Enviando: 'Olá, teste'")
try:
    conversation.ask("Olá, teste")
    print("   ✅ BUSCA FUNCIONOU!")
    print(f"\n📝 Resposta:\n{conversation.answer[:300]}...")
except Exception as e:
    print(f"   ❌ ERRO NA BUSCA: {type(e).__name__}")
    print(f"   Mensagem: {e}")
    
    # Diagnóstico extra
    print("\n🔎 Diagnóstico extra:")
    import socket
    print(f"   Hostname: {socket.gethostname()}")
    
    # Testa conectividade
    import subprocess
    try:
        result = subprocess.run(['curl', '-I', 'https://www.perplexity.ai'], 
                               capture_output=True, text=True, timeout=10)
        print(f"   Curl status: {result.stdout.split()[1] if result.stdout else 'erro'}")
    except:
        print("   Curl: não disponível")

print("\n" + "=" * 50)
print("FIM DO DIAGNÓSTICO")
print("=" * 50)
