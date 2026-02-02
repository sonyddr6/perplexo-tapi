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
from typing import Dict, Any, Optional

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
TELEGRAM_PORT = int(os.getenv("TELEGRAM_PORT", 8000))

# Verifica token
if not TELEGRAM_TOKEN or TELEGRAM_TOKEN == "seu_token_aqui":
    logger.error("❌ TELEGRAM_TOKEN não configurado! Edite o arquivo .env")
    sys.exit(1)

# ============= STORAGE DE PREFERÊNCIAS =============
# Em produção, substitua por Redis ou banco de dados

user_preferences: Dict[int, Dict[str, Any]] = {}


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
            InlineKeyboardButton("🤖 Modelo", callback_data='menu_modelos'),
            InlineKeyboardButton("🔍 Busca", callback_data='menu_busca')
        ],
        [
            InlineKeyboardButton("💬 Normal", callback_data='menu_normal'),
            InlineKeyboardButton("⚙️ Config", callback_data='menu_config')
        ],
        [InlineKeyboardButton("❓ Ajuda", callback_data='menu_ajuda')]
    ]
    
    text = (
        f"🌀 *Perplexo Bot* - Perplexity AI 2026\n\n"
        f"*Configuração Atual:*\n"
        f"🤖 Modelo: `{config['model']}`\n"
        f"🔍 Focus: `{config['focus']}`\n"
        f"💬 Modo: `{config['mode']}`\n\n"
        f"_Envie sua pergunta ou use os botões abaixo:_"
    )
    
    if update.message:
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    elif update.callback_query:
        await update.callback_query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )


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
        
        await update.message.reply_text(msg_text, parse_mode='Markdown')
    except Exception:
        await update.message.reply_text(
            "✨ *Nova conversa iniciada!*\n\n"
            "Me pergunte qualquer coisa! 🚀",
            parse_mode='Markdown'
        )


# ============= COMANDO /historico =============

async def cmd_historico(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lista conversas salvas"""
    user_id = update.effective_user.id
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{MCP_API}/history/list", params={"user_id": str(user_id)})
            data = response.json()
            
        conversations = data.get('conversations', [])
        
        if not conversations:
            await update.message.reply_text(
                "📂 *Seu histórico está vazio.*\n\n"
                "Use `/new` para criar novas conversas e elas serão salvas automaticamente ao limpar.",
                parse_mode='Markdown'
            )
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
            
        keyboard.append([InlineKeyboardButton("« Cancelar", callback_data='back_main')])
        
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Erro ao listar histórico: {e}")
        await update.message.reply_text("❌ Erro ao buscar histórico.", parse_mode='Markdown')



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
                text = f"☁️ *{msg}*\n\n⚠️ Atenção: Se estiver usando VPN/Datacenter, isso pode gerar erro 403 (Token Inválido).\nSe der ruim, use `/library` de novo para desativar."
            else:
                text = f"🏠 *{msg}*\n\nModo seguro (Local) ativado. Conversas salvas apenas no JSON interno."
            
            await update.message.reply_text(text, parse_mode='Markdown')
            
    except Exception as e:
        logger.error(f"Erro library toggle: {e}")
        await update.message.reply_text("❌ Erro ao alterar configuração.", parse_mode='Markdown')


# ============= COMANDO /token =============
async def cmd_token(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Atualiza o Token de Sessão Dinamicamente"""
    user_id = update.effective_user.id
    
    if not context.args:
        await update.message.reply_text("⚠️ Use: `/token <seu_novo_token_aqui>`")
        return
        
    token = context.args[0]
    
    # Tenta apagar a mensagem do usuário por segurança
    try:
        await update.message.delete()
    except:
        pass # Pode não ter permissão
        
    msg = await update.message.reply_text("🔑 *Atualizando Token...*", parse_mode='Markdown')
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(f"{MCP_API}/config/token", json={"token": token})
            
            if response.status_code == 200:
                await msg.edit_text("✅ *Token Atualizado com Sucesso!*\nExecutando diagnóstico automático...", parse_mode='Markdown')
                # Chama o diagnóstico
                await cmd_teste(update, context)
            else:
                await msg.edit_text(f"❌ Erro ao atualizar: {response.text}", parse_mode='Markdown')
                
    except Exception as e:
        logger.error(f"Erro token update: {e}")
        await msg.edit_text("❌ Erro de conexão com MCP.", parse_mode='Markdown')


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
    await query.answer()
    
    user_id = update.effective_user.id
    data = query.data
    
    # Navegação
    if data == 'back_main':
        await start(update, context)
        return
    
    # Menus
    if data == 'menu_modelos':
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
        
        # Ignora blocos muito pequenos (menos de 50 chars) para evitar spam
        if len(content) < 50:
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


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Processa mensagens de texto"""
    user_id = update.effective_user.id
    user_query = update.message.text
    config = get_user_config(user_id)
    
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    payload = {
        "query": user_query,
        "user_id": str(user_id),
        "model": config['model'],
        "focus": config['focus'],
        "time_range": config.get('time_range', 'all'),
        "enable_reasoning": config['reasoning'], # Não usado no stream ainda mas mantido
        "time_range": config.get('time_range', 'all'),
        "enable_reasoning": config['reasoning'], # Não usado no stream ainda mas mantido
        "citation_mode": "markdown"
    }
    
    # Adiciona coordenadas se existirem na config
    if 'lat' in config and 'lon' in config:
        payload['lat'] = config['lat']
        payload['lon'] = config['lon']
        # Feedback visual sutil (opcional)
        # await update.message.reply_text("📍 Usando sua localização", disable_notification=True)
    
    # Usa a nova função de streaming
    await stream_search_and_reply(update, context, payload)


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

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Processa arquivos de texto"""
    user_id = update.effective_user.id
    config = get_user_config(user_id)
    
    document = update.message.document
    file_name = document.file_name or f"arquivo_{document.file_id}"
    mime_type = document.mime_type or "application/octet-stream"
    
    # Lista negra de extensões perigosas (opcional, mas bom pra segurança)
    BLOCKED_EXTENSIONS = ('.exe', '.bat', '.cmd', '.sh', '.bin')
    if file_name.lower().endswith(BLOCKED_EXTENSIONS):
        await update.message.reply_text("⚠️ Tipo de arquivo não permitido por segurança.")
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="upload_document")
    
    try:
        # Download do arquivo (em memória)
        telegram_file = await document.get_file()
        file_bytes = await telegram_file.download_as_bytearray()
        
        # Prepara a query
        user_query = update.message.caption or f"Analise o arquivo {file_name}"
        
        # Envia para MCP via Multipart Upload
        async with httpx.AsyncClient(timeout=300.0) as client:  # 5 min para uploads grandes
            # Metadados como campos de formulário
            data_payload = {
                "query": user_query,
                "user_id": str(user_id),
                "model": config['model'],
                "focus": "web",
                "return_citations": "false" # string para form-data
            }
            
            # Arquivo
            files_payload = {
                'file': (file_name, file_bytes, mime_type)
            }
            
            # POST /search (agora aceita multipart)
            response = await client.post(
                f"{MCP_API}/search",
                data=data_payload,
                files=files_payload
            )
            
            # Verifica erro
            if response.status_code != 200:
                logger.error(f"Erro MCP: {response.text}")
                raise Exception(f"MCP retornou erro {response.status_code}")
                
            data = response.json()
        
        # Processa a resposta
        answer = data.get('answer', 'Sem resposta')
        clean_answer = await extract_and_send_files(update, answer)
        await reply_chunked(update, clean_answer)
        
    except Exception as e:
        logger.error(f"Erro ao processar documento: {e}")
        await update.message.reply_text(
            f"❌ Erro ao enviar arquivo: {e}",
            parse_mode='Markdown'
        )


# ============= MAIN =============

def main() -> None:
    """Inicia o bot"""
    logger.info("🚀 Iniciando Perplexo Bot...")
    
    # Cria aplicação
    app = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()
    
    # Comandos
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("modelos", cmd_modelos))
    app.add_handler(CommandHandler("busca", cmd_busca))
    app.add_handler(CommandHandler("denovo", cmd_denovo))
    app.add_handler(CommandHandler("new", cmd_new))
    app.add_handler(CommandHandler("library", cmd_library))
    app.add_handler(CommandHandler("token", cmd_token))
    app.add_handler(CommandHandler("historico", cmd_historico))
    app.add_handler(CommandHandler("teste", cmd_teste))
    app.add_handler(CommandHandler("importar", cmd_importar))
    app.add_handler(CommandHandler("normal", cmd_normal))
    app.add_handler(CommandHandler("config", cmd_config))
    app.add_handler(CommandHandler("limpar", cmd_limpar))
    app.add_handler(CommandHandler("tempo", cmd_tempo))
    app.add_handler(CommandHandler("ajuda", cmd_ajuda))
    
    # Callbacks (botões inline)
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
