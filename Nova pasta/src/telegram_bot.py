"""
Perplexo Bot - Telegram
=======================
Bot completo para Telegram com UI visual nativa:
- Menu de comandos com /
- InlineKeyboard com botões
- Seletores com checkmarks (✅/○)
- Toggles ON/OFF no /config
- Handlers para texto, imagens e documentos

Comandos:
- /start   - Menu principal
- /modelos - Escolher modelo AI
- /busca   - Modo de busca (Focus)
- /normal  - Conversa casual
- /config  - Configurações avançadas
- /ajuda   - Guia de uso

Uso:
    python src/telegram_bot.py
"""

import os
import sys
import base64
import logging
import asyncio
import json
import re
import time
from typing import Dict, Any, Optional

# APScheduler para tarefas agendadas
try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    SCHEDULER_AVAILABLE = True
except ImportError:
    SCHEDULER_AVAILABLE = False
    AsyncIOScheduler = None

# Task Manager local
from task_manager import Task, init_task_manager, get_task_manager

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    BotCommand
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
import httpx
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

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
MCP_API = os.getenv("MCP_API_URL", "http://127.0.0.1:5000")
VPN_API = os.getenv("VPN_API_URL", "http://127.0.0.1:8000")  # Gluetun control server
TELEGRAM_PORT = int(os.getenv("TELEGRAM_PORT", 8000))

# Verifica token
if not TELEGRAM_TOKEN or TELEGRAM_TOKEN == "seu_token_aqui":
    logger.error("❌ TELEGRAM_TOKEN não configurado! Edite o arquivo .env")
    sys.exit(1)

# ============= STORAGE DE PREFERÊNCIAS =============
# Em produção, substitua por Redis ou banco de dados

user_preferences: Dict[int, Dict[str, Any]] = {}

# Buffer de arquivos pendentes (até 9 arquivos por usuário)
# Formato: {user_id: [{"name": str, "bytes": bytes, "mime": str, "timestamp": float}, ...]}
pending_files: Dict[int, list] = {}


def get_user_config(user_id: int) -> Dict[str, Any]:
    """Retorna configuração do usuário ou padrão"""
    return user_preferences.get(user_id, {
        'model': 'sonar',
        'focus': 'web',
        'mode': 'busca',
        'reasoning': False,
        'return_images': True,
        'mode': 'busca',
        'time_range': 'all',
        'reasoning': False,
        'return_images': True,
        'return_citations': True
    })


def save_user_config(user_id: int, config: Dict[str, Any]) -> None:
    """Salva configuração do usuário"""
    user_preferences[user_id] = config


# ============= DADOS DOS MODELOS E FOCUS =============

MODELS = [
    ('best', '🎯 Best (Auto)', 'Seleciona o melhor'),
    ('sonar', '⚡ Sonar', 'Perplexity, rápido'),
    ('deep-research', '📊 Deep Research', 'Pesquisa profunda'),
    ('gpt-5.2', '🧠 GPT-5.2', 'OpenAI'),
    ('gpt-5.2-thinking', '🧠💭 GPT-5.2 Think', 'OpenAI c/ raciocínio'),
    ('claude-4.5-sonnet', '🎭 Claude Sonnet', 'Anthropic rápido'),
    ('claude-4.5-opus', '🎭✨ Claude Opus', 'Anthropic avançado'),
    ('gemini-3-flash', '💎 Gemini Flash', 'Google rápido'),
    ('gemini-3-pro-thinking', '💎🔥 Gemini Pro', 'Google avançado'),
    ('grok-4.1', '🚀 Grok 4.1', 'xAI'),
    ('kimi-k2.5-thinking', '🌙 Kimi K2.5', 'Moonshot AI')
]

FOCUS_MODES = [
    ('web', '🌐 Web', 'Busca geral'),
    ('academic', '🎓 Academic', 'Papers científicos'),
    ('writing', '✍️ Writing', 'Auxílio escrita'),
    ('youtube', '🎥 YouTube', 'Vídeos'),
    ('reddit', '💬 Reddit', 'Discussões'),
    ('wolfram', '🧮 Wolfram', 'Matemática/Cálculos')
]

TIME_RANGES = [
    ('all', '♾️ Qualquer data', 'Sem filtro de tempo'),
    ('day', '📅 Últimas 24h', 'Pesquisa apenas hoje'),
    ('week', '🗓️ Esta Semana', 'Últimos 7 dias'),
    ('month', '📆 Este Mês', 'Últimos 30 dias'),
    ('year', '📅 Este Ano', 'Últimos 365 dias')
]


# ============= SETUP DOS COMANDOS =============

async def post_init(application: Application) -> None:
    """Registra comandos no menu do Telegram"""
    commands = [
        BotCommand("start", "🏠 Menu Principal"),
        BotCommand("modelos", "🤖 Escolher Modelo AI"),
        BotCommand("busca", "🔍 Modo de Busca (Focus)"),
        BotCommand("denovo", "🔄 Tentar Novamente (Retry)"),
        BotCommand("tempo", "📅 Filtro de Tempo"),
        BotCommand("new", "✨ Nova Conversa"),
        BotCommand("library", "📚 Save Cloud (Toggle)"),
        BotCommand("token", "🔑 Atualizar Token"),
        BotCommand("historico", "📂 Histórico salvo"),
        BotCommand("teste", "🕵️ Diagnóstico"),
        BotCommand("importar", "📥 Importar Contexto"),
        BotCommand("normal", "💬 Conversa Normal"),
        BotCommand("config", "⚙️ Configurações"),
        BotCommand("limpar", "🗑️ Limpar Histórico"),
        BotCommand("ajuda", "❓ Guia de Uso")
    ]
    await application.bot.set_my_commands(commands)
    logger.info("✅ Comandos registrados no menu do Telegram")


# ============= COMANDO /start =============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Menu principal com botões inline"""
    user_id = update.effective_user.id
    config = get_user_config(user_id)
    
    keyboard = [
        [
            InlineKeyboardButton("✨ Nova Conversa", callback_data='menu_new'),
            InlineKeyboardButton("📂 Histórico", callback_data='menu_history')
        ],
        [
            InlineKeyboardButton("🤖 Modelo", callback_data='menu_modelos'),
            InlineKeyboardButton("🔍 Busca", callback_data='menu_busca'),
            InlineKeyboardButton("⏱ Tempo", callback_data='menu_tempo')
        ],
        [
            InlineKeyboardButton("🔑 Tokens", callback_data='menu_tokens'),
            InlineKeyboardButton("🔒 VPN", callback_data='menu_vpn'),
            InlineKeyboardButton("☁️ Library", callback_data='menu_library')
        ],
        [
            InlineKeyboardButton("📅 Tarefas", callback_data='menu_tasks'),
            InlineKeyboardButton("⚙️ Config", callback_data='menu_config'),
            InlineKeyboardButton("❓ Ajuda", callback_data='menu_ajuda')
        ]
    ]
    
    text = (
        f"🌀 *Perplexo Bot* - Painel de Controle\n\n"
        f"*Status Atual:*\n"
        f"🤖 Modelo: `{config['model']}`\n"
        f"🔍 Focus: `{config['focus']}`\n"
        f"💬 Modo: `{config['mode']}`\n"
        f"☁️ Library: `{'ON' if config.get('save_to_library') else 'OFF'}`\n\n"
        f"_Selecione uma opção:_"
    )
    
    if update.message:
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    elif update.callback_query:
        # Se for o mesmo texto, ignora erro de edição
        try:
            await update.callback_query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        except Exception:
            # Às vezes o conteúdo é idêntico
            pass


# ============= COMANDO /modelos =============

async def cmd_modelos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lista de modelos com seletor visual (checkmark)"""
    user_id = update.effective_user.id
    config = get_user_config(user_id)
    current_model = config['model']
    
    keyboard = []
    for model_id, emoji_name, description in MODELS:
        prefix = "✅ " if model_id == current_model else ""
        button_text = f"{prefix}{emoji_name}"
        keyboard.append([InlineKeyboardButton(
            button_text,
            callback_data=f'set_model_{model_id}'
        )])
    
    keyboard.append([InlineKeyboardButton("« Voltar", callback_data='back_main')])
    
    text = "🤖 *Escolher Modelo AI*\n\n"
    for model_id, emoji_name, description in MODELS:
        marker = "✅" if model_id == current_model else "○"
        text += f"{marker} *{emoji_name}*\n   _{description}_\n\n"
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    elif update.message:
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )


# ============= COMANDO /busca =============

async def cmd_busca(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Focus modes com seletor visual"""
    user_id = update.effective_user.id
    config = get_user_config(user_id)
    current_focus = config['focus']
    
    keyboard = []
    for focus_id, emoji_name, description in FOCUS_MODES:
        prefix = "✅ " if focus_id == current_focus else ""
        button_text = f"{prefix}{emoji_name}"
        keyboard.append([InlineKeyboardButton(
            button_text,
            callback_data=f'set_focus_{focus_id}'
        )])
    

    keyboard.append([InlineKeyboardButton("📅 Recency (Tempo)", callback_data='menu_tempo')])
    keyboard.append([InlineKeyboardButton("« Voltar", callback_data='back_main')])
    
    text = "🔍 *Modo de Busca (Focus)*\n\n"
    for focus_id, emoji_name, description in FOCUS_MODES:
        marker = "✅" if focus_id == current_focus else "○"
        text += f"{marker} *{emoji_name}* - {description}\n"
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    elif update.message:
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )


async def cmd_tempo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Seletor de Time Range"""
    user_id = update.effective_user.id
    config = get_user_config(user_id)
    current_range = config.get('time_range', 'all')
    
    keyboard = []
    for range_id, emoji_name, description in TIME_RANGES:
        prefix = "✅ " if range_id == current_range else ""
        button_text = f"{prefix}{emoji_name}"
        keyboard.append([InlineKeyboardButton(
            button_text,
            callback_data=f'set_time_{range_id}'
        )])
    
    keyboard.append([InlineKeyboardButton("« Voltar", callback_data='menu_busca')])
    
    text = "📅 *Filtro de Tempo (Recency)*\n\n"
    for range_id, emoji_name, description in TIME_RANGES:
        marker = "✅" if range_id == current_range else "○"
        text += f"{marker} *{emoji_name}* - {description}\n"
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    elif update.message:
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )


# ============= COMANDO /config =============

async def cmd_config(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Painel de configurações com toggle switches"""
    user_id = update.effective_user.id
    config = get_user_config(user_id)
    
    keyboard = [
        [InlineKeyboardButton(
            f"🧠 Reasoning: {'🟢 ON' if config['reasoning'] else '🔴 OFF'}",
            callback_data='toggle_reasoning'
        )],
        [InlineKeyboardButton(
            f"📚 Citações: {'🟢 ON' if config['return_citations'] else '🔴 OFF'}",
            callback_data='toggle_citations'
        )],
        [InlineKeyboardButton(
            f"🖼️ Imagens: {'🟢 ON' if config['return_images'] else '🔴 OFF'}",
            callback_data='toggle_images'
        )],
        [
            InlineKeyboardButton("🤖 Modelo", callback_data='menu_modelos'),
            InlineKeyboardButton("🔍 Focus", callback_data='menu_busca')
        ],
        [InlineKeyboardButton("« Voltar", callback_data='back_main')]
    ]
    
    text = (
        "⚙️ *Configurações*\n\n"
        f"*Modelo Atual:* `{config['model']}`\n"
        f"*Focus Atual:* `{config['focus']}`\n"
        f"*Modo:* `{config['mode']}`\n\n"
        f"*Opções Avançadas:*\n"
        f"{'🟢' if config['reasoning'] else '🔴'} Reasoning (raciocínio step-by-step)\n"
        f"{'🟢' if config['return_citations'] else '🔴'} Citações de fontes\n"
        f"{'🟢' if config['return_images'] else '🔴'} Retornar imagens\n\n"
        f"_Toque nos botões para alternar ON/OFF_"
    )
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    elif update.message:
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )


# ============= COMANDO /normal =============

async def cmd_normal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ativa modo conversa normal"""
    user_id = update.effective_user.id
    config = get_user_config(user_id)
    config['mode'] = 'normal'
    config['return_citations'] = False
    save_user_config(user_id, config)
    
    text = (
        "💬 *Modo Normal ativado*\n\n"
        "Agora respondo sem citações, como uma conversa casual.\n"
        "Use /busca para voltar ao modo pesquisa."
    )
    
    if update.callback_query:
        await update.callback_query.answer("Modo normal ativado!")
        await update.callback_query.edit_message_text(text, parse_mode='Markdown')
    elif update.message:
        await update.message.reply_text(text, parse_mode='Markdown')


# ============= COMANDO /ajuda =============

async def cmd_ajuda(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Guia de uso"""
    text = (
        "❓ *Guia de Uso do Perplexo Bot*\n\n"
        "*Comandos no menu '/' :*\n"
        "• `/start` - Menu principal\n"
        "• `/modelos` - Escolher modelo AI\n"
        "• `/busca` - Modo de busca (Focus)\n"
        "• `/normal` - Conversa casual\n"
        "• `/config` - Configurações avançadas\n"
        "• `/limpar` - Limpar histórico de conversa\n\n"
        "*Recursos:*\n"
        "• Envie texto para perguntas\n"
        "• Envie imagens para análise visual\n"
        "• Envie arquivos .txt para resumir\n\n"
        "*Histórico:*\n"
        "💬 Conversas salvas automaticamente ao usar `/new` ou `/limpar`.\n"
        "• `/historico` - Lista conversas antigas\n"
        "• `/importar <ID>` - Importa conversa antiga como contexto atual\n\n"
        "*Modelos disponíveis:*\n"
        "⚡ Sonar - Rápido, ideal para Q&A\n"
        "🔥 Sonar Pro - Análises detalhadas\n"
        "🧠 GPT-5.2 - Coding e raciocínio\n"
        "🤔 Reasoning Pro - Lógica complexa\n"
        "📊 Deep Research - Pesquisa máxima\n\n"
        "*Dica:* Use os botões do `/config` para personalizar!"
    )
    
    keyboard = [[InlineKeyboardButton("« Voltar", callback_data='back_main')]]
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    elif update.message:
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )


# ============= COMANDO /limpar =============

async def cmd_limpar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Limpa histórico de conversação no servidor MCP"""
    user_id = update.effective_user.id
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{MCP_API}/clear",
                json={"user_id": str(user_id)}
            )
            data = response.json()
        
        msg = data.get('message', 'Histórico limpo!')
        saved_id = data.get('saved_conversation_id')
        
        response_text = f"🗑️ *{msg}*\n\n"
        if saved_id:
            response_text += f"💾 *ID Salvo:* `{saved_id}`\n"
            response_text += f"Use `/importar {saved_id}` no futuro.\n\n"
            
        response_text += "Iniciando uma nova conversa do zero."
        
        await update.message.reply_text(
            response_text,
            parse_mode='Markdown'
        )
    except Exception as e:
        await update.message.reply_text(
            "🗑️ *Histórico limpo!*\n\n"
            "Iniciando uma nova conversa do zero.",
            parse_mode='Markdown'
        )


# ============= COMANDO /importar =============

async def cmd_importar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Importa o contexto de uma conversa salva"""
    user_id = update.effective_user.id
    args = context.args
    
    if not args:
        await update.message.reply_text(
            "⚠️ Use: `/importar <ID>`\n"
            "Exemplo: `/importar a1b2c3d4`\n\n"
            "Use `/historico` para ver os IDs.",
            parse_mode='Markdown'
        )
        return
        
    conv_id = args[0]
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    try:
        # Carrega histórico da API
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{MCP_API}/history/load",
                json={"user_id": str(user_id), "conversation_id": conv_id}
            )
            
        if response.status_code != 200:
            await update.message.reply_text("❌ Histórico não encontrado.", parse_mode='Markdown')
            return
            
        data = response.json()
        conversation = data.get('conversation', {})
        messages = conversation.get('messages', [])
        title = conversation.get('title', 'Sem título')
        
        if not messages:
            await update.message.reply_text("⚠️ Histórico vazio.", parse_mode='Markdown')
            return
            
        # Formata contexto
        context_text = f"Contexto importado da conversa '{title}' (ID: {conv_id}):\n\n"
        for msg in messages:
            role = "USUÁRIO" if msg.get('role') == 'user' else "ASSISTENTE"
            content = msg.get('content', '')
            context_text += f"[{role}]: {content}\n\n"
            
        # Envia como prompt para a IA
        user_query = (
            f"Estou fornecendo um contexto de uma conversa anterior para nossa referência.\n"
            f"Por favor, leia e confirme que entendeu o contexto. Não precisa resumir, apenas confirme.\n\n"
            f"--- INÍCIO DO CONTEXTO ---\n"
            f"{context_text[:10000]}..." # Limite de segurança
            f"\n--- FIM DO CONTEXTO ---"
        )
        
        # Envia para o MCP /search
        config = get_user_config(user_id)
        async with httpx.AsyncClient(timeout=120.0) as client:
            payload = {
                "query": user_query,
                "user_id": str(user_id),
                "model": config['model'],
                "focus": "writing", # Focus writing é bom para processar texto
                "return_citations": False
            }
            
            response = await client.post(f"{MCP_API}/search", json=payload)
            response.raise_for_status()
            search_data = response.json()
            
        answer = search_data.get('answer', 'Contexto processado.')
        
        await update.message.reply_text(
            f"✅ *Contexto Importado!*\n"
            f"Dívida `{title}` foi adicionada ao contexto atual.\n\n"
            f"🤖 *Resposta da IA:*\n_{answer}_",
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Erro ao importar: {e}")
        await update.message.reply_text("❌ Erro ao importar contexto.", parse_mode='Markdown')


# ============= COMANDO /new =============

async def cmd_new(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Cria uma nova conversa (limpa a anterior)"""
    user_id = update.effective_user.id
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{MCP_API}/clear",
                json={"user_id": str(user_id)}
            )
            data = response.json()
        
        msg_count = 0
        saved_id = data.get('saved_conversation_id')
        
        if 'mensagens' in data.get('message', ''):
            import re
            match = re.search(r'\((\d+)', data.get('message', ''))
            if match:
                msg_count = int(match.group(1))
        
        msg_text = f"✨ *Nova conversa iniciada!*\n\n"
        if saved_id:
             msg_text += f"💾 *Histórico salvo:* `{saved_id}`\n"
             msg_text += f"Use `/importar {saved_id}` para recuperar este contexto.\n\n"
             
        msg_text += f"Conversa anterior encerrada{f' ({msg_count} mensagens)' if msg_count else ''}.\n"
        msg_text += "Me pergunte qualquer coisa! 🚀"
        
        # Envia a resposta (compatível com comando e callback)
        if update.callback_query:
            # Se veio de botão, confirma o callback e manda nova mensagem
            await update.callback_query.answer("Nova conversa iniciada!")
            await update.effective_message.reply_text(msg_text, parse_mode='Markdown')
        else:
            await update.message.reply_text(msg_text, parse_mode='Markdown')
            
    except Exception as e:
        logger.error(f"Erro no cmd_new: {e}")
        fallback_text = "✨ *Nova conversa iniciada!*\n\nMe pergunte qualquer coisa! 🚀"
        if update.callback_query:
            await update.effective_message.reply_text(fallback_text, parse_mode='Markdown')
        else:
            await update.message.reply_text(fallback_text, parse_mode='Markdown')


# ============= COMANDO /historico =============

async def cmd_historico(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lista conversas salvas"""
    user_id = update.effective_user.id
    
    # Prepara envio (suporta message e callback)
    if update.callback_query:
        await update.callback_query.answer()
        # Edita ou envia nova msg? Melhor enviar nova para histórico não sumir rápido
        # Mas para menu, editar é mais fluido. O usuário decide com "voltar".
        # Vamos editar para ficar clean.
        reply_method = update.callback_query.edit_message_text
        reply_attr = {} # edit_message não aceita reply_to_message_id
    else:
        reply_method = update.message.reply_text
        reply_attr = {}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{MCP_API}/history/list", params={"user_id": str(user_id)})
            data = response.json()
            
        conversations = data.get('conversations', [])
        
        if not conversations:
            text = (
                "📂 *Seu histórico está vazio.*\n\n"
                "Use `/new` para criar novas conversas e elas serão salvas automaticamente ao limpar."
            )
            # Se for callback, pode ter botão "voltar"
            kb = [[InlineKeyboardButton("« Voltar", callback_data='back_main')]] if update.callback_query else []
            
            await reply_method(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))
            return
        
        keyboard = []
        text = "📂 *Histórico de Conversas:*\n\n"
        
        for conv in conversations:
            conv_id = conv.get('id')
            title = conv.get('title', 'Sem título')
            date_str = conv.get('created_at', '')[:10]  # YYYY-MM-DD
            msg_count = conv.get('message_count', 0)
            
            # Formata data
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(conv.get('created_at'))
                date_fmt = dt.strftime("%d/%m %H:%M")
            except:
                date_fmt = date_str
            
            # Adiciona ao texto
            text += f"🔹 `{date_fmt}` - *{title}* ({msg_count} msgs)\n"
            
            # Adiciona botão
            keyboard.append([InlineKeyboardButton(
                f"📂 Abrir: {title[:20]}...",
                callback_data=f'load_history_{conv_id}'
            )])
            
        keyboard.append([InlineKeyboardButton("« Voltar", callback_data='back_main')])
        
        await reply_method(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Erro ao listar histórico: {e}")
        err_text = "❌ Erro ao buscar histórico."
        await reply_method(err_text, parse_mode='Markdown')



# ============= COMANDO /denovo (RETRY) =============

async def cmd_denovo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Tenta recuperar a última resposta do backend (Retry)"""
    user_id = update.effective_user.id
    
    await update.message.reply_text("🔄 Verificando histórico no servidor...", parse_mode='Markdown')
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{MCP_API}/last_response", params={"user_id": user_id})
            
            if response.status_code == 200:
                data = response.json()
                answer = data.get('answer', '')
                
                if not answer:
                    await update.message.reply_text("❌ A última resposta estava vazia.")
                    return
                    
                await update.message.reply_text("✅ Resposta recuperada! Processando arquivos...")
                
                # Reutiliza a lógica robusta de extração
                final_text = await extract_and_send_files(update, answer)
                
                # Envia o texto final formatado
                await update.message.reply_text(final_text, parse_mode='Markdown', disable_web_page_preview=True)
                
            elif response.status_code == 404:
                await update.message.reply_text("❌ Nenhuma conversa recente encontrada na memória do servidor.")
            else:
                await update.message.reply_text(f"❌ Erro ao buscar: {response.status_code}")
                
    except Exception as e:
        logger.error(f"Erro cmd_denovo: {e}")
        await update.message.reply_text(f"❌ Erro ao tentar recuperar: {e}")


# ============= DETECÇÃO DE TAREFAS =============

def detect_task_proposal(text: str) -> Optional[Dict[str, Any]]:
    """
    Detecta propostas de tarefa no texto da resposta.
    Retorna dict com dados da tarefa ou None.
    """
    # Padrões comuns de proposta de tarefa
    task_patterns = [
        r"##\s*Detalhes da Tarefa",
        r"\*\*Nome\*\*:\s*(.+)",
        r"\*\*Prompt\*\*:\s*(.+)",
        r"\*\*Agendamento\*\*:\s*(.+)",
        r"Vou propor.*tarefa",
        r"criar uma tarefa.*agend",
    ]
    
    # Verifica se parece uma proposta de tarefa
    is_task = any(re.search(p, text, re.IGNORECASE) for p in task_patterns[:2])
    if not is_task:
        return None
    
    # Extrai dados
    result = {
        "name": None,
        "prompt": None,
        "schedule_type": "daily",
        "schedule_time": "09:00"
    }
    
    # Nome
    match = re.search(r"\*\*Nome\*\*:\s*(.+?)(?:\n|$)", text)
    if match:
        result["name"] = match.group(1).strip()
    
    # Prompt
    match = re.search(r"\*\*Prompt\*\*:\s*[\"']?(.+?)[\"']?(?:\n|$)", text)
    if match:
        result["prompt"] = match.group(1).strip()
    
    # Agendamento
    match = re.search(r"\*\*Agendamento\*\*:\s*(.+?)(?:\n|$)", text)
    if match:
        sched_text = match.group(1).lower()
        if "diário" in sched_text or "daily" in sched_text or "todo dia" in sched_text:
            result["schedule_type"] = "daily"
        elif "uma vez" in sched_text or "once" in sched_text:
            result["schedule_type"] = "once"
        
        # Extrai horário
        time_match = re.search(r"(\d{1,2}):(\d{2})", sched_text)
        if time_match:
            result["schedule_time"] = f"{int(time_match.group(1)):02d}:{time_match.group(2)}"
        else:
            # Tenta pegar hora AM/PM
            time_match = re.search(r"(\d{1,2})\s*(AM|PM)", sched_text, re.IGNORECASE)
            if time_match:
                hour = int(time_match.group(1))
                if time_match.group(2).upper() == "PM" and hour < 12:
                    hour += 12
                result["schedule_time"] = f"{hour:02d}:00"
    
    # Valida se tem dados mínimos
    if result["name"] or result["prompt"]:
        return result
    
    return None


async def send_task_confirmation(update: Update, task: Task) -> None:
    """Envia mensagem de confirmação com botões para a tarefa proposta"""
    text = (
        f"📋 *Proposta de Tarefa*\n\n"
        f"*Nome:* {task.name}\n"
        f"*Prompt:* _{task.prompt[:100]}{'...' if len(task.prompt) > 100 else ''}_\n"
        f"*Tipo:* {task.schedule_type}\n"
        f"*Horário:* {task.schedule_time}\n\n"
        f"Confirme para ativar:"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Confirmar", callback_data=f"task_confirm_{task.task_id}"),
            InlineKeyboardButton("❌ Cancelar", callback_data=f"task_cancel_{task.task_id}")
        ],
        [
            InlineKeyboardButton("🔁 Editar Horário", callback_data=f"task_edit_{task.task_id}")
        ]
    ]
    
    await update.message.reply_text(
        text,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ============= COMANDO /tarefas =============

async def cmd_tarefas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lista tarefas ativas do usuário"""
    user_id = update.effective_user.id
    tm = get_task_manager()
    
    # Prepara envio (suporta message e callback)
    if update.callback_query:
        await update.callback_query.answer()
        reply_method = update.callback_query.edit_message_text
    else:
        reply_method = update.message.reply_text

    if not tm:
        await reply_method("❌ Gerenciador de tarefas não disponível.")
        return
    
    tasks = tm.get_tasks(user_id)
    
    # Botão voltar sempre bom
    kb_back = [[InlineKeyboardButton("🔙 Voltar", callback_data='back_main')]]
    
    if not tasks:
        text = (
            "📋 *Suas Tarefas*\n\n"
            "_Você não tem tarefas agendadas._\n\n"
            "Peça ao bot para criar uma tarefa, exemplo:\n"
            '"Crie uma tarefa para me avisar o preço do Bitcoin todo dia às 9h"'
        )
        await reply_method(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb_back))
        return
    
    text = "📋 *Suas Tarefas Ativas:*\n\n"
    keyboard = []
    
    for task in tasks:
        status = "✅" if task.enabled else "⏸️"
        text += f"{status} *{task.name}*\n"
        text += f"   ⏰ {task.schedule_type} às {task.schedule_time}\n"
        if task.last_run:
            text += f"   📅 Última exec: {task.last_run[:16]}\n"
        text += "\n"
        
        keyboard.append([
            InlineKeyboardButton(f"🗑️ {task.name[:15]}", callback_data=f"task_delete_{task.task_id}")
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 Voltar", callback_data='back_main')])
    
    await reply_method(
        text,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ============= CALLBACK HANDLER DE TAREFAS =============

async def handle_task_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Processa callbacks relacionados a tarefas. Retorna True se processou."""
    query = update.callback_query
    data = query.data
    
    if not data.startswith("task_"):
        return False
    
    await query.answer()
    user_id = query.from_user.id
    tm = get_task_manager()
    
    if not tm:
        await query.edit_message_text("❌ Gerenciador de tarefas não disponível.")
        return True
    
    if data.startswith("task_confirm_"):
        task_id = data.replace("task_confirm_", "")
        task = tm.confirm_pending_task(task_id)
        
        if task:
            await query.edit_message_text(
                f"✅ *Tarefa Ativada!*\n\n"
                f"*{task.name}*\n"
                f"Será executada {task.schedule_type} às {task.schedule_time}.",
                parse_mode='Markdown'
            )
        else:
            await query.edit_message_text("❌ Tarefa não encontrada ou já confirmada.")
    
    elif data.startswith("task_cancel_"):
        task_id = data.replace("task_cancel_", "")
        tm.cancel_pending_task(task_id)
        await query.edit_message_text("❌ Tarefa cancelada.")
    
    elif data.startswith("task_edit_"):
        task_id = data.replace("task_edit_", "")
        # Mostra opções de horário
        keyboard = [
            [
                InlineKeyboardButton("06:00", callback_data=f"task_time_{task_id}_06:00"),
                InlineKeyboardButton("09:00", callback_data=f"task_time_{task_id}_09:00"),
                InlineKeyboardButton("12:00", callback_data=f"task_time_{task_id}_12:00"),
            ],
            [
                InlineKeyboardButton("15:00", callback_data=f"task_time_{task_id}_15:00"),
                InlineKeyboardButton("18:00", callback_data=f"task_time_{task_id}_18:00"),
                InlineKeyboardButton("21:00", callback_data=f"task_time_{task_id}_21:00"),
            ]
        ]
        await query.edit_message_text(
            "🕐 Escolha o horário:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif data.startswith("task_time_"):
        # task_time_{task_id}_{time}
        parts = data.split("_")
        task_id = parts[2]
        new_time = parts[3]
        
        if task_id in tm.pending_tasks:
            tm.pending_tasks[task_id].schedule_time = new_time
            task = tm.confirm_pending_task(task_id)
            await query.edit_message_text(
                f"✅ *Tarefa Ativada!*\n\n"
                f"*{task.name}*\n"
                f"Será executada às *{new_time}*.",
                parse_mode='Markdown'
            )
    
    elif data.startswith("task_delete_"):
        task_id = data.replace("task_delete_", "")
        if tm.delete_task(user_id, task_id):
            await query.edit_message_text("🗑️ Tarefa removida com sucesso!")
        else:
            await query.edit_message_text("❌ Erro ao remover tarefa.")
    
    return True


# ============= COMANDO /library =============

async def cmd_library(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Alterna o modo Save to Library (Nuvem)"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # POST faz o toggle
            response = await client.post(f"{MCP_API}/config/library")
            data = response.json()
            
            enabled = data.get('enabled', False)
            msg = data.get('message', '')
            
            # Feedback com emoji
            if enabled:
                text = f"☁️ *{msg}* - Modo Nuvem Ativo\n\n" \
                       f"Resetando contexto para iniciar uma nova conversa limpa na Library..."
            else:
                text = f"🏠 *{msg}* - Modo Local Ativo\n\n" \
                       f"Conversas salvas apenas no dispositivo."
            
            # Envia resposta
            if update.callback_query:
                await update.callback_query.answer()
                await update.effective_message.reply_text(text, parse_mode='Markdown')
            else:
                await update.message.reply_text(text, parse_mode='Markdown')

            # SE ATIVOU, OBRIGA O RESET (CMD_NEW)
            if enabled:
                # Pequeno delay visual
                await asyncio.sleep(1)
                await cmd_new(update, context)
            
    except Exception as e:
        logger.error(f"Erro library toggle: {e}")
        error_text = "❌ Erro ao alterar configuração."
        if update.callback_query:
            await update.effective_message.reply_text(error_text)
        else:
            await update.message.reply_text(error_text)


# ============= COMANDO /vpn =============

async def cmd_vpn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Controle da VPN: status, ativar/desativar, reconectar"""
    
    # Suporte a callback
    if update.callback_query:
        await update.callback_query.answer()
        reply_method = update.callback_query.edit_message_text
        msg = update.effective_message # Para editar depois se precisar interagir
    else:
        msg = await update.message.reply_text("🔄 *Verificando VPN...*", parse_mode='Markdown')
        reply_method = msg.edit_text

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Obtém status atual
            try:
                status_resp = await client.get(f"{VPN_API}/v1/openvpn/status")
                status_data = status_resp.json()
                vpn_status = status_data.get('status', 'unknown')
            except:
                vpn_status = 'offline'
            
            # Obtém IP público
            try:
                ip_resp = await client.get(f"{VPN_API}/v1/publicip/ip")
                ip_data = ip_resp.json()
                public_ip = ip_data.get('public_ip', 'Desconhecido')
            except:
                public_ip = 'Erro ao obter'
            
            # Emoji de status
            if vpn_status == 'running':
                status_emoji = "🟢"
                status_text = "Conectada"
            elif vpn_status == 'stopped':
                status_emoji = "🔴"
                status_text = "Desconectada"
            else:
                status_emoji = "⚪"
                status_text = vpn_status.capitalize()
        
        # Monta mensagem
        text = (
            f"🔐 *Controle VPN* (VPS)\n\n"
            f"{status_emoji} *Status:* {status_text}\n"
            f"🌐 *IP Público:* `{public_ip}`\n\n"
            f"Selecione uma ação:"
        )
        
        # Botões
        buttons = []
        if vpn_status == 'running':
            buttons.append([
                InlineKeyboardButton("🔄 Novo IP", callback_data="vpn_reconnect"),
                InlineKeyboardButton("🔴 Desativar", callback_data="vpn_stop")
            ])
        else:
            buttons.append([
                InlineKeyboardButton("🟢 Ativar", callback_data="vpn_start")
            ])
        
        buttons.append([InlineKeyboardButton("🔙 Voltar", callback_data="back_main")])
        
        await reply_method(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(buttons))
        
    except Exception as e:
        logger.error(f"Erro cmd_vpn: {e}")
        await reply_method(f"❌ Erro ao verificar VPN: {e}", parse_mode='Markdown')


async def handle_vpn_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Handler para callbacks de VPN"""
    query = update.callback_query
    data = query.data
    
    if not data.startswith("vpn_"):
        return False
    
    await query.answer()
    
    action = data.replace("vpn_", "")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            if action == "start":
                await query.edit_message_text("🔌 *Ativando VPN...*", parse_mode='Markdown')
                await client.put(f"{VPN_API}/v1/openvpn/status", json={"status": "running"})
                await asyncio.sleep(3)  # Aguarda conexão
                
            elif action == "stop":
                await query.edit_message_text("🔌 *Desativando VPN...*", parse_mode='Markdown')
                await client.put(f"{VPN_API}/v1/openvpn/status", json={"status": "stopped"})
                await asyncio.sleep(1)
                
            elif action == "reconnect":
                await query.edit_message_text("🔄 *Reconectando VPN (novo IP)...*", parse_mode='Markdown')
                # Stop then start para forçar novo servidor
                await client.put(f"{VPN_API}/v1/openvpn/status", json={"status": "stopped"})
                await asyncio.sleep(2)
                await client.put(f"{VPN_API}/v1/openvpn/status", json={"status": "running"})
                await asyncio.sleep(5)  # Aguarda reconexão
        
        # Atualiza status após ação
        await cmd_vpn(update, context)
        
    except Exception as e:
        logger.error(f"Erro VPN action {action}: {e}")
        await query.edit_message_text(f"❌ Erro: {e}", parse_mode='Markdown')
    
    return True


# ============= COMANDO /token =============
async def cmd_token(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Gerenciador de Tokens (Dashboard)"""
    
    # Suporte a callback
    if update.callback_query:
        await update.callback_query.answer()
        reply_method = update.callback_query.edit_message_text
    else:
        msg = await update.message.reply_text("🔄 *Carregando painel de tokens...*", parse_mode='Markdown')
        reply_method = msg.edit_text

    # Se usuário passou argumento: /token <sess> (Modo Manual)
    if context.args:
        token = context.args[0]
        try:
            await update.message.delete()
        except: pass
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(f"{MCP_API}/config/token", json={"token": token})
                if resp.status_code == 200:
                    await reply_method("✅ *Token Inserido Manualmente!*", parse_mode='Markdown')
                else:
                    await reply_method(f"❌ Erro: {resp.text}", parse_mode='Markdown')
        except Exception as e:
            await reply_method(f"❌ Erro de conexão: {e}", parse_mode='Markdown')
        return

    # Modo Dashboard
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            status_resp = await client.get(f"{MCP_API}/tokens/status")
            try:
                status = status_resp.json()
            except:
                status = {}
            
        current = status.get('current_account', {})
        total = status.get('total_accounts', 0)
        idx = status.get('current_index', 0) + 1
        is_active = status.get('active', False)
        
        status_emoji = "🟢" if is_active else "🔴"
        
        text = (
            f"🔑 *Gestão de Tokens* {status_emoji}\n\n"
            f"👤 *Conta:* `{current.get('email', 'N/A')}`\n"
            f"🏷️ *Nome:* {current.get('name', 'N/A')}\n"
            f"🔢 *Índice:* {idx}/{total}\n"
            f"📅 *Validade:* {current.get('expires', 'Desconhecida')}\n\n"
            f"_Selecione uma ação:_"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Validar", callback_data='token_validate'),
                InlineKeyboardButton("🔄 Rotação (Next)", callback_data='token_rotate')
            ],
            [
                InlineKeyboardButton("🆕 Novo Refresh OTP", callback_data='token_new_refresh')
            ],
            [InlineKeyboardButton("🔙 Voltar", callback_data='back_main')]
        ]
        
        await reply_method(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
        
    except Exception as e:
        logger.error(f"Erro cmd_token: {e}")
        await reply_method(f"❌ Erro ao carregar painel: {e}", parse_mode='Markdown')


# ============= COMANDO /teste =============

async def cmd_teste(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Executa diagnóstico do sistema"""
    try:
        msg = await update.message.reply_text("🕵️ *Executando diagnóstico...*", parse_mode='Markdown')
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                # Chama endpoint de diagnóstico
                response = await client.get(f"{MCP_API}/diagnostics")
                data = response.json()
                
                status_mcp = "✅ Online" if data.get('mcp_status') == 'online' else "❌ Offline"
                ip = data.get('public_ip', 'Desconhecido')
                auth_status = data.get('perplexity_auth', 'unknown')
                
                auth_emoji = "✅ Válido" if auth_status == 'configured' else "❌ Inválido/Ausente"
                if auth_status == 'missing_token': auth_emoji = "⚠️ Sem Token"
                
                report = (
                    "🕵️ *Relatório de Diagnóstico*\n\n"
                    f"🤖 *MCP Server:* {status_mcp}\n"
                    f"🌐 *IP de Saída:* `{ip}`\n"
                    f"🔑 *Perplexity:* {auth_emoji}\n\n"
                )
                
                if data.get('auth_error'):
                    report += f"⚠️ *Erro Auth:* `{data['auth_error']}`\n"
                    
                await msg.edit_text(report, parse_mode='Markdown')
                
            except httpx.ConnectError:
                await msg.edit_text("❌ *MCP Offline*: Não consegui conectar ao servidor.", parse_mode='Markdown')
                
    except Exception as e:
        logger.error(f"Erro no teste: {e}")
        await update.message.reply_text("❌ Erro ao executar teste.", parse_mode='Markdown')


# ============= HANDLERS DE CALLBACK =============

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para todos os botões inline"""
    query = update.callback_query
    data = query.data
    
    # Processa callbacks de VPN primeiro
    if data.startswith("vpn_"):
        await handle_vpn_callback(update, context)
        return
    
    # Processa callbacks de tarefas
    if data.startswith("task_"):
        await handle_task_callback(update, context)
        return
    
    await query.answer()
    
    user_id = update.effective_user.id
    
    # Navegação e Menus Principais
    if data == 'back_main':
        await start(update, context)
        return
    
    # Handlers do Menu Principal
    if data == 'menu_new':
        await cmd_new(update, context)
    elif data == 'menu_history':
        await cmd_historico(update, context)
    elif data == 'menu_tokens':
        await cmd_token(update, context)
    elif data == 'menu_tasks':
        await cmd_tarefas(update, context)
    elif data == 'menu_library':
        await cmd_library(update, context)
    elif data == 'menu_vpn':
        await cmd_vpn(update, context)
        
    # Sub-menus
    elif data == 'menu_modelos':
        await cmd_modelos(update, context)
    elif data == 'menu_busca':
        await cmd_busca(update, context)
    elif data == 'menu_normal':
        await cmd_normal(update, context)
    elif data == 'menu_config':
        await cmd_config(update, context)
    elif data == 'menu_ajuda':
        await cmd_ajuda(update, context)
    elif data == 'menu_tempo':
        await cmd_tempo(update, context)
    
    # Seleção de modelo
    elif data.startswith('set_model_'):
        model = data.replace('set_model_', '')
        config = get_user_config(user_id)
        config['model'] = model
        config['mode'] = 'busca'
        save_user_config(user_id, config)
        
        await query.answer(f"✅ Modelo {model.upper()} selecionado!")
        await cmd_modelos(update, context)
    
    elif data.startswith('load_history_'):
        conv_id = data.replace('load_history_', '')
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{MCP_API}/history/load",
                    json={"user_id": str(user_id), "conversation_id": conv_id}
                )
                data = response.json()
            
            if response.status_code == 200:
                title = data.get('conversation', {}).get('title', 'Conversa')
                msg_count = len(data.get('conversation', {}).get('messages', []))
                
                await query.answer("✅ Conversa carregada!")
                await query.edit_message_text(
                    f"📂 *Conversa Restaurada!* \n\n"
                    f"📝 *{title}*\n"
                    f"💬 *{msg_count} mensagens recuperadas*\n\n"
                    f"Envie uma mensagem para continuar desta conversa.",
                    parse_mode='Markdown'
                )
            else:
                await query.answer("❌ Erro ao carregar.")
                
        except Exception as e:
            logger.error(f"Erro ao carregar conversa: {e}")
            await query.answer("❌ Erro de conexão.")

    # Seleção de focus
    elif data.startswith('set_focus_'):
        focus = data.replace('set_focus_', '')
        config = get_user_config(user_id)
        config['focus'] = focus
        config['mode'] = 'busca'
        save_user_config(user_id, config)
        
        await query.answer(f"✅ Focus {focus.upper()} selecionado!")
        await cmd_busca(update, context)

    # Seleção de tempo
    elif data.startswith('set_time_'):
        time_range = data.replace('set_time_', '')
        config = get_user_config(user_id)
        config['time_range'] = time_range
        save_user_config(user_id, config)
        
        await query.answer(f"✅ Tempo {time_range.upper()} selecionado!")
        await cmd_tempo(update, context)
    elif data == 'toggle_reasoning':
        config = get_user_config(user_id)
        config['reasoning'] = not config['reasoning']
        save_user_config(user_id, config)
        
        status = "ativado" if config['reasoning'] else "desativado"
        await query.answer(f"Reasoning {status}!")
        await cmd_config(update, context)
    
    elif data == 'toggle_citations':
        config = get_user_config(user_id)
        config['return_citations'] = not config['return_citations']
        save_user_config(user_id, config)
        
        status = "ativadas" if config['return_citations'] else "desativadas"
        await query.answer(f"Citações {status}!")
        await cmd_config(update, context)
    
    elif data == 'toggle_images':
        config = get_user_config(user_id)
        config['return_images'] = not config['return_images']
        save_user_config(user_id, config)
        
        status = "ativadas" if config['return_images'] else "desativadas"
        await query.answer(f"Imagens {status}!")
        await cmd_config(update, context)


# ============= HANDLER DE MENSAGENS DE TEXTO =============

async def reply_chunked(update: Update, text: str):
    """Envia mensagem longa dividida em partes para evitar erro 400 do Telegram"""
    MAX_LENGTH = 4000
    
    if len(text) <= MAX_LENGTH:
        try:
            await update.message.reply_text(text, parse_mode='Markdown', disable_web_page_preview=True)
        except Exception:
             # Fallback: Se der erro de markdown (comum com caracteres especiais), tenta raw
             await update.message.reply_text(text, disable_web_page_preview=True)
        return

    # Divide em partes
    parts = [text[i:i+MAX_LENGTH] for i in range(0, len(text), MAX_LENGTH)]
    
    for i, part in enumerate(parts):
        try:
            # Tenta mandar com markdown
            await update.message.reply_text(part, parse_mode='Markdown', disable_web_page_preview=True)
        except Exception:
            # Se falhar (ex: corte no meio de um bloco de código), manda raw
            await update.message.reply_text(part)


async def extract_and_send_files(update: Update, text: str) -> str:
    """
    Extrai blocos de código (>50 chars), envia como arquivos e remove do texto original.
    Retorna o texto limpo.
    """
    import re
    import tempfile
    
    # Regex para capturar blocos ```lang ... ```
    pattern = r"```(\w+)?\n(.*?)```"
    matches = list(re.finditer(pattern, text, re.DOTALL))
    
    file_count = 0
    clean_text = text
    
    # Mapeamento de extensões
    EXT_MAP = {
        'html': '.html', 'htm': '.html',
        'css': '.css',
        'js': '.js', 'javascript': '.js', 'typescript': '.ts', 'ts': '.ts',
        'py': '.py', 'python': '.py',
        'java': '.java',
        'c': '.c', 'cpp': '.cpp',
        'cs': '.cs', 'csharp': '.cs',
        'php': '.php',
        'sql': '.sql',
        'json': '.json',
        'xml': '.xml',
        'yaml': '.yaml', 'yml': '.yaml',
        'md': '.md',
        'sh': '.sh', 'bash': '.sh', 'shell': '.sh',
        'txt': '.txt',
        'dockerfile': 'Dockerfile'
    }

    for match in matches:
        lang = (match.group(1) or 'txt').lower()
        content = match.group(2)
        full_block = match.group(0)
        
        # Conta linhas do bloco
        line_count = content.count('\n') + 1
        
        # Ignora blocos curtos (<= 50 linhas) - mantém inline no chat
        if line_count <= 50:
            continue
            
        ext = EXT_MAP.get(lang, '.txt')
        file_count += 1
        
        # Nome inteligente
        filename = f"code_{file_count}{ext}"
        if ext == 'Dockerfile': filename = 'Dockerfile'
        
        try:
            # Cria arquivo temporário
            with tempfile.NamedTemporaryFile(mode='w', suffix=ext, delete=False, encoding='utf-8') as tmp:
                tmp.write(content)
                tmp_path = tmp.name
                
            # Envia arquivo
            await update.message.reply_document(
                document=open(tmp_path, 'rb'),
                filename=filename,
                caption=f"📝 Código extraído ({lang})"
            )
            
            # Limpa temp
            os.remove(tmp_path)
            
            # Remove do texto final (substitui por placeholder discreto)
            clean_text = clean_text.replace(full_block, f"\n📂 *[Arquivo enviado: {filename}]*\n")
            
        except Exception as e:
            logger.error(f"Erro code-to-file: {e}")
            
    return clean_text 

    return clean_text 


async def stream_search_and_reply(update: Update, context: ContextTypes.DEFAULT_TYPE, payload: dict):
    """
    Realiza busca via streaming e atualiza mensagem no Telegram em tempo real.
    """
    user_id = payload.get('user_id')
    config = get_user_config(int(user_id))
    
    # Mensagem inicial (placeholder)
    msg = await update.message.reply_text("🧠 _Pensando..._", parse_mode='Markdown')
    
    full_answer = ""
    thinking_buffer = ""
    citations = []
    status_text = "Iniciando..."
    
    last_update_time = 0
    import time
    
    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            async with client.stream("POST", f"{MCP_API}/search_stream", json=payload) as response:
                if response.status_code != 200:
                    error_text = await response.aread()
                    await msg.edit_text(f"❌ Erro no stream: {error_text.decode()[:200]}")
                    return

                async for line in response.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                        
                    try:
                        data = json.loads(line.replace("data: ", ""))
                        
                        # Atualiza estado local
                        if "status" in data:
                            status_text = data['status']
                        
                        if "thinking" in data:
                            thinking_buffer = data['thinking']
                            status_text = "Raciocinando..."
                            
                        if "citation" in data:
                            citations.append(data['citation'])
                            status_text = f"Encontradas {len(citations)} fontes..."
                            
                        if "chunk" in data:
                            full_answer += data['chunk']
                            status_text = "Escrevendo..."

                        if "clarifying_question" in data:
                            status_text = "❓ Aguardando resposta..."
                            # Poderíamos adicionar um botão aqui se fosse interativo, 
                            # mas por enquanto apenas avisa no status.
                            full_answer += "\n\n❓ *Pergunta de Esclarecimento*: Por favor, responda abaixo para continuar."
                            
                        # Lógica de atualização da UI (Throttling ~1.5s)
                        current_time = time.time()
                        if current_time - last_update_time > 1.5 or "done" in data:
                            # Monta o texto visual
                            display_text = ""
                            
                            # 1. Bloco de Pensamento (Collapsible ou Quote)
                            if thinking_buffer:
                                # Mostra apenas as últimas linhas para não poluir, ou tudo em quote
                                # Vamos mostrar um resumo
                                th_preview = thinking_buffer[-200:].replace("\n", " ")
                                display_text += f"🧠 _{th_preview}._\n\n"
                            
                            # 2. Status e Fontes
                            if not full_answer:
                                display_text += f"🔄 *{status_text}*\n"
                                if citations:
                                    display_text += f"📚 _{len(citations)} fontes lidas_\n"
                            
                            # 3. Resposta Real
                            if full_answer:
                                display_text += full_answer
                            
                            # Adiciona cursor piscando se não acabou
                            if "done" not in data:
                                display_text += " 🟢"
                            
                            # Tenta editar (com tratamento de erro de markdown)
                            try:
                                # Limite do Telegram
                                if len(display_text) > 4000:
                                    display_text = display_text[:4000] + "..."
                                    
                                await msg.edit_text(display_text, parse_mode='Markdown')
                            except Exception:
                                # Fallback para raw em caso de erro de parse
                                try:
                                    await msg.edit_text(display_text)
                                except:
                                    pass
                                    
                            last_update_time = current_time
                            
                        if "done" in data:
                            # Garante que usamos a resposta completa e oficial do backend
                            if 'answer' in data:
                                full_answer = data['answer']
                            break
                            
                    except json.JSONDecodeError:
                        continue

        # Formatação Final Bonita
        final_text = ""
        
        # Opcional: Incluir raciocínio expandido se configurado
        if config['reasoning'] and thinking_buffer:
             final_text += f"🧠 *Raciocínio:*\n_{thinking_buffer}_\n\n---\n\n"
        
        final_text += full_answer
        
        if config['return_citations'] and citations:
            final_text += "\n\n📚 *Fontes:*\n"
            for i, cite in enumerate(citations[:5], 1):
                title = cite.get('title', 'Link')
                url = cite.get('url', '')
                final_text += f"{i}. [{title}]({url})\n"
        
        # 🔗 Footer Informativo (Restaurado)
        model_name = config.get('model', 'best')
        focus_name = config.get('focus', 'web')
        msg_count = data.get('conversation_info', {}).get('message_count', '?')
        footer = f"\n` {model_name} | 🔍 {focus_name} | 💬 {msg_count} msg `"
        final_text += footer
        
        # Só edita se for diferente do que já está (remove o cursor verde)
        try:
            # 1. Tenta extrair e enviar arquivos (isso é PRIORITÁRIO)
            # A função extract_and_send_files agora é robusta e retorna o texto SEM os blocos de código
            clean_text = await extract_and_send_files(update, final_text)
            
            # 2. Atualiza a mensagem final
            await msg.edit_text(clean_text, parse_mode='Markdown', disable_web_page_preview=True)
            
        except Exception as e:
            logger.error(f"Erro ao finalizar msg: {e}")
            # Fallback: Tenta mandar sem markdown se falhar
            try:
                await msg.edit_text(final_text, disable_web_page_preview=True)
            except Exception as e2:
                logger.error(f"Erro fatal ao editar msg final: {e2}")

    except Exception as e:
        logger.error(f"Erro stream handler: {e}")
        await msg.edit_text(f"❌ Erro: {e}")


# ============= COMANDO /local =============

async def cmd_local(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Toggle de localização: liga/desliga busca local"""
    user_id = update.effective_user.id
    config = get_user_config(user_id)
    
    has_location = config.get('lat') is not None and config.get('lon') is not None
    
    if has_location:
        # Remove coords
        config.pop('lat', None)
        config.pop('lon', None)
        save_user_config(user_id, config)
        await update.message.reply_text(
            "📍 *Localização DESATIVADA*\n\n"
            "Suas buscas agora serão globais.\n"
            "Para reativar, envie sua localização pelo 📎 clip.",
            parse_mode='Markdown'
        )
    else:
        # Pede para enviar
        await update.message.reply_text(
            "📍 *Localização não configurada*\n\n"
            "Para ativar buscas locais:\n"
            "1. Clique no 📎 (clip) no Telegram\n"
            "2. Selecione *Localização*\n"
            "3. Envie sua localização atual\n\n"
            "Depois disso, `/local` para desligar.",
            parse_mode='Markdown'
        )


# ============= HANDLER DE LOCALIZAÇÃO =============

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Armazena localização do usuário para buscas locais"""
    user_id = update.effective_user.id
    location = update.message.location
    
    if location:
        config = get_user_config(user_id)
        config['lat'] = location.latitude
        config['lon'] = location.longitude
        save_user_config(user_id, config)
        
        await update.message.reply_text(
            f"📍 *Localização Definida!*\n\n"
            f"Lat: `{location.latitude:.4f}`\n"
            f"Lon: `{location.longitude:.4f}`\n\n"
            f"Próximas buscas usarão esta localização. Para limpar, use /config > Limpar Localização (se houver) ou apenas reinicie.",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text("❌ Erro ao ler localização.")


# ============= COMANDO /token =============

async def cmd_token(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Gerencia tokens do Perplexity (Status, Validação, Rotação)"""
    user_id = update.effective_user.id
    
    # Verifica status via MCP
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{MCP_API}/tokens")
            status = response.json()
    except Exception as e:
        status = {"active": False, "error": str(e)}
    
    # Monta texto de status
    active = status.get('active', False)
    current = status.get('current_account', {})
    total = status.get('total_accounts', 0)
    
    status_emoji = "🟢 Ativo" if active else "🔴 Inativo"
    
    text = (
        f"🔑 *Gerenciador de Tokens*\n\n"
        f"*Status:* {status_emoji}\n"
        f"*Conta Atual:* `{current.get('name', 'N/A')}`\n"
        f"*Total Contas:* {total}\n"
        f"*Fonte:* `{current.get('source', 'N/A')}`\n\n"
        f"_Use os botões abaixo para gerenciar:_"
    )
    
    # Botões
    keyboard = [
        [
            InlineKeyboardButton("✅ Validar Token", callback_data='token_validate'),
            InlineKeyboardButton("🔄 Próximo Token", callback_data='token_rotate')
        ],
        [
            InlineKeyboardButton("✨ Novo Refresh OTP", callback_data='token_new_refresh')
        ],
        [InlineKeyboardButton("« Voltar", callback_data='back_main')]
    ]
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )


async def token_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para ações de token"""
    query = update.callback_query
    data = query.data
    
    if data == 'token_validate':
        await query.answer("Validando token...")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(f"{MCP_API}/tokens/validate")
                result = response.json()
            
            is_valid = result.get('valid', False)
            msg = "✅ Token Válido!" if is_valid else "❌ Token Inválido/Expirado!"
            account = result.get('account', {}).get('name', 'N/A')
            
            await query.edit_message_text(
                f"{msg}\n\nConta: `{account}`",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Voltar", callback_data='token_menu')]]),
                parse_mode='Markdown'
            )
        except Exception as e:
            await query.edit_message_text(f"Erro: {e}")

    elif data == 'token_rotate':
        await query.answer("Rotacionando...")
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(f"{MCP_API}/tokens/rotate")
                result = response.json()
            
            new_acc = result.get('current_account', {}).get('name')
            
            if result.get('rotated'):
                await query.edit_message_text(
                    f"🔄 *Token Rotacionado!*\n\nNova conta: `{new_acc}`",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Voltar", callback_data='token_menu')]]),
                    parse_mode='Markdown'
                )
            else:
                 # Se não rodou, provavelmente só tem 1 conta
                total = result.get('current_account', {}).get('total_accounts', 1)
                if total > 1:
                     msg = "Falha na rotação."
                else:
                     msg = "ℹ️ Apenas uma conta cadastrada. Rotação não necessária."
                
                await query.answer(msg, show_alert=True)
                
        except Exception as e:
            await query.answer(f"Erro: {e}", show_alert=True)

    elif data == 'token_new_refresh':
        # Inicia fluxo de refresh OTP via Telegram
        await query.edit_message_text(
            "📧 *Novo Refresh Token*\n\n"
            "Envie seu email do Perplexity para iniciar.\n"
            "Ex: `user@email.com`\n\n"
            "_Digite /cancelar para abortar._",
            parse_mode='Markdown'
        )
        context.user_data['waiting_for_email'] = True

    elif data == 'token_menu':
        await cmd_token(update, context)


# ============= COMANDO /cancelar =============

async def cmd_cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Cancela operações de token em andamento"""
    if context.user_data.get('waiting_for_email') or context.user_data.get('waiting_for_otp'):
        context.user_data['waiting_for_email'] = False
        context.user_data['waiting_for_otp'] = False
        context.user_data['refresh_email'] = None
        await update.message.reply_text("🚫 Operação cancelada. Estado limpo.")
    else:
        await update.message.reply_text("Nada para cancelar.")


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Processa mensagens de texto (e arquivos pendentes se houver)"""
    user_id = update.effective_user.id
    user_query = update.message.text
    text = user_query
    config = get_user_config(user_id)
    
    # ---------------------------------------------------------
    # FLUXO DE REFRESH TOKEN (EMAIL/OTP)
    # ---------------------------------------------------------
    
    # Nota: Comandos como /cancelar são tratados pelos seus próprios handlers
    # porque este handler usa filtro ~filters.COMMAND no main().

    # Verifica explicitamente se é True (não None ou False)
    if context.user_data.get('waiting_for_email') is True:
        email = text.strip()
        # Validação simples de email
        if '@' not in email or '.' not in email:
            await update.message.reply_text("❌ Email inválido. Tente novamente ou use /cancelar.")
            return

        msg = await update.message.reply_text("🔄 Enviando código de verificação... (isso pode levar alguns segundos)")
        
        try:
            # Chama script de refresh (send-only)
            import subprocess
            # Usa sys.executable para garantir que usa o mesmo python
            cmd = [sys.executable, "scripts/refresh_token.py", "--email", email, "--send-only"]
            
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            if proc.returncode == 0:
                await msg.edit_text(
                    f"✅ Código enviado para `{email}`!\n\n"
                    "📬 Verifique seu email e digite o código OTP (6 dígitos) ou cole o Magic Link aqui:",
                    parse_mode='Markdown'
                )
                context.user_data['waiting_for_email'] = False
                context.user_data['waiting_for_otp'] = True
                context.user_data['refresh_email'] = email
            else:
                err_msg = stderr.decode()
                logger.error(f"Erro refresh send: {err_msg}")
                await msg.edit_text(f"❌ Erro ao enviar código. Verifique se o email está correto.\n\n_Erro: {err_msg.splitlines()[-1] if err_msg else 'Desconhecido'}_", parse_mode='Markdown')
        except Exception as e:
            await msg.edit_text(f"❌ Erro interno: {e}")
        return

    if context.user_data.get('waiting_for_otp') is True:
        otp = text.strip()
        email = context.user_data.get('refresh_email')
        
        msg = await update.message.reply_text("🔐 Validando código e gerando token...")
        
        try:
            # Chama script para validar e salvar
            import subprocess
            cmd = [sys.executable, "scripts/refresh_token.py", "--email", email, "--otp", otp]
            
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            if proc.returncode == 0:
                await msg.edit_text(
                    "✅ *Token Gerado com Sucesso!*\n"
                    "O novo token foi salvo e já está ativo no sistema.\n\n"
                    "Use `/token` para verificar o status.",
                    parse_mode='Markdown'
                )
            else:
                err_msg = stderr.decode()
                logger.error(f"Erro refresh otp: {err_msg}")
                await msg.edit_text(f"❌ Código inválido ou erro na validação.\n\n_Erro: {err_msg.splitlines()[-1] if err_msg else 'Desconhecido'}_", parse_mode='Markdown')
        except Exception as e:
            await msg.edit_text(f"❌ Erro interno: {e}")
        
        context.user_data['waiting_for_otp'] = False
        return
    # ---------------------------------------------------------

    
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    # Verifica se há arquivos pendentes para processar em batch
    if user_id in pending_files and len(pending_files[user_id]) > 0:
        # Processa em batch
        files_to_process = pending_files.pop(user_id)  # Remove do buffer
        await process_files_batch(update, context, user_query, files_to_process, config)
        return
    
    # Fluxo normal (sem arquivos pendentes)
    payload = {
        "query": user_query,
        "user_id": str(user_id),
        "model": config['model'],
        "focus": config['focus'],
        "time_range": config.get('time_range', 'all'),
        "enable_reasoning": config['reasoning'],
        "citation_mode": "markdown"
    }
    
    # Adiciona coordenadas se existirem na config
    if 'lat' in config and 'lon' in config:
        payload['lat'] = config['lat']
        payload['lon'] = config['lon']
    
    # Usa a nova função de streaming
    await stream_search_and_reply(update, context, payload)


async def process_files_batch(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                               query: str, files: list, config: dict) -> None:
    """Processa múltiplos arquivos em uma única request"""
    user_id = update.effective_user.id
    
    msg = await update.message.reply_text(
        f"🔄 *Processando {len(files)} arquivo(s)...*",
        parse_mode='Markdown'
    )
    
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            # Metadados
            data_payload = {
                "query": query,
                "user_id": str(user_id),
                "model": config['model'],
                "focus": "web",
                "return_citations": "false"
            }
            
            # Monta lista de arquivos para multipart
            # Formato: [('file', (nome, bytes, mime)), ('file', ...), ...]
            files_payload = [
                ('file', (f['name'], f['bytes'], f['mime'])) 
                for f in files
            ]
            
            response = await client.post(
                f"{MCP_API}/search",
                data=data_payload,
                files=files_payload
            )
            
            if response.status_code != 200:
                logger.error(f"Erro MCP batch: {response.text}")
                await msg.edit_text(f"❌ Erro ao processar arquivos: {response.status_code}")
                return
            
            data = response.json()
        
        answer = data.get('answer', 'Sem resposta')
        clean_answer = await extract_and_send_files(update, answer)
        
        await msg.delete()
        await reply_chunked(update, clean_answer)
        
    except Exception as e:
        logger.error(f"Erro batch upload: {e}")
        await msg.edit_text(f"❌ Erro: {e}")



# ============= HANDLER DE IMAGENS =============

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Processa imagens enviadas pelo usuário"""
    user_id = update.effective_user.id
    config = get_user_config(user_id)
    
    caption = update.message.caption or "O que você vê nesta imagem?"
    
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    try:
        # Download da imagem
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        
        # Converte para base64
        photo_b64 = base64.b64encode(photo_bytes).decode()
        
        # Chama MCP API com imagem
        async with httpx.AsyncClient(timeout=180.0) as client:
            payload = {
                "query": caption,
                "model": config['model'],
                "image_base64": photo_b64,
                "focus": "web"
            }
            
            response = await client.post(f"{MCP_API}/vision", json=payload)
            response.raise_for_status()
            data = response.json()
        
        answer = data.get('answer', 'Sem resposta')
        await update.message.reply_text(answer, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Erro ao processar imagem: {e}")
        await update.message.reply_text(
            "❌ Erro ao analisar imagem. Tente novamente ou use outro modelo.",
            parse_mode='Markdown'
        )


# ============= HANDLER DE DOCUMENTOS =============

MAX_PENDING_FILES = 9
FILE_TIMEOUT_SECONDS = 120  # 2 minutos

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Acumula arquivos no buffer. Processa quando usuário enviar texto."""
    user_id = update.effective_user.id
    
    document = update.message.document
    file_name = document.file_name or f"arquivo_{document.file_id}"
    mime_type = document.mime_type or "application/octet-stream"
    
    # Lista negra de extensões perigosas
    BLOCKED_EXTENSIONS = ('.exe', '.bat', '.cmd', '.sh', '.bin')
    if file_name.lower().endswith(BLOCKED_EXTENSIONS):
        await update.message.reply_text("⚠️ Tipo de arquivo não permitido por segurança.")
        return
    
    try:
        # Download do arquivo
        telegram_file = await document.get_file()
        file_bytes = await telegram_file.download_as_bytearray()
        
        # Inicializa buffer se não existe
        if user_id not in pending_files:
            pending_files[user_id] = []
        
        # Limpa arquivos antigos (timeout)
        current_time = time.time()
        pending_files[user_id] = [
            f for f in pending_files[user_id] 
            if current_time - f['timestamp'] < FILE_TIMEOUT_SECONDS
        ]
        
        # Verifica limite
        if len(pending_files[user_id]) >= MAX_PENDING_FILES:
            await update.message.reply_text(
                f"⚠️ Limite de {MAX_PENDING_FILES} arquivos atingido.\n"
                "Envie sua pergunta para processar ou use /limpar para recomeçar."
            )
            return
        
        # Adiciona ao buffer
        pending_files[user_id].append({
            'name': file_name,
            'bytes': bytes(file_bytes),
            'mime': mime_type,
            'timestamp': current_time
        })
        
        count = len(pending_files[user_id])
        file_list = "\n".join([f"  • {f['name']}" for f in pending_files[user_id]])
        
        await update.message.reply_text(
            f"📎 *{count} arquivo(s) recebido(s):*\n{file_list}\n\n"
            f"Envie mais arquivos (até {MAX_PENDING_FILES}) ou digite sua pergunta para processar.",
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Erro ao receber documento: {e}")
        await update.message.reply_text(f"❌ Erro ao receber arquivo: {e}")


# ============= POST INIT =============

async def post_init(application: Application) -> None:
    """Executado após a inicialização da aplicação, dentro do loop de eventos"""
    logger.info("🚀 Executando post_init...")
    
    # Inicia Scheduler (agora que temos loop)
    tm = get_task_manager()
    if tm and tm.scheduler:
        try:
            tm.scheduler.start()
            logger.info("📅 APScheduler iniciado com sucesso!")
        except Exception as e:
            logger.warning(f"⚠️ Scheduler já rodando ou erro: {e}")

    # Define comandos
    await application.bot.set_my_commands([
        BotCommand("start", "Menu Principal"),
        BotCommand("busca", "Nova Busca"),
        BotCommand("new", "Nova Conversa"),
        BotCommand("vpn", "Controle VPN"),
        BotCommand("tarefas", "Gerenciar Tarefas"),
        BotCommand("modelos", "Trocar Modelo"),
        BotCommand("config", "Configurações"),
        BotCommand("ajuda", "Ajuda")
    ])
    logger.info("✅ Comandos registrados no Telegram")


# ============= MAIN =============

def main() -> None:
    """Inicia o bot"""
    logger.info("🚀 Iniciando Perplexo Bot...")
    
    # Inicializa APScheduler se disponível
    scheduler = None
    if SCHEDULER_AVAILABLE:
        scheduler = AsyncIOScheduler()
        # scheduler.start()  <-- Removido: Seráiciado no post_init
        logger.info("📅 APScheduler inicializado (aguardando start)")
    
    # Callback para executar tarefas agendadas
    async def execute_scheduled_task(user_id: int, task: Task):
        """Callback executado pelo scheduler quando uma tarefa dispara"""
        logger.info(f"⏰ Executando tarefa agendada: {task.name} para user {user_id}")
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{MCP_API}/search_stream",
                    json={
                        "query": task.prompt,
                        "user_id": str(user_id),
                        "model": task.model,
                        "focus": "web"
                    }
                )
                
                if response.status_code == 200:
                    # Processa resposta do stream
                    full_answer = ""
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            try:
                                data = json.loads(line[6:])
                                if "chunk" in data:
                                    full_answer += data['chunk']
                                if "answer" in data:
                                    full_answer = data['answer']
                            except:
                                pass
                    
                    # Envia notificação via Telegram
                    from telegram import Bot
                    bot = Bot(token=TELEGRAM_TOKEN)
                    msg_text = f"📋 *Tarefa: {task.name}*\n\n{full_answer[:3900]}"
                    await bot.send_message(
                        chat_id=user_id,
                        text=msg_text,
                        parse_mode='Markdown'
                    )
                    logger.info(f"✅ Notificação enviada para {user_id}")
        except Exception as e:
            logger.error(f"Erro ao executar tarefa {task.task_id}: {e}")
    
    # Inicializa TaskManager com scheduler
    init_task_manager(scheduler=scheduler, execute_callback=execute_scheduled_task)
    logger.info("📋 TaskManager inicializado")
    
    # Cria aplicação
    app = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()
    
    # Comandos
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("modelos", cmd_modelos))
    app.add_handler(CommandHandler("busca", cmd_busca))
    app.add_handler(CommandHandler("denovo", cmd_denovo))
    app.add_handler(CommandHandler("tarefas", cmd_tarefas))
    app.add_handler(CommandHandler("local", cmd_local))
    app.add_handler(CommandHandler("new", cmd_new))
    app.add_handler(CommandHandler("library", cmd_library))
    app.add_handler(CommandHandler("vpn", cmd_vpn))
    app.add_handler(CommandHandler("token", cmd_token))
    app.add_handler(CommandHandler("cancelar", cmd_cancelar))

    app.add_handler(CommandHandler("historico", cmd_historico))
    app.add_handler(CommandHandler("teste", cmd_teste))
    app.add_handler(CommandHandler("importar", cmd_importar))
    app.add_handler(CommandHandler("normal", cmd_normal))
    app.add_handler(CommandHandler("config", cmd_config))
    app.add_handler(CommandHandler("limpar", cmd_limpar))
    app.add_handler(CommandHandler("tempo", cmd_tempo))
    app.add_handler(CommandHandler("ajuda", cmd_ajuda))
    
    # Callbacks (botões inline)
    app.add_handler(CallbackQueryHandler(token_callback_handler, pattern="^token_"))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    # Mensagens
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    
    # Webhook ou Polling
    if WEBHOOK_URL:
        logger.info(f"📡 Modo Webhook: {WEBHOOK_URL}")
        app.run_webhook(
            listen="127.0.0.1",
            port=TELEGRAM_PORT,
            webhook_url=WEBHOOK_URL,
            url_path="/telegram"
        )
    else:
        logger.info("🔄 Modo Polling (desenvolvimento)")
        app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
