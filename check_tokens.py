import sys
import os
import json
from pathlib import Path

# Setup paths
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.append(str(PROJECT_ROOT / 'src'))

print(f"📂 Diretório do Projeto: {PROJECT_ROOT}")

# Import TokenManager
try:
    from token_manager import TokenManager, DEFAULT_TOKENS_DIR
    print(f"✅ Importou token_manager de: {PROJECT_ROOT / 'src/token_manager.py'}")
except ImportError as e:
    print(f"❌ Erro ao importar: {e}")
    sys.exit(1)

# Check Environment
print(f"\n🔍 Verificando Ambiente:")
print(f"   DEFAULT_TOKENS_DIR: {DEFAULT_TOKENS_DIR}")
print(f"   Existe? {'✅ Sim' if DEFAULT_TOKENS_DIR.exists() else '❌ Não'}")

# List files
if DEFAULT_TOKENS_DIR.exists():
    print(f"\n📂 Arquivos em {DEFAULT_TOKENS_DIR}:")
    for f in DEFAULT_TOKENS_DIR.glob("*"):
        print(f"   - {f.name} ({f.stat().st_size} bytes)")

# Initialize Manager
print(f"\n🔑 Inicializando TokenManager...")
tm = TokenManager()
status = tm.get_status()

print(f"\n📊 STATUS DO TOKEN MANAGER:")
print(f"   Ativo: {'✅ SIM' if status['active'] else '🔴 NÃO'}")
print(f"   Contas: {status['total_accounts']}")
print(f"   Conta Atual: {status.get('current_account', {}).get('name')}")

if not status['active']:
    print("\n⚠️ DIAGNÓSTICO: O bot não encontrou tokens.")
    print("   Verifique se 'browser_cookies.json' está na pasta data/tokens")
else:
    print("\n✅ TUDO CERTO! O bot consegue ler os tokens.")

print("\n---------------------------------------------------")
