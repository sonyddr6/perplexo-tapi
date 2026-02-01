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
    CitationMode = _CitationMode
    
    # Tenta importar SourceFocus (pode não existir em todas as versões)
    try:
        from perplexity_webui_scraper import SourceFocus as _SourceFocus
        SourceFocus = _SourceFocus
    except ImportError:
        logger.warning("⚠️ SourceFocus não disponível nesta versão do scraper")
        SourceFocus = None
    
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

client = None
if SCRAPER_AVAILABLE and Perplexity and PERPLEXITY_SESSION_TOKEN and PERPLEXITY_SESSION_TOKEN != "seu_session_token_aqui":
    try:
        client = Perplexity(session_token=PERPLEXITY_SESSION_TOKEN)
        logger.info("✅ Cliente Perplexity inicializado com sucesso!")
    except Exception as e:
        logger.error(f"❌ Erro ao inicializar cliente: {e}")
        client = None


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


# ============= ENDPOINTS =============

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "scraper_available": SCRAPER_AVAILABLE,
        "client_initialized": client is not None,
        "source_focus_available": SourceFocus is not None,
        "version": "2.1.0"
    })


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
    Endpoint principal de busca.
    
    Payload:
    {
        "query": "string",
        "model": "best|sonar|deep-research|gpt-5.2|claude-4.5-sonnet|...",
        "focus": "web|academic|youtube|reddit|wolfram",
        "citation_mode": "default|markdown|clean"
    }
    """
    try:
        data = request.json
        
        if not data or 'query' not in data:
            return jsonify({"error": "Campo 'query' é obrigatório"}), 400
        
        query = data['query']
        model_id = data.get('model', 'best')
        focus_id = data.get('focus', 'web')
        citation_mode = data.get('citation_mode', 'markdown')
        
        logger.info(f"[SEARCH] Query: {query[:50]}... | Model: {model_id} | Focus: {focus_id}")
        
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
        
        # Cria configuração da conversa (sem source_focus se não disponível)
        config_kwargs = {
            "model": model_enum,
            "citation_mode": citation_enum,
            "language": "pt-BR"
        }
        
        # Adiciona source_focus apenas se disponível
        if SourceFocus is not None:
            source_focus_enum = get_source_focus(focus_id)
            if source_focus_enum:
                config_kwargs["source_focus"] = [source_focus_enum]
        
        config = ConversationConfig(**config_kwargs)
        
        # Cria conversa e faz a pergunta
        conversation = client.create_conversation(config)
        conversation.ask(query)
        
        # Extrai resposta
        answer = conversation.answer if hasattr(conversation, 'answer') else str(conversation)
        
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
            "answer": answer,
            "thinking": thinking,  # Novo campo para raciocínio
            "model_used": model_id,
            "focus_mode": focus_id,
            "citations": citations,
            "has_thinking": thinking is not None
        }
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Erro em /search: {e}")
        logger.error(traceback.format_exc())
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
