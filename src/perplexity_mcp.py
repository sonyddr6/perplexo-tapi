"""
Perplexity MCP Server
=====================
API Flask que integra com o scraper real do Perplexity.ai
usando perplexity-webui-scraper.

Endpoints:
- POST /search   - Busca com modelo/focus configurável
- POST /vision   - Análise de imagens/arquivos
- GET  /models   - Lista modelos e focus modes disponíveis
- GET  /health   - Health check

Uso:
    pip install git+https://github.com/henrique-coder/perplexity-webui-scraper
    python src/perplexity_mcp.py
"""

import os
import sys
import base64
import tempfile
import logging
import traceback
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

from flask import Flask, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv

# Carrega .env
load_dotenv()

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============= CONFIGURAÇÃO =============

app = Flask(__name__)

# Rate limiting
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["100 per hour", "10 per minute"]
)

# Session token do Perplexity
PERPLEXITY_SESSION_TOKEN = os.getenv("PERPLEXITY_SESSION_TOKEN", "")
MCP_PORT = int(os.getenv("MCP_PORT", 5000))

# ============= TOKEN MANAGER =============
from token_manager import get_token_manager, TokenManager

try:
    token_manager = get_token_manager()
    logger.info(f"🔑 TokenManager inicializado: {len(token_manager.accounts)} conta(s)")
except Exception as e:
    logger.warning(f"⚠️ TokenManager não disponível: {e}")
    token_manager = None

# ============= IMPORTAÇÃO DO SCRAPER REAL =============

SCRAPER_AVAILABLE = False
Perplexity = None
ConversationConfig = None
Models = None
SourceFocus = None
CitationMode = None

try:
    from perplexity_webui_scraper import Perplexity as _Perplexity
    from perplexity_webui_scraper import ConversationConfig as _ConversationConfig
    from perplexity_webui_scraper import Models as _Models
    from perplexity_webui_scraper import CitationMode as _CitationMode
    
    Perplexity = _Perplexity
    ConversationConfig = _ConversationConfig
    Models = _Models
    Models = _Models
    CitationMode = _CitationMode
    
    # Tenta importar TimeRange e SourceFocus
    try:
        from perplexity_webui_scraper import SourceFocus as _SourceFocus
        SourceFocus = _SourceFocus
    except ImportError:
        logger.warning("⚠️ SourceFocus não disponível")
        SourceFocus = None

    try:
        from perplexity_webui_scraper import TimeRange as _TimeRange
        TimeRange = _TimeRange
    except ImportError:
        logger.warning("⚠️ TimeRange não disponível")
        TimeRange = None
    
    SCRAPER_AVAILABLE = True
    logger.info("✅ Scraper perplexity-webui-scraper carregado com sucesso!")
    
    # Log dos modelos disponíveis
    if Models:
        available_models = [attr for attr in dir(Models) if not attr.startswith('_')]
        logger.info(f"📋 Modelos disponíveis: {available_models[:5]}...")
        
except ImportError as e:
    logger.warning(f"⚠️ Scraper não instalado: {e}")
    logger.warning("Instale com: pip install git+https://github.com/henrique-coder/perplexity-webui-scraper")

# ============= CLIENTE PERPLEXITY =============

# ============= GERENCIADOR DE CLIENTES =============

class ClientManager:
    def __init__(self):
        self.default_client: Optional[Perplexity] = None
        self.location_clients: Dict[str, Perplexity] = {} # "lat,lon" -> client
        self.session_token = ""
        
    def init_default(self, token: str):
        self.session_token = token
        if SCRAPER_AVAILABLE and Perplexity and token and token != "seu_session_token_aqui":
            try:
                self.default_client = Perplexity(session_token=token)
                logger.info("✅ Cliente Default inicializado!")
            except Exception as e:
                logger.error(f"❌ Erro config default client: {e}")

    def get_client(self, lat: float = None, lon: float = None) -> Optional[Perplexity]:
        # Se não tem coords, usa default
        if lat is None or lon is None:
            return self.default_client
            
        # Cria chave única para coords (arredondando para agrupar proximidade)
        # 1 grau ~ 111km, 0.01 ~ 1.1km. Vamos usar 2 casas decimais (~1km precision)
        key = f"{lat:.2f},{lon:.2f}"
        
        if key in self.location_clients:
            return self.location_clients[key]
            
        # Cria novo cliente com coords
        if SCRAPER_AVAILABLE and Perplexity and self.session_token:
            try:
                # Tenta criar config com coords
                logger.info(f"📍 Criando novo cliente para local: {key}")
                from perplexity_webui_scraper import Coordinates, ClientConfig
                
                # Nota: Na versão atual da lib, Coordinates pode ser passado no construtor?
                # Vamos assumir que sim ou via config
                # ClientConfig é passado no create_conversation, mas precisamos do Client configurado?
                # A lib parece não expor Coordinates no __init__ do Perplexity, 
                # mas vamos tentar passar config se possível ou ignorar se não suportado.
                
                # Investigação mostrou que ClientConfig aceita coordinates.
                # E Perplexity aceita config?
                # Não, Perplexity(session_token). 
                # Mas create_conversation aceita config.
                # ENTÃO: Não precisamos de múltiplos clientes! O mesmo cliente pode criar conversas com configs diferentes?
                # Se a lib suporta isso, ótimo. Se não, (Coordinates geralmente vai no ClientConfig da conversa)
                # Vamos verificar o teste: ClientConfig(coordinates=coords). create_conversation(config).
                
                # Se Coordinates vai no ConversationConfig, então só precisamos de UM cliente!
                # E passamos Coordinates na hora de criar a conversa.
                
                return self.default_client
                
            except Exception as e:
                logger.warning(f"Erro ao criar cliente local: {e}")
                return self.default_client
                
        return self.default_client

client_manager = ClientManager()

# Inicializa cliente usando TokenManager (prioridade) ou fallback .env
if token_manager and token_manager.accounts:
    # Usa token do TokenManager
    current_token = token_manager.get_current_token()
    if current_token:
        client_manager.init_default(current_token)
        account_info = token_manager.get_account_info()
        logger.info(f"🔑 Usando token do TokenManager: {account_info.get('name', 'unknown')}")
elif PERPLEXITY_SESSION_TOKEN:
    # Fallback para variável de ambiente
    client_manager.init_default(PERPLEXITY_SESSION_TOKEN)
    logger.info("📌 Usando PERPLEXITY_SESSION_TOKEN do .env")

client = client_manager.default_client  # Fallback compatibility

# ============= STORAGE DE CONVERSAS ATIVAS =============
# Mantém uma conversa ativa por usuário para histórico nativo
active_conversations: Dict[str, Any] = {}
conversation_message_counts: Dict[str, int] = {}
conversation_messages: Dict[str, List[Dict[str, str]]] = {}  # Armazena mensagens para salvar
SAVE_TO_LIBRARY_ENABLED = False  # Default: False (Evita erro 403 na VPN)

# Diretório para salvar conversas
CONVERSATIONS_DIR = Path(os.getenv("CONVERSATIONS_DIR", "./data/conversations"))
CONVERSATIONS_DIR.mkdir(parents=True, exist_ok=True)
logger.info(f"📁 Diretório de conversas: {CONVERSATIONS_DIR.absolute()}")


def save_conversation(user_id: str) -> Optional[str]:
    """
    Salva a conversa atual do usuário em um arquivo JSON.
    Retorna o ID da conversa salva ou None se não houver conversa.
    """
    if user_id not in conversation_messages or not conversation_messages[user_id]:
        return None
    
    conv_id = str(uuid.uuid4())[:8]
    timestamp = datetime.now().isoformat()
    
    # Gera título a partir da primeira mensagem do usuário
    first_msg = ""
    for msg in conversation_messages[user_id]:
        if msg.get('role') == 'user':
            first_msg = msg.get('content', '')[:50]
            break
    
    title = first_msg + "..." if len(first_msg) >= 50 else first_msg
    if not title:
        title = f"Conversa {conv_id}"
    
    # Cria objeto da conversa
    conversation_data = {
        "id": conv_id,
        "user_id": user_id,
        "title": title,
        "created_at": timestamp,
        "message_count": len(conversation_messages[user_id]),
        "messages": conversation_messages[user_id]
    }
    
    # Cria pasta do usuário
    user_dir = CONVERSATIONS_DIR / user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    
    # Salva arquivo
    file_path = user_dir / f"{conv_id}.json"
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(conversation_data, f, ensure_ascii=False, indent=2)
    
    logger.info(f"[💾 SAVE] Conversa {conv_id} salva para user_id={user_id} ({len(conversation_messages[user_id])} msgs)")
    return conv_id


def list_saved_conversations(user_id: str) -> List[Dict[str, Any]]:
    """
    Lista todas as conversas salvas de um usuário.
    """
    user_dir = CONVERSATIONS_DIR / user_id
    if not user_dir.exists():
        return []
    
    conversations = []
    for file_path in sorted(user_dir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                conversations.append({
                    "id": data.get("id"),
                    "title": data.get("title"),
                    "created_at": data.get("created_at"),
                    "message_count": data.get("message_count", 0)
                })
        except Exception as e:
            logger.warning(f"Erro ao ler {file_path}: {e}")
    
    return conversations[:20]  # Limita a 20 conversas


def load_conversation(user_id: str, conv_id: str) -> Optional[Dict[str, Any]]:
    """
    Carrega uma conversa salva pelo ID.
    """
    file_path = CONVERSATIONS_DIR / user_id / f"{conv_id}.json"
    if not file_path.exists():
        return None
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Erro ao carregar conversa {conv_id}: {e}")
        return None


def delete_saved_conversation(user_id: str, conv_id: str) -> bool:
    """
    Deleta uma conversa salva.
    """
    file_path = CONVERSATIONS_DIR / user_id / f"{conv_id}.json"
    if file_path.exists():
        file_path.unlink()
        logger.info(f"[🗑️ DELETE] Conversa {conv_id} deletada")
        return True
    return False


def get_model_enum(model_id: str):
    """Converte ID do modelo para enum do scraper"""
    if not SCRAPER_AVAILABLE or Models is None:
        return None
    
    model_id = model_id.lower().replace("-", "_").replace(".", "_")
    
    # Mapeamento de IDs amigáveis para atributos do enum
    id_to_attr = {
        "best": "BEST",
        "sonar": "SONAR",
        "deep_research": "DEEP_RESEARCH",
        "gpt_5_2": "GPT_52",
        "gpt_5_2_thinking": "GPT_52_THINKING",
        "claude_4_5_sonnet": "CLAUDE_45_SONNET",
        "claude_4_5_sonnet_thinking": "CLAUDE_45_SONNET_THINKING",
        "claude_4_5_opus": "CLAUDE_45_OPUS",
        "claude_4_5_opus_thinking": "CLAUDE_45_OPUS_THINKING",
        "gemini_3_flash": "GEMINI_3_FLASH",
        "gemini_3_flash_thinking": "GEMINI_3_FLASH_THINKING",
        "gemini_3_pro_thinking": "GEMINI_3_PRO_THINKING",
        "grok_4_1": "GROK_41",
        "grok_4_1_thinking": "GROK_41_THINKING",
        "kimi_k2_5_thinking": "KIMI_K25_THINKING",
        "create_files": "CREATE_FILES_AND_APPS"
    }
    
    attr_name = id_to_attr.get(model_id, "BEST")
    
    # Tenta obter o atributo do enum
    if hasattr(Models, attr_name):
        return getattr(Models, attr_name)
    
    # Fallback para BEST
    return getattr(Models, "BEST", None)


def get_source_focus(focus_id: str):
    """Converte ID do focus para enum do scraper (se disponível)"""
    if not SCRAPER_AVAILABLE or SourceFocus is None:
        return None
    
    focus_id = focus_id.upper()
    
    # Tenta obter o atributo
    if hasattr(SourceFocus, focus_id):
        return getattr(SourceFocus, focus_id)
    
    # Fallback para WEB
    return getattr(SourceFocus, "WEB", None)


def get_citation_mode(mode: str):
    """Converte modo de citação para enum"""
    if not SCRAPER_AVAILABLE or CitationMode is None:
        return None
    
    mode = mode.upper()
    
    if hasattr(CitationMode, mode):
        return getattr(CitationMode, mode)
    
    return getattr(CitationMode, "MARKDOWN", None)


def get_time_range(range_id: str):
    """Converte ID de tempo para enum"""
    if not SCRAPER_AVAILABLE or TimeRange is None:
        return None
        
    range_id = range_id.upper()
    mapping = {
        "ALL": "ALL",
        "DAY": "TODAY",
        "WEEK": "LAST_WEEK", 
        "MONTH": "LAST_MONTH",
        "YEAR": "LAST_YEAR"
    }
    
    attr = mapping.get(range_id, "ALL")
    return getattr(TimeRange, attr, TimeRange.ALL)


# ============= ENDPOINTS =============

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "scraper_available": SCRAPER_AVAILABLE,
        "client_initialized": client is not None,
        "source_focus_available": SourceFocus is not None,
        "token_manager_active": token_manager is not None and len(token_manager.accounts) > 0,
        "active_conversations": len(active_conversations),
        "version": "2.4.0"
    })


@app.route('/tokens', methods=['GET'])
@app.route('/tokens/status', methods=['GET'])
def tokens_status():
    """Retorna status do TokenManager"""
    if token_manager is None:
        return jsonify({
            "active": False,
            "message": "TokenManager não disponível",
            "fallback": "PERPLEXITY_SESSION_TOKEN" if PERPLEXITY_SESSION_TOKEN else None
        })
    
    return jsonify(token_manager.get_status())


@app.route('/tokens/rotate', methods=['POST'])
def tokens_rotate():
    """Rotaciona para próximo token manualmente"""
    if token_manager is None or len(token_manager.accounts) < 2:
        return jsonify({"error": "Rotação não disponível"}), 400
    
    old_index = token_manager.current_index
    new_token = token_manager.get_next_token()
    
    # Reinicializa cliente com novo token
    if new_token:
        client_manager.init_default(new_token)
        global client
        client = client_manager.default_client
    
    return jsonify({
        "rotated": True,
        "old_index": old_index,
        "new_index": token_manager.current_index,
        "current_account": token_manager.get_account_info()
    })


@app.route('/tokens/validate', methods=['POST'])
def tokens_validate():
    """Valida o token atual"""
    if token_manager is None:
        return jsonify({"error": "TokenManager não disponível"}), 400
    
    is_valid = token_manager.validate_token()
    return jsonify({
        "valid": is_valid,
        "account": token_manager.get_account_info()
    })

# Valida o token atual
@app.route('/tokens/validate', methods=['GET'])
def tokens_validate_get(): # Renamed to avoid conflict with POST route
    if not token_manager:
        return jsonify({"error": "TokenManager não disponível"}), 503
    
    is_valid = token_manager.validate_token()
    return jsonify({
        "valid": is_valid,
        "token_preview": token_manager.get_current_token()[:15] + "..." if token_manager.get_current_token() else None
    })

# Renovação inteligente de token via browser_cookies.json
@app.route('/tokens/refresh', methods=['POST', 'GET'])
@limiter.limit("5 per minute")
def tokens_refresh():
    """Tenta renovar o token usando todos os cookies do browser"""
    if not token_manager:
        return jsonify({"error": "TokenManager não disponível"}), 503
    
    logger.info("🔄 Iniciando renovação de token via API...")
    result = token_manager.refresh_from_browser_cookies()
    
    if result["success"]:
        # Se renovou com sucesso, reinicializa o cliente default com o novo token
        new_token = token_manager.get_current_token()
        if new_token:
            client_manager.init_default(new_token)
            logger.info("✅ Cliente reinicializado com novo token!")
        
        return jsonify({
            "status": "success",
            "message": result["message"],
            "new_token_preview": result["new_token"][:15] + "..." if result["new_token"] else "N/A"
        })
    else:
        return jsonify({
            "status": "error",
            "message": result["message"]
        }), 400


@app.route('/search_stream', methods=['POST'])
@limiter.limit("20 per minute")
def search_stream():
    """
    Endpoint de busca com STREAMING (SSE).
    Retorna eventos: status, thinking, citation, chunk, done.
    """
    try:
        data = request.json or {}
        query = data.get('query')
        user_id = str(data.get('user_id', 'default'))
        model_id = data.get('model', 'best')
        focus_id = data.get('focus', 'web')
        time_range_id = data.get('time_range', 'all')
        
        if not query:
            return jsonify({"error": "Query required"}), 400

        if not SCRAPER_AVAILABLE or client is None:
             return jsonify({"error": "Service unavailable"}), 503

        # Configuração
        model_enum = get_model_enum(model_id)
        config_kwargs = {
            "model": model_enum,
             "language": "pt-BR",
             "save_to_library": SAVE_TO_LIBRARY_ENABLED
        }
        
        if SourceFocus is not None:
             source_focus_enum = get_source_focus(focus_id)
             if source_focus_enum:
                 config_kwargs["source_focus"] = [source_focus_enum]

        if TimeRange is not None:
            config_kwargs["time_range"] = get_time_range(time_range_id)

        config = ConversationConfig(**config_kwargs)
        
        # Reutiliza ou cria conversa
        if user_id in active_conversations:
             conversation = active_conversations[user_id]
             # Opcional: atualizar config da conversa existente se suportado
        else:
             conversation = client.create_conversation(config)
             active_conversations[user_id] = conversation

        def generate():
            # Retry loop para rotação de token
            max_retries = 3 if token_manager and len(token_manager.accounts) > 1 else 1
            
            for attempt in range(max_retries):
                try:
                    # Recupera (ou recria) conversa dentro do loop para garantir cliente atualizado
                    global client
                    if user_id in active_conversations:
                        conversation = active_conversations[user_id]
                    else:
                        conversation = client.create_conversation(config)
                        active_conversations[user_id] = conversation

                    # Evento inicial
                    yield f"data: {json.dumps({'status': 'Iniciando busca...'})}\n\n"
                    
                    full_response = ""
                    citations = []
                    
                    conversation.ask(query, stream=True)
                    
                    last_thinking = ""
                    
                    for response_step in conversation:
                        # Extrai dados do passo
                        raw = response_step.raw_data
                        
                        # 1. Status/Thinking
                        thinking = None
                        if raw:
                            thinking = raw.get('thinking') or raw.get('reasoning')
                            # Se tiver steps (Sonar)
                            if not thinking and 'steps' in raw:
                                steps = raw.get('steps', [])
                                if steps:
                                    thinking = "\\n".join([s.get('content','') for s in steps if s.get('type')=='thinking'])

                        if thinking and thinking != last_thinking:
                            yield f"data: {json.dumps({'thinking': thinking})}\n\n"
                            last_thinking = thinking
                        
                        # 2. Citações (sources)
                        current_results = getattr(response_step, 'search_results', [])
                        if len(current_results) > len(citations):
                            for i in range(len(citations), len(current_results)):
                                src = current_results[i]
                                cit_data = {
                                    'title': getattr(src, 'title', 'Fonte'),
                                    'url': getattr(src, 'url', '')
                                }
                                yield f"data: {json.dumps({'citation': cit_data})}\n\n"
                            citations = current_results
                        
                        # 3. Chunk de Texto
                        current_answer = response_step.answer or ""
                        if len(current_answer) > len(full_response):
                            delta = current_answer[len(full_response):]
                            if delta:
                                yield f"data: {json.dumps({'chunk': delta})}\n\n"
                            full_response = current_answer
                            
                        # 4. Debug Canvas
                        if 'canvas' in raw:
                            logger.info(f"🎨 Canvas detected: {raw['canvas'].keys()}")
                            # TODO: Emit file event

                        # 5. Clarifying Questions
                        # Alguns modelos retornam 'clarifying_question' boolean ou str
                        # Ou 'text' é uma pergunta.
                        # Vamos verificar se há flag explícita
                        if raw.get('clarifying_question'):
                            yield f"data: {json.dumps({'clarifying_question': True})}\n\n"
                            
                    # Se chegou aqui, sucesso total
                    # Final Payload
                    final_payload = {
                        "done": True,
                        "answer": full_response,
                        "citations": [{'title': getattr(c, 'title'), 'url': getattr(c, 'url')} for c in citations],
                        "conversation_id": user_id,
                        "backend_uuid": getattr(conversation, 'backend_uuid', None)
                    }
                    yield f"data: {json.dumps(final_payload)}\n\n"
                    
                    # Salva histórico
                    if user_id not in conversation_messages:
                        conversation_messages[user_id] = []
                    conversation_messages[user_id].append({"role": "user", "content": query})
                    conversation_messages[user_id].append({"role": "assistant", "content": full_response})
                    conversation_message_counts[user_id] = conversation_message_counts.get(user_id, 0) + 1
                    
                    break # Break retry loop
                    
                except Exception as e:
                    err_str = str(e).lower()
                    is_auth = '401' in err_str or '403' in err_str or 'unauthorized' in err_str or 'forbidden' in err_str
                    
                    if is_auth and attempt < max_retries - 1:
                        logger.warning(f"⚠️ Erro Auth (Stream). Rotacionando... ({attempt+1}/{max_retries})")
                        yield f"data: {json.dumps({'status': '🔄 Token expirado. Trocando conta...'})}\n\n"
                        
                        # Rotação
                        new_token = token_manager.get_next_token()
                        if new_token:
                            client_manager.init_default(new_token)
                            client = client_manager.default_client
                            # Força recriação da conversa na próxima iteração
                            active_conversations.pop(user_id, None)
                            continue
                            
                    logger.error(f"Erro stream final: {e}")
                    yield f"data: {json.dumps({'error': str(e)})}\n\n"
                    break

        return app.response_class(generate(), mimetype='text/event-stream')

    except Exception as e:
        logger.error(f"Erro /search_stream: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/models', methods=['GET'])
def list_models():
    """Lista modelos e focus modes disponíveis"""
    return jsonify({
        "models": [
            {"id": "best", "name": "🎯 Best (Auto)", "description": "Seleciona automaticamente o melhor modelo"},
            {"id": "sonar", "name": "⚡ Sonar", "description": "Modelo mais recente da Perplexity"},
            {"id": "deep-research", "name": "📊 Deep Research", "description": "Relatórios detalhados com mais fontes"},
            {"id": "gpt-5.2", "name": "🧠 GPT-5.2", "description": "Modelo mais recente da OpenAI"},
            {"id": "claude-4.5-sonnet", "name": "🎭 Claude 4.5 Sonnet", "description": "Modelo rápido da Anthropic"},
            {"id": "claude-4.5-opus", "name": "🎭✨ Claude 4.5 Opus", "description": "Modelo avançado da Anthropic"},
            {"id": "gemini-3-flash", "name": "💎 Gemini 3 Flash", "description": "Modelo rápido do Google"},
            {"id": "grok-4.1", "name": "🚀 Grok 4.1", "description": "Modelo mais recente da xAI"},
            {"id": "kimi-k2.5-thinking", "name": "🌙 Kimi K2.5 Thinking", "description": "Modelo da Moonshot AI"}
        ],
        "focus_modes": [
            {"id": "web", "name": "🌐 Web", "description": "Busca geral na web"},
            {"id": "academic", "name": "🎓 Academic", "description": "Papers científicos e acadêmicos"},
            {"id": "youtube", "name": "🎥 YouTube", "description": "Busca em vídeos do YouTube"},
            {"id": "reddit", "name": "💬 Reddit", "description": "Discussões do Reddit"},
            {"id": "wolfram", "name": "🧮 Wolfram", "description": "Cálculos e matemática avançada"}
        ],
        "citation_modes": [
            {"id": "default", "description": "texto[1] - Citações numeradas"},
            {"id": "markdown", "description": "texto[1](url) - Citações com links"},
            {"id": "clean", "description": "texto - Sem citações"}
        ]
    })


@app.route('/search', methods=['POST'])
@limiter.limit("20 per minute")
def search():
    """
    Endpoint principal de busca COM HISTÓRICO NATIVO.
    
    Payload:
    {
        "query": "string",
        "user_id": "string (identificador do usuário)",
        "model": "best|sonar|deep-research|gpt-5.2|claude-4.5-sonnet|...",
        "focus": "web|academic|youtube|reddit|wolfram",
        "time_range": "all|day|week|month|year",
        "citation_mode": "default|markdown|clean"
    }
    
    O histórico é mantido automaticamente por user_id.
    Use POST /clear para limpar o histórico de um usuário.
    """
    try:
        # Suporte Híbrido: JSON ou Multipart/Form
        files_to_upload = []
        
        data = None
        if request.is_json:
            data = request.json
        else:
            data = request.form
            # Processa upload de arquivos
            if request.files:
                try:
                    upload_dir = Path(tempfile.gettempdir()) / "pplx_uploads"
                    upload_dir.mkdir(exist_ok=True)
                    
                    for key in request.files:
                        file = request.files[key]
                        if file.filename:
                            safe_name = f"{uuid.uuid4().hex[:8]}_{file.filename}"
                            tmp_path = upload_dir / safe_name
                            file.save(tmp_path)
                            files_to_upload.append(str(tmp_path))
                            logger.info(f"[UPLOAD] Arquivo salvo: {tmp_path}")
                except Exception as e:
                    logger.error(f"Erro ao salvar upload: {e}")

        if not data or 'query' not in data:
            return jsonify({"error": "Campo 'query' é obrigatório"}), 400
        
        query = data['query']
        user_id = str(data.get('user_id', 'default'))
        model_id = data.get('model', 'best')
        focus_id = data.get('focus', 'web')
        time_range_id = data.get('time_range', 'all')
        citation_mode = data.get('citation_mode', 'markdown')
        
        # Verifica se o scraper está disponível
        if not SCRAPER_AVAILABLE:
            return jsonify({
                "error": "Scraper não instalado",
                "message": "Execute: pip install git+https://github.com/henrique-coder/perplexity-webui-scraper"
            }), 503
        
        # Verifica se o cliente foi inicializado
        if client is None:
            return jsonify({
                "error": "Cliente não inicializado",
                "message": "Verifique o PERPLEXITY_SESSION_TOKEN no arquivo .env"
            }), 503
        
        # Obtém enums
        model_enum = get_model_enum(model_id)
        citation_enum = get_citation_mode(citation_mode)
        
        # Verifica se já existe conversa ativa para este usuário
        conversation = active_conversations.get(user_id)
        is_new_conversation = False
        
        if conversation is None:
            # Cria nova conversa para o usuário
            # Configuração da conversa
            config_kwargs = {
                "model": model_enum,
                "citation_mode": citation_enum,
                "language": "pt-BR",
                "save_to_library": SAVE_TO_LIBRARY_ENABLED
            }
            
            # Adiciona time_range se disponível
            if TimeRange is not None:
                config_kwargs["time_range"] = get_time_range(time_range_id)
            
            # Adiciona coordenadas se fornecidas
            lat = data.get('lat')
            lon = data.get('lon')
            if lat is not None and lon is not None:
                try:
                    from perplexity_webui_scraper import Coordinates
                    config_kwargs["coordinates"] = Coordinates(
                        latitude=float(lat), 
                        longitude=float(lon), 
                        accuracy=20.0
                    )
                    logger.info(f"📍 Configurando busca local: {lat}, {lon}")
                except Exception as e:
                    logger.warning(f"Erro ao configurar coords: {e}")

            # Adiciona source_focus apenas se disponível
            if SourceFocus is not None:
                source_focus_enum = get_source_focus(focus_id)
                if source_focus_enum:
                    config_kwargs["source_focus"] = [source_focus_enum]
            
            config = ConversationConfig(**config_kwargs)
            conversation = client.create_conversation(config)
            active_conversations[user_id] = conversation
            
            # Se já tem mensagens em memória (ex: restauradas do histórico), injeta na nova conversa
            if user_id in conversation_messages and conversation_messages[user_id]:
                logger.info(f"[SEARCH] Restaurando {len(conversation_messages[user_id])} mensagens para user_id={user_id}")
                try:
                    # Tenta reinjetar histórico
                    msgs = conversation_messages[user_id]
                    for i in range(0, len(msgs) - 1, 2):
                        user_msg = msgs[i]
                        asst_msg = msgs[i+1] if i+1 < len(msgs) else None
                        
                        if user_msg.get('role') == 'user' and asst_msg and asst_msg.get('role') == 'assistant':
                             if hasattr(conversation, 'add_message'):
                                conversation.add_message(user_msg['content'], role='user')
                                conversation.add_message(asst_msg['content'], role='assistant')
                except Exception as e:
                    logger.warning(f"Erro ao restaurar histórico nativo: {e}")
            else:
                conversation_messages[user_id] = []  # Inicia limpo se não tinha nada
                
            conversation_message_counts[user_id] = len(conversation_messages.get(user_id, []))
            is_new_conversation = True
            logger.info(f"[SEARCH] Nova conversa iniciada para user_id={user_id}")
        
        # Incrementa contador de mensagens
        conversation_message_counts[user_id] = conversation_message_counts.get(user_id, 0) + 1
        msg_count = conversation_message_counts[user_id]
        
        logger.info(f"[SEARCH] Query: {query[:50]}... | User: {user_id} | Msg #{msg_count} | Model: {model_id}")
        
        # Faz a pergunta NA MESMA CONVERSA (histórico nativo!)
        if files_to_upload:
            logger.info(f"[SEARCH] Enviando {len(files_to_upload)} arquivos para Perplexity...")
            conversation.ask(query, files=files_to_upload)
        else:
            conversation.ask(query)
        
        # Extrai resposta
        answer = conversation.answer if hasattr(conversation, 'answer') else str(conversation)
        
        # Salva mensagens para persistência
        if user_id not in conversation_messages:
            conversation_messages[user_id] = []
        conversation_messages[user_id].append({"role": "user", "content": query})
        conversation_messages[user_id].append({"role": "assistant", "content": answer})
        
        # Extrai thinking (raciocínio) se disponível - para modelos THINKING
        thinking = None
        raw_data = getattr(conversation, 'raw_data', {}) if hasattr(conversation, 'raw_data') else {}
        
        # Tenta extrair thinking de vários lugares possíveis
        if raw_data:
            thinking = raw_data.get('thinking') or raw_data.get('reasoning') or raw_data.get('thought_process')
            
            # Alguns modelos colocam em 'steps' ou 'chain_of_thought'
            if not thinking:
                steps = raw_data.get('steps', [])
                if steps and isinstance(steps, list):
                    thinking_steps = [s.get('content', '') for s in steps if s.get('type') in ['thinking', 'reasoning']]
                    if thinking_steps:
                        thinking = '\n'.join(thinking_steps)
            
            # Claude coloca em 'internal_reasoning' às vezes
            if not thinking:
                thinking = raw_data.get('internal_reasoning')
        
        # Extrai citações se disponíveis
        citations = []
        search_results = getattr(conversation, 'search_results', []) if hasattr(conversation, 'search_results') else []
        if search_results:
            for src in search_results:
                citations.append({
                    "title": getattr(src, 'title', 'Fonte'),
                    "url": getattr(src, 'url', ''),
                    "snippet": getattr(src, 'snippet', '')
                })
        
        # Fallback para sources (versões antigas)
        if not citations and hasattr(conversation, 'sources') and conversation.sources:
            for src in conversation.sources:
                citations.append({
                    "title": getattr(src, 'title', 'Fonte'),
                    "url": getattr(src, 'url', ''),
                    "snippet": getattr(src, 'snippet', '')
                })
        
        response = {
            "status": "success",
            "answer": answer,
            "thinking": thinking,
            "model_used": model_id,
            "focus_mode": focus_id,
            "time_range": time_range_id,
            "citations": citations,
            "has_thinking": thinking is not None,
            "conversation_info": {
                "id": user_id,
                "uuid": getattr(conversation, 'backend_uuid', None),
                "model": model_id,
                "message_count": conversation_message_counts.get(user_id, 0)
            }
        }

        # Limpeza de arquivos temporários
        for fpath in files_to_upload:
            try:
                os.remove(fpath)
            except Exception as e:
                logger.warning(f"Erro ao remover temp {fpath}: {e}")
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Erro em /search: {e}")
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


@app.route('/last_response', methods=['GET'])
def get_last_response():
    """Retorna a última resposta gerada para o usuário (Retry)"""
    user_id = request.args.get('user_id', 'default')
    
    if user_id not in conversation_messages:
        return jsonify({"error": "No history found"}), 404
        
    messages = conversation_messages[user_id]
    if not messages:
        return jsonify({"error": "Empty history"}), 404
        
    # Procura a última msg do assistant de trás pra frente
    for msg in reversed(messages):
        if msg['role'] == 'assistant':
            return jsonify({
                "answer": msg['content'],
            })
            
    return jsonify({"error": "No assistant message found"}), 404


@app.route('/clear', methods=['POST'])
def clear_conversation():
    """
    Limpa o histórico de conversa de um usuário.
    
    Payload:
    {
        "user_id": "string"
    }
    """
    try:
        data = request.json or {}
        user_id = str(data.get('user_id', 'default'))
        
        saved_id = None
        msg_count = 0
        
        # SALVA a conversa antes de limpar!
        if user_id in conversation_messages and conversation_messages[user_id]:
            saved_id = save_conversation(user_id)
            msg_count = len(conversation_messages[user_id]) // 2  # Pares de msgs
        
        # Limpa da memória
        if user_id in active_conversations:
            del active_conversations[user_id]
        if user_id in conversation_message_counts:
            del conversation_message_counts[user_id]
        if user_id in conversation_messages:
            del conversation_messages[user_id]
        
        if saved_id:
            logger.info(f"[CLEAR] Conversa salva como {saved_id} e limpa para user_id={user_id}")
            return jsonify({
                "success": True,
                "message": f"Conversa salva ({msg_count} mensagens) e limpa",
                "user_id": user_id,
                "saved_conversation_id": saved_id
            })
        else:
            return jsonify({
                "success": True,
                "message": "Nenhum histórico encontrado",
                "user_id": user_id
            })
            
    except Exception as e:
        logger.error(f"Erro em /clear: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/conversation-status', methods=['GET'])
def conversation_status():
    """
    Retorna status das conversas ativas.
    Query param: ?user_id=xxx para ver de um usuário específico
    """
    user_id = request.args.get('user_id')
    
    if user_id:
        return jsonify({
            "user_id": user_id,
            "has_active_conversation": user_id in active_conversations,
            "message_count": conversation_message_counts.get(user_id, 0)
        })
    
    return jsonify({
        "total_active_conversations": len(active_conversations),
        "conversations": {
            uid: {"message_count": conversation_message_counts.get(uid, 0)}
            for uid in active_conversations.keys()
        }
    })


@app.route('/history/list', methods=['GET'])
def history_list():
    """
    Lista conversas salvas de um usuário.
    Query param: ?user_id=xxx
    """
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"error": "user_id required"}), 400
    
    conversations = list_saved_conversations(user_id)
    return jsonify({"conversations": conversations})


@app.route('/history/load', methods=['POST'])
def history_load():
    """
    Carrega uma conversa salva.
    Payload: { "user_id": "xxx", "conversation_id": "xxx" }
    """
    data = request.json or {}
    user_id = data.get('user_id')
    conv_id = data.get('conversation_id')
    
    if not user_id or not conv_id:
        return jsonify({"error": "user_id and conversation_id required"}), 400
        
    conversation_data = load_conversation(user_id, conv_id)
    if not conversation_data:
        return jsonify({"error": "Conversation not found"}), 404
    
    # Restaura estado em memória
    messages = conversation_data.get('messages', [])
    conversation_messages[user_id] = messages
    conversation_message_counts[user_id] = len(messages)
    
    # Remove conversa ativa anterior para forçar criação de nova com nosso histórico
    if user_id in active_conversations:
        del active_conversations[user_id]
    
    logger.info(f"[LOAD] Conversa {conv_id} carregada para user_id={user_id} ({len(messages)} msgs)")
    
    return jsonify({
        "success": True, 
        "conversation": conversation_data,
        "message": "Conversa carregada! Próxima mensagem continuará este contexto."
    })


@app.route('/history/delete', methods=['POST'])
def history_delete():
    """
    Deleta uma conversa salva.
    Payload: { "user_id": "xxx", "conversation_id": "xxx" }
    """
    data = request.json or {}
    user_id = data.get('user_id')
    conv_id = data.get('conversation_id')
    
    if not user_id or not conv_id:
        return jsonify({"error": "user_id and conversation_id required"}), 400
        
    success = delete_saved_conversation(user_id, conv_id)
    return jsonify({"success": success})


@app.route('/config/library', methods=['GET', 'POST'])
def config_library():
    """
    GET: Retorna estado atual do save_to_library
    POST: Inverte estado (toggle) e retorna novo
    """
    global SAVE_TO_LIBRARY_ENABLED
    
    if request.method == 'POST':
        SAVE_TO_LIBRARY_ENABLED = not SAVE_TO_LIBRARY_ENABLED
        logger.info(f"[CONFIG] Save to Library alterado para: {SAVE_TO_LIBRARY_ENABLED}")
        
    return jsonify({
        "enabled": SAVE_TO_LIBRARY_ENABLED,
        "message": "Save to Library ATIVADO" if SAVE_TO_LIBRARY_ENABLED else "Save to Library DESATIVADO"
    })


@app.route('/config/token', methods=['POST'])
def config_token():
    """
    Atualiza o token de sessão do Perplexity em tempo de execução.
    Payload: {"token": "seu_token_aqui"}
    """
    global client, PERPLEXITY_SESSION_TOKEN
    
    data = request.json or {}
    new_token = data.get('token')
    
    if not new_token:
        return jsonify({"error": "Token required"}), 400
        
    try:
        # Reinicializa o cliente
        if SCRAPER_AVAILABLE and Perplexity:
            PERPLEXITY_SESSION_TOKEN = new_token
            client = Perplexity(session_token=new_token)
            logger.info("✅ Cliente Perplexity reinicializado com NOVO token!")
            return jsonify({"success": True, "message": "Token atualizado e cliente reinicializado!"})
        else:
            return jsonify({"error": "Scraper not available"}), 503
            
    except Exception as e:
        logger.error(f"Erro ao atualizar token: {e}")
        return jsonify({"error": str(e)}), 500





@app.route('/vision', methods=['POST'])
@limiter.limit("10 per minute")
def vision():
    """
    Endpoint para análise de imagens/arquivos.
    
    Payload:
    {
        "query": "string",
        "image_base64": "string (base64 encoded)",
        "model": "best" (recomendado)
    }
    """
    try:
        data = request.json
        
        if not data or 'query' not in data or 'image_base64' not in data:
            return jsonify({"error": "Campos 'query' e 'image_base64' são obrigatórios"}), 400
        
        query = data['query']
        image_b64 = data['image_base64']
        model_id = data.get('model', 'best')
        
        logger.info(f"[VISION] Query: {query[:50]}... | Model: {model_id}")
        
        # Verifica scraper
        if not SCRAPER_AVAILABLE or client is None:
            return jsonify({
                "error": "Scraper não disponível",
                "message": "Verifique a instalação e o session token"
            }), 503
        
        # Salva imagem temporariamente
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            tmp.write(base64.b64decode(image_b64))
            tmp_path = tmp.name
        
        try:
            # Cria configuração
            model_enum = get_model_enum(model_id)
            config = ConversationConfig(
                model=model_enum,
                language="pt-BR"
            )
            
            # Cria conversa com arquivo
            conversation = client.create_conversation(config)
            conversation.ask(query, files=[tmp_path])
            
            answer = conversation.answer if hasattr(conversation, 'answer') else str(conversation)
            
            return jsonify({"answer": answer})
            
        finally:
            # Remove arquivo temporário
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        
    except Exception as e:
        logger.error(f"Erro em /vision: {e}")
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


@app.route('/diagnostics', methods=['GET'])
def diagnostics():
    """
    Diagnóstico completo do sistema.
    Checa:
    1. IP Público (para validar VPN)
    2. Autenticação Perplexity (tenta conectar)
    """
    result = {
        "mcp_status": "online",
        "public_ip": "unknown",
        "perplexity_auth": "unknown",
        "auth_error": None
    }
    
    # 1. Checa IP Público
    try:
        import urllib.request
        try:
            with urllib.request.urlopen('https://api.ipify.org', timeout=5) as response:
                result['public_ip'] = response.read().decode('utf-8')
        except:
             # Fallback
             with urllib.request.urlopen('https://ifconfig.me/ip', timeout=5) as response:
                result['public_ip'] = response.read().decode('utf-8').strip()
             
    except Exception as e:
        result['public_ip'] = f"Error: {str(e)}"
        
    # 2. Checa Autenticação Perplexity
    try:
        if SCRAPER_AVAILABLE and client is not None:
             # Verifica apenas se o cliente existe (o check anterior de .session falhava)
             result['perplexity_auth'] = "configured"
        else:
            result['perplexity_auth'] = "scraper_unavailable"

    except Exception as e:
        result['error'] = str(e)
        
    return jsonify(result)


# ============= ERROR HANDLERS =============

@app.errorhandler(429)
def ratelimit_handler(e):
    """Handler para rate limit excedido"""
    return jsonify({
        "error": "Rate limit excedido. Aguarde um momento.",
        "retry_after": e.description
    }), 429


@app.errorhandler(500)
def internal_error(e):
    """Handler para erros internos"""
    logger.error(f"Erro interno: {e}")
    return jsonify({"error": "Erro interno do servidor"}), 500


# ============= MAIN =============

if __name__ == '__main__':
    logger.info(f"🚀 MCP Server iniciando na porta {MCP_PORT}")
    logger.info(f"📦 Scraper disponível: {SCRAPER_AVAILABLE}")
    logger.info(f"🔑 Cliente inicializado: {client is not None}")
    logger.info(f"📍 SourceFocus disponível: {SourceFocus is not None}")
    
    if not SCRAPER_AVAILABLE:
        logger.warning("⚠️ Instale o scraper: pip install git+https://github.com/henrique-coder/perplexity-webui-scraper")
    
    if client is None and SCRAPER_AVAILABLE:
        logger.warning("⚠️ Configure o PERPLEXITY_SESSION_TOKEN no arquivo .env")
    
    app.run(
        host='0.0.0.0',
        port=MCP_PORT,
        debug=os.getenv('FLASK_ENV') != 'production'
    )
