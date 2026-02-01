"""
Teste rápido do Perplexity Scraper
Rode: python test_perplexity.py
"""
from dotenv import load_dotenv
import os

# Carrega .env
load_dotenv()

from perplexity_webui_scraper import Perplexity, ConversationConfig, Models

token = os.getenv('PERPLEXITY_SESSION_TOKEN')
if not token:
    print('❌ PERPLEXITY_SESSION_TOKEN não encontrado no .env!')
    exit(1)

print(f'Token: {token[:25]}...')

try:
    client = Perplexity(session_token=token)
    print('✅ Cliente inicializado!')
    
    # Teste de busca real
    config = ConversationConfig(model=Models.SONAR, language="pt-BR")
    conversation = client.create_conversation(config)
    print('✅ Conversa criada!')
    
    conversation.ask("Olá, tudo bem?")
    print('✅ BUSCA FUNCIONOU!')
    print(f'\n📝 Resposta:\n{conversation.answer[:500]}...')
    
except Exception as e:
    print(f'❌ ERRO: {type(e).__name__}: {e}')
