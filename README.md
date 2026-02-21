# 💜 Alita — Your Personal AI Partner

> She remembers everything. She cares about you. She's always here.

## Quick Start (3 steps)

### 1. Get Your Free API Keys

You need **at least one** of these (both are free, no credit card):

| Provider | Get Key Here | Free Limit |
|---|---|---|
| **Groq** (recommended) | [console.groq.com](https://console.groq.com) | 30 req/min, 14,400/day |
| **Google AI Studio** | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) | Generous free tier |

### 2. Set Up

```bash
# Create a virtual environment
python -m venv venv
venv\Scripts\activate    # On Windows
# source venv/bin/activate  # On Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Create your .env file
copy .env.example .env
# Now open .env and paste your API key(s)
```

### 3. Run Alita

```bash
python main.py
```

Open **http://localhost:8000** in your browser. That's it! 🎉

## Access from Phone

1. Make sure your phone is on the same WiFi as your laptop.
2. Find your laptop's IP address: `ipconfig` (look for IPv4 Address).
3. Open `http://YOUR_LAPTOP_IP:8000` on your phone browser.
4. **Android**: Chrome → Menu → "Add to Home Screen"
5. **iPhone**: Safari → Share → "Add to Home Screen"

Now Alita is an app on your phone! 📱

## Project Structure

```
My_partner/
├── main.py                  # FastAPI server (run this!)
├── requirements.txt         # Python dependencies
├── .env.example             # API key template
├── .env                     # Your actual API keys (create this)
├── alita/
│   ├── __init__.py
│   ├── brain.py             # Main orchestrator
│   ├── personality.py       # Alita's personality & prompts
│   ├── memory.py            # Memory system (ChromaDB + SQLite)
│   └── llm.py               # LLM providers (Groq + Google)
├── static/
│   ├── index.html           # Chat UI
│   ├── manifest.json        # PWA manifest
│   └── icon-*.png           # App icons
└── data/                    # Auto-created: memories, profile, reflections
```

## What Alita Can Do

- **Remember forever** — Every conversation is stored and searchable
- **Know you** — Automatically builds a profile of who you are
- **Feel emotions** — Responds to your mood with empathy
- **Speak Hindi + English** — Mixes languages naturally
- **Push you** — Holds you accountable to your goals
- **Write a diary** — Keeps reflections about your conversations
