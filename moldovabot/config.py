import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
CMC_API_KEY = os.getenv("CMC_API_KEY", "")
XAI_API_KEY = os.getenv("XAI_API_KEY", "")
AIRLABS_API_KEY = os.getenv("AIRLABS_API_KEY", "")
MORNING_CHAT_ID = int(os.getenv("MORNING_CHAT_ID", "0"))
