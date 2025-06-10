# 📁 Project Structure

## Directory Layout

```
modcast/
├── src/                          # Core library code
│   ├── __init__.py              # Package initialization
│   ├── simple_orchestrator.py   # Main orchestrator implementation
│   └── openai_config.py         # OpenAI API configuration
│
├── examples/                     # Example implementations
│   ├── web_demo.py              # Full-featured web interface demo
│   └── simple_example.py        # Basic console example
│
├── docs/                         # Documentation
│   ├── ARCHITECTURE.md          # Technical architecture details
│   ├── QUICKSTART.md            # Getting started guide
│   └── PROJECT_STRUCTURE.md     # This file
│
├── scripts/                      # Utility scripts (legacy)
│   └── tests/                   # Test files
│
├── requirements.txt              # Python dependencies
├── env.example                   # Environment variable template
├── README.md                     # Main project documentation
├── LICENSE                       # MIT License
└── .gitignore                   # Git ignore rules
```

## Key Files Explained

### Core Library (`src/`)

#### `simple_orchestrator.py`
The heart of the system. Contains:
- `SimpleOrchestrator` class - Main orchestration logic
- `PersonaConfig` dataclass - Persona configuration
- `AudioChunkManager` class - Audio timing management
- WebSocket handling for OpenAI Realtime API
- Event system for extensibility

#### `openai_config.py`
Configuration management:
- `OpenAIRealtimeConfig` dataclass
- Environment variable loading
- API endpoint configuration
- Default settings

### Examples (`examples/`)

#### `web_demo.py`
Full-featured demonstration:
- Flask web server with SocketIO
- Real-time audio streaming
- Browser-based UI
- Microphone input handling
- Three pre-configured AI personas

#### `simple_example.py`
Minimal implementation showing:
- Basic orchestrator setup
- Console-based output
- Educational personas example
- Event handler usage

### Documentation (`docs/`)

#### `ARCHITECTURE.md`
Technical deep-dive:
- System design decisions
- Flow diagrams
- Performance optimizations
- Security considerations

#### `QUICKSTART.md`
Beginner-friendly guide:
- Step-by-step setup
- Common issues and solutions
- First conversation walkthrough
- Tips for best experience

## Import Structure

### From Examples
```python
# In examples/, import from src
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))
from simple_orchestrator import SimpleOrchestrator, PersonaConfig
from openai_config import OPENAI_REALTIME_CONFIG
```

### As a Package
```python
# If installed as a package
from modcast import SimpleOrchestrator, PersonaConfig
from modcast import OPENAI_REALTIME_CONFIG
```

## Configuration Files

### `requirements.txt`
All necessary dependencies:
- `websockets` - WebSocket client
- `openai[realtime]` - OpenAI SDK with realtime support
- `flask` & `flask-socketio` - Web framework
- `python-dotenv` - Environment variable management
- `ffmpeg-python` - Audio conversion

### `env.example`
Template for environment variables:
```env
OPENAI_API_KEY=your-api-key-here
OPENAI_REALTIME_MODEL=gpt-4o-realtime-preview
OPENAI_VOICE=alloy
```

## Development Workflow

1. **Core Development**: Work in `src/` for library changes
2. **Testing**: Use `examples/simple_example.py` for quick tests
3. **Demo**: Run `examples/web_demo.py` for full experience
4. **Documentation**: Update `docs/` when adding features

## Adding New Features

### New Persona Types
1. Define in example files or create new example
2. Use `PersonaConfig` with custom parameters
3. Set unique voice and instructions

### New Event Handlers
1. Add to `SimpleOrchestrator` class
2. Follow naming convention: `on_event_name`
3. Document in architecture guide

### New Examples
1. Create in `examples/` directory
2. Include proper imports from `src/`
3. Add documentation header
4. Focus on demonstrating specific features 