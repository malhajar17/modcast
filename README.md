# Modcast - Azure OpenAI Realtime Audio Testing

This project provides tools for testing Azure OpenAI Realtime API audio functionality.

## Purpose

The main goal is to test and validate that Azure OpenAI's Realtime API can successfully:
- Establish WebSocket connections
- Send and receive audio data
- Handle real-time audio streaming
- Process audio responses correctly

## Files

- `test_audio_realtime.py` - Main testing script for Azure OpenAI Realtime API
- `requirements.txt` - Python dependencies
- `env.example` - Template for environment variables

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set your Azure OpenAI credentials as environment variables:

**Option A: Use the example file**
```bash
cp env.example .env
# Edit .env with your actual credentials
```

**Option B: Set directly in terminal**
```bash
export AZURE_OPENAI_API_KEY="your-api-key-here"
export AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com"
export AZURE_OPENAI_DEPLOYMENT_NAME="gpt-4o-realtime-preview"  # optional, defaults to this
export AZURE_OPENAI_API_VERSION="2024-10-01-preview"  # optional, defaults to this
```

Or on Windows:
```cmd
set AZURE_OPENAI_API_KEY=your-api-key-here
set AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
set AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o-realtime-preview
set AZURE_OPENAI_API_VERSION=2024-10-01-preview
```

3. Run the audio test:
```bash
python test_audio_realtime.py
```

### Alternative: Direct Parameter Injection

You can also pass credentials directly in code:
```python
from test_audio_realtime import RealtimeAudioTest

test = RealtimeAudioTest(
    api_key="your-api-key",
    azure_endpoint="https://your-resource.openai.azure.com",
    deployment_name="gpt-4o-realtime-preview",
    api_version="2024-10-01-preview"
)
await test.connect_and_test()
```

## What the Test Does

The test script:
1. Connects to Azure OpenAI Realtime API via WebSocket
2. Configures audio session with PCM16 format
3. Sends a test message requesting audio response
4. Monitors for audio chunks in the response
5. Reports success/failure of audio streaming

## Expected Output

If working correctly, you should see:
- Successful WebSocket connection
- Session configuration confirmation
- Audio chunks being received with byte counts
- Test PASSED message

## Based On

This implementation follows the official Azure OpenAI Realtime API patterns from:
https://github.com/Azure-Samples/aoai-realtime-audio-sdk