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
        BotCommand("normal", "💬 Conversa Normal"),
        BotCommand("config", "⚙️ Configurações"),
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
        "• `/config` - Configurações avançadas\n\n"
        "*Recursos:*\n"
        "• Envie texto para perguntas\n"
        "• Envie imagens para análise visual\n"
        "• Envie arquivos .txt para resumir\n\n"
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
        
        # Adiciona citações se ativado
        if config['return_citations'] and data.get('citations'):
            answer += "\n\n📚 *Fontes:*\n"
            for i, cite in enumerate(data['citations'][:5], 1):
                title = cite.get('title', 'Link')
                url = cite.get('url', '')
                answer += f"{i}. [{title}]({url})\n"
        
        # Badge de metadados
        answer += f"\n_🤖 {data.get('model_used', config['model'])} | 🔍 {data.get('focus_mode', config['focus'])}_"
        
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
    app.add_handler(CommandHandler("normal", cmd_normal))
    app.add_handler(CommandHandler("config", cmd_config))
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
