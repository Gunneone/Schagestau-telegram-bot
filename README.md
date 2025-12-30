# Schagestau Telegram Bot

An automated news digest bot that fetches news from the Tagesschau API, ranks them by importance using OpenAI, and sends curated summaries to a Telegram channel.

## 🚀 Quick Start (5 Minutes)

### Option 1: Docker (Recommended)

```bash
# 1. Setup
git clone <repo-url>
cd schagestau-telegram
cp .env.example .env
# Edit .env with your API keys

# 2. Run
docker-compose up -d

# 3. Check logs
docker-compose logs -f
```

### Option 2: Python

```bash
# 1. Setup
git clone <repo-url>
cd schagestau-telegram
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 2. Install & Configure
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys

# 3. Initialize & Run
python scripts/init_db.py
python main.py
```

---

## Overview

This bot runs on a configurable schedule (default: 8 AM and 9 PM daily), fetches all news articles since the last run, uses an OpenAI LLM to rank them by importance, selects the top 3 most important pieces, generates concise summaries, and sends a formatted digest to a Telegram channel.

## Features

- **Automated Scheduling**: Configurable fetch times (default: 8 AM and 9 PM)
- **Manual Trigger**: Send `/fire` to bot for instant digest of last 12 hours
- **Incremental Fetching**: Only fetches news since the last successful run
- **AI-Powered Ranking**: Uses OpenAI LLM to evaluate and rank news by importance
- **Concise Summaries**: Generates max 3-sentence summaries for each selected article
- **Telegram Integration**: Automatically posts formatted digests to a Telegram channel
- **German Language**: All output and LLM prompts are in German
- **Fully Configurable**: All settings managed via `.env` file
- **Docker Ready**: Production-ready Docker Compose setup

## Configuration

### Required Settings

Create a `.env` file from `.env.example`:

```env
# OpenAI Configuration
OPENAI_API_KEY=sk-...                    # Get from https://platform.openai.com/
OPENAI_MODEL=gpt-4o-mini                 # Recommended: gpt-4o-mini
OPENAI_TEMPERATURE=0.3
OPENAI_MAX_TOKENS=2000

# Telegram Configuration
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...     # Get from @BotFather
TELEGRAM_CHANNEL_ID=@your_channel        # Channel username or -1001234567890

# Schedule Configuration
FETCH_TIMES=08:00,21:00                  # Comma-separated times (24-hour)
TIMEZONE=Europe/Berlin

# Storage
LAST_FETCH_FILE=last_fetch.json
LOG_FILE=bot.log
LOG_LEVEL=INFO

# Optional: News Selection
NEWS_COUNT=3
MAX_SUMMARY_SENTENCES=3
```

### Setup Telegram

1. **Create Bot**: Message @BotFather → `/newbot` → Save token
2. **Create Channel**: Create channel → Add bot as admin
3. **Get Channel ID**: 
   - Public: use `@channel_name`
   - Private: run `python scripts/get_channel_id.py`

### Setup OpenAI

1. **Get API Key**: https://platform.openai.com/ → API Keys
2. **Choose Model**:
   - `gpt-4o-mini`: Best balance (recommended, ~$0.06/month)
   - `gpt-4o`: Highest quality (more expensive)
   - `gpt-3.5-turbo`: Cheapest, fastest

## Usage

### Docker Commands

```bash
# Start
docker-compose up -d

# Stop
docker-compose down

# View logs
docker-compose logs -f

# Restart
docker-compose restart

# Update after code changes
docker-compose up -d --build
```

### Manual Commands

```bash
# Test without sending to Telegram
python main.py --run-once --dry-run

# Force fetch all news (ignore timestamp)
python main.py --run-once --force

# Run scheduler
python main.py

# Only run command listener
python main.py --listen-only
```

### Using Makefile

```bash
make help           # Show all commands
make test           # Test run (dry-run)
make docker-up      # Start with Docker
make docker-logs    # View logs
make docker-down    # Stop
make clean          # Clean temp files
```

## Manual Trigger Feature

### `/fire` Command

Authorized users can send `/fire` to the bot to manually trigger a digest for the **last 24 hours**.

**Usage:**
1. Find your bot on Telegram
2. Start a private chat
3. Send `/fire`
4. Bot processes and sends digest to channel

**Authorization:**

Edit `src/command_handler.py` to add users:

```python
# Line 14
AUTHORIZED_USERS = ['Gunneone', 'OtherUsername']
```

Then rebuild: `docker-compose up -d --build`

**Bot Responses (German):**
- 🔥 "Nachrichten-Digest wird erstellt..."
- 📊 "X Artikel gefunden. Analysiere Wichtigkeit..."
- ✅ "Top 3 Artikel ausgewählt. Erstelle Zusammenfassungen..."
- ✅ "Nachrichten-Digest erfolgreich gesendet!"
- ⛔ "Du bist nicht autorisiert..." (unauthorized)

## Output Format

The bot sends messages in German:

```
📰 Nachrichten-Digest - 30.12.2024 21:00

Schlagzeile 1 | Schlagzeile 2 | Schlagzeile 3

━━━━━━━━━━━━━━━━━━━━━━

📌 Schlagzeile 1
Zusammenfassung Satz eins. Zusammenfassung Satz zwei. Zusammenfassung Satz drei.
🔗 https://www.tagesschau.de/article1

📌 Schlagzeile 2
Zusammenfassung Satz eins. Zusammenfassung Satz zwei. Zusammenfassung Satz drei.
🔗 https://www.tagesschau.de/article2

📌 Schlagzeile 3
Zusammenfassung Satz eins. Zusammenfassung Satz zwei. Zusammenfassung Satz drei.
🔗 https://www.tagesschau.de/article3
```

## Project Structure

```
schagestau-telegram/
├── src/                    # Core application code
│   ├── __init__.py
│   ├── config.py           # Configuration loader
│   ├── fetcher.py          # Tagesschau API integration
│   ├── ranker.py           # OpenAI ranking logic
│   ├── summarizer.py       # OpenAI summarization
│   ├── telegram_bot.py     # Telegram integration
│   ├── storage.py          # State persistence
│   ├── command_handler.py  # /fire command handler
│   └── utils.py            # Helper functions
├── scripts/                # Utility scripts
│   ├── init_db.py          # Initialize storage
│   └── get_channel_id.py   # Get Telegram channel ID
├── data/                   # Runtime data (auto-generated)
│   ├── last_fetch.json
│   └── bot.log
├── main.py                 # Main entry point
├── requirements.txt        # Python dependencies
├── Dockerfile              # Docker container definition
├── docker-compose.yml      # Docker Compose configuration
├── Makefile                # Convenience commands
├── .env.example            # Example configuration
├── .env                    # Your configuration (not in git)
└── README.md               # This file
```

## Deployment

### Using systemd (Linux)

1. Create `/etc/systemd/system/schagestau-bot.service`:

```ini
[Unit]
Description=Schagestau Telegram News Bot
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/schagestau-telegram
Environment=PATH=/path/to/venv/bin
ExecStart=/path/to/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

2. Enable and start:

```bash
sudo systemctl enable schagestau-bot
sudo systemctl start schagestau-bot
sudo systemctl status schagestau-bot
```

### Using Docker Swarm

```bash
docker stack deploy -c docker-compose.yml schagestau
```

### Using cron

```bash
0 8,21 * * * cd /path/to/schagestau-telegram && /path/to/venv/bin/python main.py >> /var/log/schagestau.log 2>&1
```

## Troubleshooting

### Docker: Permission denied on data directory (macOS)

```bash
mkdir -p data
chmod -R 755 data
docker-compose down
docker-compose up -d
```

### Bot doesn't send messages

- Verify `TELEGRAM_BOT_TOKEN` is correct
- Ensure bot is admin in the channel
- Check `TELEGRAM_CHANNEL_ID` format
- Review logs: `docker-compose logs` or `cat bot.log`

### No news fetched

- Check Tagesschau API: `curl https://www.tagesschau.de/api2/news/`
- Check `last_fetch.json` timestamp
- Try `--force` flag
- Review network connectivity

### OpenAI errors

- Verify `OPENAI_API_KEY` is valid
- Check quota: https://platform.openai.com/usage
- Reduce `OPENAI_MAX_TOKENS` if hitting limits
- Try different model

### Container keeps restarting

```bash
docker-compose logs --tail=50
```

Common issues:
- Missing/invalid `.env` file
- Invalid API keys
- Network connectivity

### /fire command not working

- Ensure bot is running: `docker-compose ps`
- Check username is in `AUTHORIZED_USERS` (case-sensitive)
- Don't include @ in username list
- Check logs for authorization errors

## API Documentation

### Tagesschau API

- **Base URL**: `https://www.tagesschau.de/api2/news/`
- **Authentication**: None required
- **Rate Limit**: Reasonable use
- **Response**: JSON with news array

### OpenAI Integration

**Ranking Prompt (German)**:
```
Du bist ein Nachrichtenredakteur, der die Wichtigkeit deutscher Nachrichtenartikel bewertet.
Ranke die folgenden Artikel nach Wichtigkeit unter Berücksichtigung von:
1. Politische und gesellschaftliche Bedeutung
2. Auswirkungen auf das Leben der Menschen
3. Dringlichkeit und Aktualität
4. Geografischer und demografischer Umfang

Gib ein JSON-Array mit den IDs der Top 3 Artikel zurück.
```

**Summarization Prompt (German)**:
```
Fasse den folgenden deutschen Nachrichtenartikel in maximal 3 Sätzen zusammen.
Konzentriere dich auf die wichtigsten Fakten: Was ist passiert, wer ist beteiligt und was bedeutet es.
Schreibe in klarem, prägnanten Deutsch.
```

## Error Handling

The bot implements comprehensive error handling:

1. **API Failures**: Retries with exponential backoff
2. **Network Issues**: Logs error and waits for next run
3. **Invalid Responses**: Logs and skips malformed data
4. **Telegram Errors**: Retries up to 3 times
5. **OpenAI Rate Limits**: Waits and retries with delays

All errors are logged to `bot.log` with timestamps and stack traces.

## Security

1. **Never commit `.env`** - Contains sensitive credentials
2. **Restrict permissions**: `chmod 600 .env`
3. **Rotate API keys** regularly
4. **Use environment-specific keys** for dev/prod
5. **Monitor API usage** to detect unauthorized access
6. **Keep dependencies updated**: `pip install -U -r requirements.txt`
7. **Authorized users only** for `/fire` command

## Cost Estimation

### OpenAI API (with gpt-4o-mini, 2 runs/day)

- Input tokens: ~3,000 per run
- Output tokens: ~500 per run
- Cost per run: ~$0.001 USD
- **Monthly cost: ~$0.06 USD**

### Hosting

- VPS (minimal): $5-10/month
- Docker container: $0 (self-hosted)
- Free tier: Heroku, Railway, Render

## Development

### Running Tests

```bash
pytest tests/
```

### Code Style

```bash
black .
flake8 .
```

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## Dependencies

```
requests==2.31.0           # HTTP client
python-telegram-bot==20.7  # Telegram bot integration
openai==1.6.1              # OpenAI API client
python-dotenv==1.0.0       # Environment variables
schedule==1.2.0            # Job scheduling
pytz==2023.3               # Timezone support
```

## Changelog

### Version 1.0.0 (2024-12-30)

- Initial release
- Tagesschau API integration
- OpenAI ranking and summarization (German)
- Telegram channel posting (German)
- Configurable scheduling
- Manual trigger via `/fire` command
- Docker Compose support
- Comprehensive error handling

## License

[Specify your license here]

## Support

For issues or questions:
- Open an issue on GitHub
- Check logs: `docker-compose logs -f`
- Review troubleshooting section above

---

**Status**: Production Ready ✅  
**Version**: 1.0.0  
**Last Updated**: 2024-12-30
