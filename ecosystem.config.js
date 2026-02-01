/**
 * PM2 Ecosystem Configuration
 * Gerencia todos os processos do Perplexo Bot
 * 
 * Uso:
 *   pm2 start ecosystem.config.js
 *   pm2 logs
 *   pm2 status
 */

module.exports = {
  apps: [
    {
      name: 'perplexity-mcp',
      script: 'src/perplexity_mcp.py',
      interpreter: 'python3',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '500M',
      env: {
        FLASK_ENV: 'production',
        MCP_PORT: 5000
      },
      error_file: 'logs/mcp-error.log',
      out_file: 'logs/mcp-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
    },
    {
      name: 'telegram-bot',
      script: 'src/telegram_bot.py',
      interpreter: 'python3',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '300M',
      env: {
        TELEGRAM_PORT: 8000
      },
      error_file: 'logs/telegram-error.log',
      out_file: 'logs/telegram-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
    },
    {
      name: 'whatsapp-bot',
      script: 'src/whatsapp_bot.js',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '500M',
      env: {
        NODE_ENV: 'production',
        WHATSAPP_PORT: 3000
      },
      error_file: 'logs/whatsapp-error.log',
      out_file: 'logs/whatsapp-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
    }
  ]
};
