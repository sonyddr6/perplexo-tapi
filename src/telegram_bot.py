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


# ============= SETUP DOS COMANDOS =============

async def post_init(application: Application) -> None:
    """Registra comandos no menu do Telegram"""
    commands = [
        BotCommand("start", "🏠 Menu Principal"),
        BotCommand("modelos", "🤖 Escolher Modelo AI"),
        BotCommand("busca", "🔍 Modo de Busca (Focus)"),
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
        async with httpx.AsyncClient(timeout=60.0) as client:
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
    
    # Toggles de config
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

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Processa mensagens de texto"""
    user_id = update.effective_user.id
    user_query = update.message.text
    config = get_user_config(user_id)
    
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            payload = {
                "query": user_query,
                "user_id": str(user_id),  # HISTÓRICO NATIVO!
                "model": config['model'],
                "focus": config['focus'],
                "enable_reasoning": config['reasoning'],
                "return_citations": config['return_citations'],
                "return_images": config['return_images']
            }
            
            response = await client.post(f"{MCP_API}/search", json=payload)
            response.raise_for_status()
            data = response.json()
        
        answer = data.get('answer', 'Sem resposta')
        thinking = data.get('thinking')
        conv_info = data.get('conversation_info', {})
        
        # Se tem thinking (raciocínio), mostra primeiro
        if thinking and data.get('has_thinking'):
            thinking_text = f"🧠 *Raciocínio interno:*\n_{thinking[:1500]}{'...' if len(thinking) > 1500 else ''}_\n\n---\n\n"
            await update.message.reply_text(
                thinking_text,
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
        
        # Adiciona citações se ativado
        if config['return_citations'] and data.get('citations'):
            answer += "\n\n📚 *Fontes:*\n"
            for i, cite in enumerate(data['citations'][:5], 1):
                title = cite.get('title', 'Link')
                url = cite.get('url', '')
                answer += f"{i}. [{title}]({url})\n"
        
        # Badge de metadados com contador de mensagens nativo
        msg_count = conv_info.get('message_count', 0)
        thinking_badge = "🧠 " if data.get('has_thinking') else ""
        is_new = "🌟 " if conv_info.get('is_new') else ""
        answer += f"\n_{is_new}{thinking_badge}🤖 {data.get('model_used', config['model'])} | 🔍 {data.get('focus_mode', config['focus'])} | 💬 {msg_count} msg_"
        
        await update.message.reply_text(
            answer,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
        
        # Envia imagens se retornadas
        if config['return_images'] and data.get('images'):
            for img_url in data['images'][:3]:
                try:
                    await update.message.reply_photo(photo=img_url)
                except Exception as e:
                    logger.warning(f"Erro ao enviar imagem: {e}")
        
    except httpx.ConnectError:
        await update.message.reply_text(
            "❌ *Erro de conexão*\n\n"
            "O servidor MCP não está respondendo.\n"
            "Verifique se `perplexity_mcp.py` está rodando.",
            parse_mode='Markdown'
        )
    except httpx.TimeoutException:
        await update.message.reply_text(
            "⏱️ *Timeout*\n\n"
            "A busca demorou muito. Tente um modelo mais rápido (`/modelos`).",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Erro: {e}")
        await update.message.reply_text(
            "❌ Erro ao processar. Use /config para verificar suas configurações.",
            parse_mode='Markdown'
        )


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
        async with httpx.AsyncClient(timeout=90.0) as client:
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
    file_name = document.file_name
    
    # Só aceita .txt por enquanto
    if not file_name.endswith('.txt'):
        await update.message.reply_text(
            "⚠️ Por enquanto só aceito arquivos `.txt`\n"
            "Envie um arquivo de texto para resumir.",
            parse_mode='Markdown'
        )
        return
    
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    try:
        # Download do arquivo
        file = await document.get_file()
        file_bytes = await file.download_as_bytearray()
        
        try:
            text_content = file_bytes.decode('utf-8')
        except UnicodeDecodeError:
            text_content = file_bytes.decode('latin-1')
        
        # Limita tamanho (10KB máx)
        if len(text_content) > 10000:
            text_content = text_content[:10000] + "\n[...truncado]"
        
        # Chama MCP API
        query = f"Resuma o seguinte texto:\n\n{text_content}"
        
        async with httpx.AsyncClient(timeout=90.0) as client:
            payload = {
                "query": query,
                "model": config['model'],
                "focus": "writing",
                "return_citations": False
            }
            
            response = await client.post(f"{MCP_API}/search", json=payload)
            response.raise_for_status()
            data = response.json()
        
        answer = f"📄 *Resumo de {file_name}:*\n\n{data.get('answer', 'Sem resposta')}"
        await update.message.reply_text(answer, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Erro ao processar documento: {e}")
        await update.message.reply_text(
            "❌ Erro ao processar arquivo. Verifique se é UTF-8.",
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
    app.add_handler(CommandHandler("new", cmd_new))
    app.add_handler(CommandHandler("new", cmd_new))
    app.add_handler(CommandHandler("library", cmd_library))
    app.add_handler(CommandHandler("token", cmd_token))
    app.add_handler(CommandHandler("historico", cmd_historico))
    app.add_handler(CommandHandler("teste", cmd_teste))
    app.add_handler(CommandHandler("importar", cmd_importar))
    app.add_handler(CommandHandler("normal", cmd_normal))
    app.add_handler(CommandHandler("config", cmd_config))
    app.add_handler(CommandHandler("limpar", cmd_limpar))
    app.add_handler(CommandHandler("ajuda", cmd_ajuda))
    
    # Callbacks (botões inline)
    app.add_handler(CallbackQueryHandler(button_handler))
    
    # Mensagens
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.TEXT, handle_document))
    
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
