# Inworld AI TTS - Módulo para Perplexo
# Extrai áudio via API Inworld (integrado)
# Com auto-renovação de token via Firebase

import requests
import json
import base64
import time
import random
import logging
import os
from functools import wraps
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# ============================================================
# CONFIGURAÇÕES
# ============================================================

WORKSPACE_ID = os.getenv("WORKSPACE_ID", "")
BASE_URL = "https://api.inworld.ai"
FIREBASE_API_KEY = os.getenv("FIREBASE_API_KEY", "")
FIREBASE_REFRESH_TOKEN = os.getenv("FIREBASE_REFRESH_TOKEN", "")
TTS_VOICE_ID = os.getenv("TTS_VOICE_ID", "")

# Token em memória (será renovado automaticamente)
_current_token = os.getenv("INWORLD_TOKEN", "")
_token_expiry = None

# Limite de caracteres
MAX_CARACTERES = 2000

# User-Agents para rotação
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/144.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/144.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/144.0.0.0 Safari/537.36"
]

# Verifica se TTS está disponível
TTS_AVAILABLE = bool(_current_token) or bool(FIREBASE_REFRESH_TOKEN)

if not TTS_AVAILABLE:
    logger.warning("⚠️ TTS desativado - configure INWORLD_TOKEN ou FIREBASE_REFRESH_TOKEN")

# ============================================================
# AUTO-RENOVAÇÃO DE TOKEN
# ============================================================

def refresh_firebase_token():
    """Renova accessToken usando refreshToken do Firebase"""
    if not FIREBASE_REFRESH_TOKEN:
        logger.error("❌ FIREBASE_REFRESH_TOKEN não configurado")
        return None
    
    logger.info("🔄 Renovando token Firebase...")
    
    url = f"https://securetoken.googleapis.com/v1/token?key={FIREBASE_API_KEY}"
    payload = {"grant_type": "refresh_token", "refresh_token": FIREBASE_REFRESH_TOKEN}
    
    try:
        response = requests.post(url, data=payload, timeout=30)
        if response.status_code == 200:
            data = response.json()
            access_token = data.get("id_token")
            logger.info("✅ Firebase token renovado!")
            return access_token
        else:
            logger.error(f"❌ Erro Firebase: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"❌ Erro ao renovar Firebase: {e}")
        return None


def generate_tts_token(firebase_token):
    """Gera token TTS usando endpoint do portal Inworld"""
    global _token_expiry
    logger.info("🔄 Gerando token TTS...")
    
    url = f"https://platform.inworld.ai/ai/inworld/portal/v1alpha/workspaces/{WORKSPACE_ID}/token:generate"
    
    headers = {
        "authorization": f"Bearer {firebase_token}",
        "content-type": "text/plain;charset=UTF-8",
        "grpc-metadata-x-authorization-bearer-type": "firebase",
        "origin": "https://platform.inworld.ai",
        "referer": f"https://platform.inworld.ai/v2/workspaces/{WORKSPACE_ID}/tts-playground",
        "user-agent": random.choice(USER_AGENTS)
    }
    
    try:
        response = requests.post(url, headers=headers, data=json.dumps({}), timeout=30)
        if response.status_code == 200:
            data = response.json()
            tts_token = data.get("token")
            expiration = data.get("expirationTime")
            
            # Parseia e armazena o tempo de expiração
            if expiration:
                _token_expiry = datetime.fromisoformat(expiration.replace('Z', '+00:00'))
            
            logger.info(f"✅ Token TTS gerado! Expira: {expiration}")
            return tts_token
        else:
            logger.error(f"❌ Erro ao gerar TTS token: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"❌ Erro ao gerar TTS token: {e}")
        return None


def auto_renew_token():
    """Renova token automaticamente usando Firebase"""
    global _current_token, TTS_AVAILABLE
    
    # Passo 1: Renovar Firebase token
    firebase_token = refresh_firebase_token()
    if not firebase_token:
        return False
    
    # Passo 2: Gerar TTS token
    tts_token = generate_tts_token(firebase_token)
    if not tts_token:
        return False
    
    # Atualiza token em memória
    _current_token = tts_token
    TTS_AVAILABLE = True
    logger.info("🔑 Token TTS atualizado com sucesso!")
    return True


def get_token():
    """Retorna token atual, renovando se necessário"""
    global _current_token, _token_expiry
    
    # Verifica se token está próximo de expirar (5 minutos antes)
    if _token_expiry:
        now = datetime.now(_token_expiry.tzinfo) if _token_expiry.tzinfo else datetime.now()
        time_until_expiry = _token_expiry - now
        
        # Renova se faltar menos de 5 minutos para expirar
        if time_until_expiry.total_seconds() < 300:
            logger.info("🔄 Token próximo de expirar, renovando...")
            if FIREBASE_REFRESH_TOKEN:
                auto_renew_token()
    
    if not _current_token and FIREBASE_REFRESH_TOKEN:
        auto_renew_token()
    
    return _current_token

# ============================================================
# HEADERS
# ============================================================

def get_headers():
    """Gera headers com User-Agent rotativo"""
    return {
        "Authorization": f"Bearer {get_token()}",
        "Content-Type": "application/json",
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8",
        "Origin": "https://platform.inworld.ai",
        "Referer": "https://platform.inworld.ai/"
    }

# ============================================================
# RETRY DECORATOR COM AUTO-RENEW
# ============================================================

def retry_com_backoff(max_tentativas=3, backoff_factor=2):
    """Retry automático com exponential backoff e auto-renovação"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            ultima_excecao = None
            
            for tentativa in range(max_tentativas):
                try:
                    return func(*args, **kwargs)
                except requests.exceptions.HTTPError as e:
                    ultima_excecao = e
                    status = e.response.status_code
                    
                    if status == 401:
                        logger.warning("🔄 Token expirado - tentando renovar...")
                        if auto_renew_token():
                            logger.info("✅ Token renovado - retentando...")
                            continue  # Retenta com novo token
                        else:
                            logger.error("❌ Falha ao renovar token")
                            return None
                    elif status == 429:
                        tempo = backoff_factor ** tentativa * 5
                        logger.warning(f"⏳ Rate limit. Aguardando {tempo}s...")
                        time.sleep(tempo)
                    else:
                        logger.warning(f"Erro HTTP {status}. Tentativa {tentativa+1}/{max_tentativas}")
                        time.sleep(backoff_factor ** tentativa)
                except Exception as e:
                    ultima_excecao = e
                    logger.warning(f"Erro TTS: {e}. Tentativa {tentativa+1}/{max_tentativas}")
                    time.sleep(backoff_factor ** tentativa)
            
            logger.error(f"❌ TTS falhou após {max_tentativas} tentativas: {ultima_excecao}")
            return None
        return wrapper
    return decorator

# ============================================================
# FUNÇÃO PRINCIPAL
# ============================================================

@retry_com_backoff(max_tentativas=3)
def generate_audio_bytes(text: str, voice_id: str = None) -> bytes:
    """
    Gera áudio MP3 a partir do texto.
    
    Args:
        text: Texto para converter em áudio (máx 2000 chars)
        voice_id: ID da voz (usa TTS_VOICE_ID se não especificado)
    
    Returns:
        bytes do arquivo MP3 ou None se falhar
    """
    if not TTS_AVAILABLE:
        logger.error("TTS não disponível - configure INWORLD_TOKEN ou FIREBASE_REFRESH_TOKEN")
        return None
    
    voice_id = voice_id or TTS_VOICE_ID
    
    # Trunca se muito longo
    if len(text) > MAX_CARACTERES:
        logger.warning(f"Texto truncado: {len(text)} -> {MAX_CARACTERES} chars")
        text = text[:MAX_CARACTERES]
        # Tenta cortar na última frase completa ou palavra
        last_period = text.rfind('.')
        last_space = text.rfind(' ')
        if last_period > MAX_CARACTERES * 0.7:
            text = text[:last_period + 1]
        elif last_space > MAX_CARACTERES * 0.7:
            text = text[:last_space]
    
    url = f"{BASE_URL}/tts/v1/workspaces/{WORKSPACE_ID}/tts:synthesize"
    
    payload = {
        "text": text,
        "voice_id": voice_id,
        "model_id": "inworld-tts-1.5-max",
        "audio_config": {
            "audio_encoding": "MP3",
            "speaking_rate": 1.0,
            "sample_rate_hertz": 48000
        },
        "temperature": 1.0
    }
    
    logger.info(f"🎙️ Gerando TTS: '{text[:50]}...'")
    
    response = requests.post(url, headers=get_headers(), json=payload, timeout=60)
    response.raise_for_status()
    
    content_type = response.headers.get('Content-Type', '')
    
    if 'application/json' in content_type:
        data = response.json()
        if 'audioContent' in data:
            audio_bytes = base64.b64decode(data['audioContent'])
            logger.info(f"✅ TTS gerado: {len(audio_bytes)/1024:.1f} KB")
            return audio_bytes
        else:
            logger.error(f"Resposta sem audioContent: {list(data.keys())}")
            return None
    else:
        logger.info(f"✅ TTS gerado (raw): {len(response.content)/1024:.1f} KB")
        return response.content


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def is_tts_available() -> bool:
    """Verifica se TTS está configurado"""
    return TTS_AVAILABLE or bool(FIREBASE_REFRESH_TOKEN)


def update_token(new_token: str):
    """Atualiza token em runtime"""
    global _current_token, TTS_AVAILABLE
    _current_token = new_token
    TTS_AVAILABLE = bool(new_token)
    logger.info("🔑 Token TTS atualizado manualmente")
