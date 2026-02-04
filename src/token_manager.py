"""
Token Manager - Gerenciador de Cookies/Tokens do Perplexity
=============================================================
Permite usar cookies extraídos do browser para autenticação,
com suporte a múltiplas contas e rotação round-robin.

Como obter cookies:
1. Abra perplexity.ai e faça login
2. F12 → Application → Cookies → .perplexity.ai
3. Copie o valor de `__Secure-next-auth.session-token`
4. Salve em data/tokens/cookies.json

Formato do arquivo cookies.json:
{
    "accounts": [
        {
            "name": "conta_principal",
            "session_token": "eyJhbGciOi..."
        },
        {
            "name": "conta_backup",
            "session_token": "eyJhbGciOi..."
        }
    ],
    "current_index": 0
}
"""

import os
import json
import logging
import requests
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any

logger = logging.getLogger(__name__)

# ============= CONFIGURAÇÃO =============

# Resolve paths relative to the project root (where src/ is)
BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_TOKENS_DIR = Path(os.getenv("TOKENS_DIR", BASE_DIR / "data" / "tokens"))
DEFAULT_COOKIES_FILE = os.getenv("PERPLEXITY_COOKIES_FILE", "cookies.json")
DEFAULT_RAW_COOKIES_FILE = os.getenv("PERPLEXITY_RAW_COOKIES_FILE", "browser_cookies.json")
TOKEN_ROTATION_ENABLED = os.getenv("TOKEN_ROTATION_ENABLED", "true").lower() == "true"

# Cookies necessários do Perplexity
PERPLEXITY_COOKIE_NAMES = [
    "__Secure-next-auth.session-token",  # PRINCIPAL - JWT de sessão
    "next-auth.csrf-token",               # Anti-CSRF
    "__Secure-next-auth.callback-url",    # URL de callback
]


class TokenManager:
    """
    Gerenciador de tokens/cookies do Perplexity.ai
    
    Funcionalidades:
    - Carrega tokens de arquivo JSON ou variáveis de ambiente
    - Rotação round-robin entre múltiplas contas
    - Validação de tokens
    - Persistência e reload
    """
    
    def __init__(self, tokens_dir: Path = None, cookies_file: str = None):
        self.tokens_dir = tokens_dir or DEFAULT_TOKENS_DIR
        self.cookies_file = cookies_file or DEFAULT_COOKIES_FILE
        self.tokens_dir.mkdir(parents=True, exist_ok=True)
        
        self.accounts: List[Dict[str, Any]] = []
        self.current_index = 0
        self.rotation_enabled = TOKEN_ROTATION_ENABLED
        self._env_token = os.getenv("PERPLEXITY_SESSION_TOKEN", "")
        
        # Carrega tokens
        # Carrega tokens
        self.reload_tokens()
    
    def _load_raw_tokens(self) -> List[Dict[str, str]]:
        """Carrega tokens de um arquivo de exportação de cookies (array de objetos)"""
        raw_path = self.tokens_dir / DEFAULT_RAW_COOKIES_FILE
        if not raw_path.exists():
            return []
            
        try:
            with open(raw_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            if not isinstance(data, list):
                return []
                
            # Procura pelo token de sessão
            found_tokens = []
            for cookie in data:
                if cookie.get('name') == "__Secure-next-auth.session-token":
                    val = cookie.get('value')
                    if val:
                        found_tokens.append({
                            "name": f"Browser Export {len(found_tokens)+1}",
                            "session_token": val
                        })
            
            if found_tokens:
                logger.info(f"🍪 TokenManager: Carregados {len(found_tokens)} tokens via {DEFAULT_RAW_COOKIES_FILE}")
            
            return found_tokens
            
        except Exception as e:
            logger.error(f"Erro ao ler raw cookies: {e}")
            return []

    def reload_tokens(self):
        """Recarrega tokens do disco (alias para _load_tokens)"""
        self._load_tokens()

    def _load_tokens(self):
        """Carrega tokens do arquivo JSON (e raw) ou fallback para .env"""
        # 1. Carrega tokens raw (Browser Export)
        self.accounts = self._load_raw_tokens()
        
        # 2. Carrega tokens estruturados (cookies.json)
        cookies_path = self.tokens_dir / self.cookies_file
        
        if cookies_path.exists():
            try:
                with open(cookies_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                file_accounts = data.get('accounts', [])
                # Mescla (append)
                self.accounts.extend(file_accounts)
                
                # Restaura indice se valido
                idx = data.get('current_index', 0)
                if idx < len(self.accounts):
                    self.current_index = idx # Nota: isso pode apontar para token errado se a lista mudou
                
            except Exception as e:
                logger.error(f"Erro ao ler cookies.json: {e}")

        # Se não tem nada, tenta env var
        if not self.accounts:
            if self._env_token:
                self.accounts.append({
                    "name": "ENV_TOKEN",
                    "session_token": self._env_token
                })
        
        # Remove duplicatas
        unique = []
        seen = set()
        for acc in self.accounts:
            t = acc.get('session_token')
            if t and t not in seen:
                seen.add(t)
                unique.append(acc)
        self.accounts = unique

        # Garante índice válido
        if self.current_index >= len(self.accounts):
            self.current_index = 0
            
        logger.info(f"✅ TokenManager: Total {len(self.accounts)} conta(s) ativas.")
        # Valida cada conta
        for i, acc in enumerate(self.accounts):
            name = acc.get('name', f'conta_{i}')
            token = acc.get('session_token', '')
            if token and len(token) > 20:
                logger.info(f"   📋 {name}: token presente ({len(token)} chars)")
            else:
                logger.warning(f"   ⚠️ {name}: token inválido ou vazio")
        
        # Fallback para variável de ambiente
        if not self.accounts and self._env_token:
            logger.info("📌 Usando PERPLEXITY_SESSION_TOKEN do .env como fallback")
            self.accounts = [{
                "name": "env_token",
                "session_token": self._env_token,
                "source": "environment"
            }]
    
    def get_current_token(self) -> Optional[str]:
        """Retorna o token atual sem rotacionar"""
        if not self.accounts:
            return self._env_token or None
        
        if self.current_index < len(self.accounts):
            return self.accounts[self.current_index].get('session_token')
        
        return None
    
    def get_next_token(self) -> Optional[str]:
        """Retorna próximo token (rotação round-robin se habilitada)"""
        if not self.accounts:
            return self._env_token or None
        
        token = self.get_current_token()
        
        if self.rotation_enabled and len(self.accounts) > 1:
            self.current_index = (self.current_index + 1) % len(self.accounts)
            self._save_state()
            logger.debug(f"🔄 Token rotacionado para conta {self.current_index}")
        
        return token
    
    def get_account_info(self) -> Dict[str, Any]:
        """Retorna informações da conta atual"""
        if not self.accounts:
            return {"name": "env_token", "source": "environment"}
        
        if self.current_index < len(self.accounts):
            acc = self.accounts[self.current_index]
            return {
                "name": acc.get('name', f'conta_{self.current_index}'),
                "index": self.current_index,
                "total_accounts": len(self.accounts),
                "last_validated": acc.get('last_validated'),
                "source": acc.get('source', 'cookies.json')
            }
        
        return {}
    
    def validate_token(self, token: str = None) -> bool:
        """
        Valida se um token ainda é válido fazendo uma requisição simples.
        
        NOTA: Isso faz uma requisição real à Perplexity!
        Use com moderação para evitar rate limiting.
        """
        token = token or self.get_current_token()
        if not token:
            return False
        
        try:
            headers = {
                "Cookie": f"__Secure-next-auth.session-token={token}",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            
            # Tenta usar curl_cffi para evitar bloqueio do Cloudflare
            try:
                from curl_cffi import requests as cffi_requests
                # impersonate="chrome" é crucial
                response = cffi_requests.get(
                    "https://www.perplexity.ai/api/auth/session",
                    headers=headers,
                    timeout=10,
                    impersonate="chrome"
                )
            except ImportError:
                logger.warning("⚠️ curl_cffi não instalado, usando requests (pode falhar com 403)")
                response = requests.get(
                    "https://www.perplexity.ai/api/auth/session",
                    headers=headers,
                    timeout=10
                )
            
            if response.status_code == 200:
                data = response.json()
                # Verifica se retornou usuário logado
                if data.get('user'):
                    # Atualiza timestamp de validação
                    if self.accounts and self.current_index < len(self.accounts):
                        self.accounts[self.current_index]['last_validated'] = datetime.now().isoformat()
                        self._save_state()
                    
                    logger.info(f"✅ Token validado: {data.get('user', {}).get('email', 'OK')}")
                    return True
            
            logger.warning(f"⚠️ Token inválido ou expirado (status {response.status_code})")
            return False
            
        except Exception as e:
            logger.error(f"❌ Erro ao validar token: {e}")
            return False
    
    def refresh_from_browser_cookies(self) -> Dict[str, Any]:
        """
        Tenta obter um novo token usando todos os cookies do browser_cookies.json.
        Simula o comportamento de abrir uma nova aba no navegador.
        
        Returns:
            Dict com 'success', 'new_token', 'old_token', 'message'
        """
        result = {
            "success": False,
            "new_token": None,
            "old_token": None,
            "message": ""
        }
        
        # 1. Carregar todos os cookies do browser_cookies.json
        raw_path = self.tokens_dir / DEFAULT_RAW_COOKIES_FILE
        if not raw_path.exists():
            result["message"] = f"Arquivo {DEFAULT_RAW_COOKIES_FILE} não encontrado"
            logger.warning(f"⚠️ {result['message']}")
            return result
        
        try:
            with open(raw_path, 'r', encoding='utf-8') as f:
                raw_cookies = json.load(f)
        except Exception as e:
            result["message"] = f"Erro ao ler {DEFAULT_RAW_COOKIES_FILE}: {e}"
            logger.error(f"❌ {result['message']}")
            return result
        
        if not isinstance(raw_cookies, list):
            result["message"] = "Formato inválido: esperado array de cookies"
            return result
        
        # 2. Converter para dicionário
        all_cookies = {}
        for cookie in raw_cookies:
            name = cookie.get('name')
            value = cookie.get('value')
            if name and value:
                all_cookies[name] = value
        
        result["old_token"] = all_cookies.get("__Secure-next-auth.session-token", "")[:50] + "..."
        
        if not all_cookies.get("__Secure-next-auth.session-token"):
            result["message"] = "Session token não encontrado nos cookies"
            return result
        
        logger.info(f"🍪 Carregados {len(all_cookies)} cookies do browser")
        
        # 3. Fazer requisição para /api/auth/session
        try:
            from curl_cffi import requests as cffi_requests
        except ImportError:
            result["message"] = "curl_cffi não instalado (pip install curl-cffi)"
            return result
        
        headers = {
            "Accept": "*/*",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": "https://www.perplexity.ai/",
            "sec-ch-ua": '"Not(A:Brand";v="8", "Chromium";v="144", "Google Chrome";v="144"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "x-app-apiclient": "default",
            "x-app-apiversion": "2.18"
        }
        
        try:
            response = cffi_requests.get(
                "https://www.perplexity.ai/api/auth/session?version=2.18&source=default",
                headers=headers,
                cookies=all_cookies,
                impersonate="chrome",
                timeout=15
            )
            
            if response.status_code == 200:
                # Verificar se retornou novo token
                new_token = None
                if hasattr(response, 'cookies'):
                    new_token = response.cookies.get("__Secure-next-auth.session-token")
                
                if new_token:
                    result["new_token"] = new_token
                    result["success"] = True
                    
                    # Salvar o novo token
                    self._save_refreshed_token(new_token)
                    
                    # Recarregar tokens
                    self.reload_tokens()
                    
                    result["message"] = "Token renovado com sucesso!"
                    logger.info(f"🎉 Token renovado! Novo: {new_token[:30]}...")
                else:
                    result["message"] = "Servidor não retornou novo token (token atual ainda válido)"
                    result["success"] = True  # Não é erro, só não rotacionou
                    
            elif response.status_code == 403:
                result["message"] = "Cloudflare bloqueou (403). Cookies podem estar expirados."
            elif response.status_code == 401:
                result["message"] = "Token expirado ou inválido (401)"
            else:
                result["message"] = f"Status inesperado: {response.status_code}"
                
        except Exception as e:
            result["message"] = f"Erro na requisição: {e}"
            logger.error(f"❌ {result['message']}")
        
        return result
    
    def _save_refreshed_token(self, token: str):
        """Salva token renovado no cookies.json"""
        cookies_path = self.tokens_dir / self.cookies_file
        
        try:
            if cookies_path.exists():
                with open(cookies_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                data = {"accounts": [], "current_index": 0}
            
            new_account = {
                "name": "auto_refreshed",
                "session_token": token,
                "refreshed_at": datetime.now().isoformat(),
                "source": "browser_refresh"
            }
            
            # Remove refresh anterior se existir
            data['accounts'] = [a for a in data['accounts'] if a.get('name') != 'auto_refreshed']
            data['accounts'].insert(0, new_account)  # Coloca no início
            data['current_index'] = 0
            data['updated_at'] = datetime.now().isoformat()
            
            with open(cookies_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"💾 Token salvo em {cookies_path}")
            
        except Exception as e:
            logger.error(f"❌ Erro ao salvar token renovado: {e}")
    
    def add_account(self, name: str, session_token: str, validate: bool = True) -> bool:
        """Adiciona uma nova conta ao gerenciador"""
        if validate and not self.validate_token(session_token):
            logger.warning(f"⚠️ Token para '{name}' é inválido, não foi adicionado")
            return False
        
        # Remove conta existente com mesmo nome
        self.accounts = [a for a in self.accounts if a.get('name') != name]
        
        self.accounts.append({
            "name": name,
            "session_token": session_token,
            "added_at": datetime.now().isoformat(),
            "last_validated": datetime.now().isoformat() if validate else None
        })
        
        self._save_state()
        logger.info(f"✅ Conta '{name}' adicionada ao TokenManager")
        return True
    
    def remove_account(self, name: str) -> bool:
        """Remove uma conta do gerenciador"""
        initial_count = len(self.accounts)
        self.accounts = [a for a in self.accounts if a.get('name') != name]
        
        if len(self.accounts) < initial_count:
            # Ajusta índice se necessário
            if self.current_index >= len(self.accounts):
                self.current_index = max(0, len(self.accounts) - 1)
            self._save_state()
            logger.info(f"🗑️ Conta '{name}' removida")
            return True
        
        return False
    
    def _save_state(self):
        """Persiste estado atual no arquivo JSON"""
        cookies_path = self.tokens_dir / self.cookies_file
        
        try:
            data = {
                "accounts": self.accounts,
                "current_index": self.current_index,
                "updated_at": datetime.now().isoformat()
            }
            
            with open(cookies_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.debug(f"💾 Estado salvo em {cookies_path}")
            
        except Exception as e:
            logger.error(f"❌ Erro ao salvar estado: {e}")
    
    def reload(self):
        """Recarrega tokens do arquivo"""
        self._load_tokens()
    
    def get_status(self) -> Dict[str, Any]:
        """Retorna status completo do TokenManager"""
        return {
            "active": bool(self.accounts),
            "total_accounts": len(self.accounts),
            "current_index": self.current_index,
            "current_account": self.get_account_info(),
            "rotation_enabled": self.rotation_enabled,
            "tokens_dir": str(self.tokens_dir),
            "accounts": [
                {
                    "name": a.get('name', f'conta_{i}'),
                    "token_length": len(a.get('session_token', '')),
                    "last_validated": a.get('last_validated'),
                    "source": a.get('source', 'file')
                }
                for i, a in enumerate(self.accounts)
            ]
        }


# ============= FUNÇÕES UTILITÁRIAS =============

def parse_browser_cookies(cookie_string: str) -> Dict[str, str]:
    """
    Parseia string de cookies do browser (formato DevTools).
    
    Uso:
        cookies = parse_browser_cookies("__Secure-next-auth.session-token=eyJ...; next-auth.csrf-token=xxx")
    """
    cookies = {}
    
    if not cookie_string:
        return cookies
    
    for part in cookie_string.split(';'):
        part = part.strip()
        if '=' in part:
            name, value = part.split('=', 1)
            cookies[name.strip()] = value.strip()
    
    return cookies


def extract_session_token(cookie_string: str) -> Optional[str]:
    """Extrai apenas o session token de uma string de cookies"""
    cookies = parse_browser_cookies(cookie_string)
    return cookies.get('__Secure-next-auth.session-token')


def create_cookies_file_template(output_path: Path = None):
    """Cria um arquivo de template para cookies.json"""
    output_path = output_path or DEFAULT_TOKENS_DIR / "cookies.json.example"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    template = {
        "accounts": [
            {
                "name": "conta_principal",
                "session_token": "COLE_SEU_SESSION_TOKEN_AQUI",
                "_comment": "Obtenha em: F12 → Application → Cookies → __Secure-next-auth.session-token"
            },
            {
                "name": "conta_backup",
                "session_token": "TOKEN_CONTA_2_AQUI"
            }
        ],
        "current_index": 0
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(template, f, ensure_ascii=False, indent=2)
    
    logger.info(f"📝 Template criado: {output_path}")
    return output_path


# ============= SINGLETON =============

_token_manager: Optional[TokenManager] = None

def get_token_manager() -> TokenManager:
    """Retorna instância singleton do TokenManager"""
    global _token_manager
    if _token_manager is None:
        _token_manager = TokenManager()
    return _token_manager


# ============= CLI =============

if __name__ == "__main__":
    import sys
    
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    
    tm = TokenManager()
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        
        if cmd == "status":
            import pprint
            pprint.pprint(tm.get_status())
        
        elif cmd == "validate":
            token = sys.argv[2] if len(sys.argv) > 2 else None
            result = tm.validate_token(token)
            print(f"Token válido: {result}")
        
        elif cmd == "add" and len(sys.argv) >= 4:
            name = sys.argv[2]
            token = sys.argv[3]
            tm.add_account(name, token)
        
        elif cmd == "template":
            create_cookies_file_template()
        
        else:
            print("""
Token Manager - Gerenciador de Cookies do Perplexity

Comandos:
    python token_manager.py status              - Mostra status atual
    python token_manager.py validate [token]    - Valida token atual ou específico
    python token_manager.py add <nome> <token>  - Adiciona nova conta
    python token_manager.py template            - Cria arquivo de exemplo
            """)
    else:
        # Mostra status por padrão
        print(f"\n🔑 TokenManager Status:")
        print(f"   Contas: {len(tm.accounts)}")
        print(f"   Rotação: {'✅' if tm.rotation_enabled else '❌'}")
        
        if tm.accounts:
            print(f"\n   Conta atual: {tm.get_account_info().get('name')}")
            token = tm.get_current_token()
            if token:
                print(f"   Token: {token[:30]}...{token[-10:]}")
