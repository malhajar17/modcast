# 🚀 Quick Start Guide

<p align="center">
  <img src="../mo-logo.png" alt="Mo - Modcast Logo" width="100">
</p>

Get up and running with Modcast in under 5 minutes!

## Prerequisites Check

Before starting, ensure you have:
- ✅ Python 3.8 or higher
- ✅ OpenAI API key with Realtime API access
- ✅ FFmpeg installed
- ✅ A modern web browser

## Step 1: Clone and Setup

```bash
# Clone the repository
git clone <repository-url>
cd modcast

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Linux/Mac:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Step 2: Configure API Key

```bash
# Copy environment template
cp env.example .env

# Edit .env file and add your OpenAI API key
# OPENAI_API_KEY=sk-your-key-here
```

## Step 3: Run the Demo

```bash
# Navigate to examples directory
cd examples

# Start the web demo
python web_demo.py
```

## Step 4: Experience Real-time AI Conversations

1. Open your browser to `http://localhost:3001`
2. Click "🚀 Start Real-time Conversation"
3. Watch AI personas interact in real-time!
4. Click and hold the microphone button when it's your turn to speak

## What You'll See

### The AI Personas

- **Mo** 🧑‍🔬 - A pedantic AI researcher with increasingly wild theories
- **Marine** 🎭 - A cheerful AI revealing elaborate takeover plans
- **Jordan** 💻 - Delivers dark truths about AI dominance casually

### Features in Action

- **Real-time Audio**: Hear personas speak with < 500ms latency
- **Dynamic Conversations**: Each persona chooses who speaks next
- **Human Interaction**: Jump in anytime with your voice
- **Visual Feedback**: See who's speaking and conversation flow

## Common Issues & Solutions

### "No module named 'openai'"
```bash
pip install openai[realtime]
```

### "FFmpeg not found"
- **Ubuntu/Debian**: `sudo apt-get install ffmpeg`
- **macOS**: `brew install ffmpeg`
- **Windows**: Download from [ffmpeg.org](https://ffmpeg.org)

### "403 Forbidden" from OpenAI
- Ensure your API key has Realtime API access
- Check your OpenAI account status

### No Audio Playback
- Check browser console for errors
- Ensure your browser allows audio playback
- Try refreshing the page

## Next Steps

1. **Customize Personas**: Edit personas in `web_demo.py`
2. **Change Topics**: Modify the initial conversation prompt
3. **Adjust Timing**: Tweak `chunk_duration_ms` for different pacing
4. **Build Your Own**: Use `SimpleOrchestrator` in your projects

## Example: Creating Your Own Personas

```python
from src.simple_orchestrator import SimpleOrchestrator, PersonaConfig
from src.openai_config import OPENAI_REALTIME_CONFIG

# Define your personas
personas = [
    PersonaConfig(
        name="Alice",
        voice="alloy",
        instructions="You are Alice, a friendly teacher. Be helpful and encouraging.",
        temperature=0.7
    ),
    PersonaConfig(
        name="Bob",
        voice="echo",
        instructions="You are Bob, a curious student. Ask thoughtful questions.",
        temperature=0.8
    )
]

# Create orchestrator
orchestrator = SimpleOrchestrator(personas, OPENAI_REALTIME_CONFIG)

# Start conversation
await orchestrator.start_conversation_async("Let's learn about space!")
```

## Tips for Best Experience

1. **Use a Good Microphone**: Clear audio input improves AI responses
2. **Speak Naturally**: The AI understands conversational speech
3. **Let Personas Finish**: Wait for smooth transitions between speakers
4. **Experiment**: Try different conversation starters and see what happens!

## Getting Help

- 📖 Read the [Architecture Guide](ARCHITECTURE.md)
- 🐛 Check [Troubleshooting](../README.md#-troubleshooting)
- 💬 Open an issue on GitHub
- 🤝 Join our community discussions

---

Ready to experience the future of AI conversations? Start the demo and enjoy! 🎉 