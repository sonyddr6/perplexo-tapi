/**
 * Perplexo Bot - WhatsApp
 * =======================
 * Bot completo para WhatsApp usando Baileys.
 * 
 * Recursos:
 * - Conexão persistente com QR code
 * - Menu textual interativo
 * - Integração com MCP Server
 * - Reconexão automática
 * 
 * Uso:
 *   node src/whatsapp_bot.js
 */

const {
    default: makeWASocket,
    DisconnectReason,
    useMultiFileAuthState,
    fetchLatestBaileysVersion
} = require('@whiskeysockets/baileys');
const axios = require('axios');
const pino = require('pino');
const qrcode = require('qrcode-terminal');
require('dotenv').config();

// ============= CONFIGURAÇÃO =============

const MCP_API = process.env.MCP_API_URL || 'http://127.0.0.1:5000';
const AUTH_FOLDER = './auth_info_baileys';

// Logger silencioso (ajuste para 'debug' para troubleshooting)
const logger = pino({ level: 'silent' });

// Storage de preferências por usuário (em produção: use Redis)
const userPreferences = new Map();

// ============= MODELOS E FOCUS =============

const MODELS = {
    best: '🎯 Best (Auto)',
    sonar: '⚡ Sonar (Perplexity)',
    'deep-research': '📊 Deep Research',
    'gpt-5.2': '🧠 GPT-5.2 (OpenAI)',
    'gpt-5.2-thinking': '🧠💭 GPT-5.2 Thinking',
    'claude-4.5-sonnet': '🎭 Claude Sonnet',
    'claude-4.5-opus': '🎭✨ Claude Opus',
    'gemini-3-flash': '💎 Gemini Flash',
    'gemini-3-pro-thinking': '💎🔥 Gemini Pro',
    'grok-4.1': '🚀 Grok 4.1 (xAI)',
    'kimi-k2.5-thinking': '🌙 Kimi K2.5'
};

const FOCUS_MODES = {
    web: '🌐 Web (Geral)',
    academic: '🎓 Academic (Papers)',
    writing: '✍️ Writing (Escrita)',
    youtube: '🎥 YouTube (Vídeos)',
    reddit: '💬 Reddit (Discussões)',
    wolfram: '🧮 Wolfram (Matemática)'
};

// ============= FUNÇÕES AUXILIARES =============

function getUserConfig(userId) {
    return userPreferences.get(userId) || {
        model: 'sonar',
        focus: 'web',
        mode: 'busca'
    };
}

function saveUserConfig(userId, config) {
    userPreferences.set(userId, config);
}

function generateMenu() {
    return `🌀 *Perplexo Bot - WhatsApp*

Comandos disponíveis:

*1* - 🤖 Ver/Trocar Modelo
*2* - 🔍 Ver/Trocar Focus
*3* - ⚙️ Ver Configurações
*0* - ℹ️ Ajuda

Ou envie sua pergunta diretamente!`;
}

function generateModelMenu(currentModel) {
    let text = '🤖 *Escolher Modelo AI*\n\n';
    let i = 1;
    for (const [id, name] of Object.entries(MODELS)) {
        const marker = id === currentModel ? '✅' : `${i}`;
        text += `${marker} - ${name}\n`;
        i++;
    }
    text += '\nEnvie o número do modelo desejado.';
    return text;
}

function generateFocusMenu(currentFocus) {
    let text = '🔍 *Modo de Busca (Focus)*\n\n';
    let i = 1;
    for (const [id, name] of Object.entries(FOCUS_MODES)) {
        const marker = id === currentFocus ? '✅' : `${i}`;
        text += `${marker} - ${name}\n`;
        i++;
    }
    text += '\nEnvie o número do focus desejado.';
    return text;
}

function generateConfigText(config) {
    return `⚙️ *Suas Configurações*

🤖 Modelo: *${MODELS[config.model] || config.model}*
🔍 Focus: *${FOCUS_MODES[config.focus] || config.focus}*
💬 Modo: *${config.mode}*

Para alterar, envie:
*1* - Trocar modelo
*2* - Trocar focus`;
}

function generateHelpText() {
    return `ℹ️ *Ajuda - Perplexo Bot*

*Como usar:*
• Envie qualquer pergunta para pesquisar
• Use números para navegar nos menus

*Comandos:*
• *1* - Escolher modelo AI
• *2* - Escolher focus de busca
• *3* - Ver configurações
• *0* - Esta ajuda

*Modelos disponíveis:*
🎯 Best, ⚡ Sonar, 📊 Deep Research
🧠 GPT-5.2, 🎭 Claude 4.5, 💎 Gemini 3
🚀 Grok 4.1, 🌙 Kimi K2.5

*Focus disponíveis:*
🌐 Web, 🎓 Academic, ✍️ Writing
🎥 YouTube, 💬 Reddit, 🧮 Wolfram`;
}

// ============= CHAMADA À API =============

async function searchPerplexity(query, config) {
    try {
        const response = await axios.post(`${MCP_API}/search`, {
            query,
            model: config.model,
            focus: config.focus,
            enable_reasoning: false,
            return_citations: true
        }, {
            timeout: 60000
        });

        const data = response.data;
        let answer = data.answer || 'Sem resposta';

        // Adiciona citações
        if (data.citations && data.citations.length > 0) {
            answer += '\n\n📚 *Fontes:*\n';
            data.citations.slice(0, 3).forEach((cite, i) => {
                answer += `${i + 1}. ${cite.title}: ${cite.url}\n`;
            });
        }

        // Badge de metadados
        answer += `\n_🤖 ${data.model_used} | 🔍 ${data.focus_mode}_`;

        return answer;

    } catch (error) {
        console.error('Erro na API:', error.message);

        if (error.code === 'ECONNREFUSED') {
            return '❌ *Erro de conexão*\n\nO servidor MCP não está respondendo.\nVerifique se `perplexity_mcp.py` está rodando.';
        }

        return `❌ Erro ao processar: ${error.message}`;
    }
}

// ============= CONEXÃO WHATSAPP =============

async function connectToWhatsApp() {
    const { state, saveCreds } = await useMultiFileAuthState(AUTH_FOLDER);
    const { version } = await fetchLatestBaileysVersion();

    console.log('📱 Conectando ao WhatsApp...');
    console.log(`📦 Versão Baileys: ${version.join('.')}`);

    const sock = makeWASocket({
        version,
        auth: state,
        printQRInTerminal: false,  // Usamos qrcode-terminal customizado
        logger,
        browser: ['Perplexo Bot', 'Chrome', '121.0.0']
    });

    // Salva credenciais quando atualizadas
    sock.ev.on('creds.update', saveCreds);

    // Eventos de conexão
    sock.ev.on('connection.update', async (update) => {
        const { connection, lastDisconnect, qr } = update;

        // Exibe QR code no terminal
        if (qr) {
            console.log('\n📲 Escaneie o QR Code abaixo com seu WhatsApp:\n');
            qrcode.generate(qr, { small: true });
        }

        if (connection === 'open') {
            console.log('\n✅ Conectado ao WhatsApp!');
            console.log('🤖 Perplexo Bot está pronto para receber mensagens.\n');
        }

        if (connection === 'close') {
            const statusCode = lastDisconnect?.error?.output?.statusCode;
            const shouldReconnect = statusCode !== DisconnectReason.loggedOut;

            console.log(`❌ Conexão fechada. Código: ${statusCode}`);

            if (shouldReconnect) {
                console.log('🔄 Reconectando em 5 segundos...');
                setTimeout(connectToWhatsApp, 5000);
            } else {
                console.log('🚪 Desconectado (logout). Exclua a pasta auth_info_baileys e reconecte.');
            }
        }
    });

    // Processa mensagens recebidas
    sock.ev.on('messages.upsert', async ({ messages }) => {
        const msg = messages[0];

        // Ignora mensagens próprias, notificações, etc.
        if (!msg.message) return;
        if (msg.key.fromMe) return;
        if (msg.key.remoteJid.endsWith('@g.us')) return; // Ignora grupos por padrão

        const userId = msg.key.remoteJid;
        const messageText = msg.message.conversation ||
            msg.message.extendedTextMessage?.text ||
            '';

        if (!messageText.trim()) return;

        console.log(`📩 Mensagem de ${userId}: ${messageText.substring(0, 50)}...`);

        const config = getUserConfig(userId);
        let response = '';

        // Processa comandos de menu
        const text = messageText.trim().toLowerCase();

        // Menu principal
        if (text === 'menu' || text === '/start') {
            response = generateMenu();
        }
        // Ajuda
        else if (text === '0' || text === 'ajuda') {
            response = generateHelpText();
        }
        // Menu de modelos
        else if (text === '1' || text === 'modelos') {
            config.menuState = 'models';
            saveUserConfig(userId, config);
            response = generateModelMenu(config.model);
        }
        // Menu de focus
        else if (text === '2' || text === 'busca' || text === 'focus') {
            config.menuState = 'focus';
            saveUserConfig(userId, config);
            response = generateFocusMenu(config.focus);
        }
        // Ver configurações
        else if (text === '3' || text === 'config') {
            response = generateConfigText(config);
        }
        // Seleção de modelo (se estiver no menu de modelos)
        else if (config.menuState === 'models' && /^([1-9]|1[0-1])$/.test(text)) {
            const modelIds = Object.keys(MODELS);
            const selectedModel = modelIds[parseInt(text) - 1];
            if (selectedModel) {
                config.model = selectedModel;
                config.menuState = null;
                saveUserConfig(userId, config);
                response = `✅ Modelo alterado para *${MODELS[selectedModel]}*\n\nAgora envie sua pergunta!`;
            }
        }
        // Seleção de focus (se estiver no menu de focus)
        else if (config.menuState === 'focus' && /^[1-6]$/.test(text)) {
            const focusIds = Object.keys(FOCUS_MODES);
            const selectedFocus = focusIds[parseInt(text) - 1];
            if (selectedFocus) {
                config.focus = selectedFocus;
                config.menuState = null;
                saveUserConfig(userId, config);
                response = `✅ Focus alterado para *${FOCUS_MODES[selectedFocus]}*\n\nAgora envie sua pergunta!`;
            }
        }
        // Pergunta normal → buscar no Perplexity
        else {
            config.menuState = null;
            saveUserConfig(userId, config);

            // Envia indicador de "digitando"
            await sock.sendPresenceUpdate('composing', userId);

            response = await searchPerplexity(messageText, config);
        }

        // Envia resposta
        if (response) {
            await sock.sendMessage(userId, { text: response });
            console.log(`📤 Resposta enviada para ${userId}`);
        }
    });

    return sock;
}

// ============= MAIN =============

async function main() {
    console.log('🌀 Perplexo Bot - WhatsApp');
    console.log('==========================\n');

    try {
        await connectToWhatsApp();
    } catch (error) {
        console.error('❌ Erro fatal:', error);
        process.exit(1);
    }
}

main();
