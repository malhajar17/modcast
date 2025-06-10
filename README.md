# Modcast - OpenAI Realtime Audio Testing

This project provides tools for testing OpenAI Realtime API audio functionality.

## Purpose

The main goal is to test and validate that OpenAI's Realtime API can successfully:
- Establish WebSocket connections
- Send and receive audio data
- Handle real-time audio streaming
- Process audio responses correctly

## Files

- `scripts/tests/test_audio_realtime.py` - Main testing script for OpenAI Realtime API
- `requirements.txt` - Python dependencies
- `env.example` - Template for environment variables

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set your OpenAI credentials as environment variables:

**Option A: Use the example file**
```bash
cp env.example .env
# Edit .env with your actual API key
```

**Option B: Set directly in terminal**
```bash
export OPENAI_API_KEY="your-openai-api-key-here"
```

Or on Windows:
```cmd
set OPENAI_API_KEY=your-openai-api-key-here
```

3. Run the audio test:
```bash
python scripts/tests/test_audio_realtime.py
```

### Alternative: Direct Parameter Injection

You can also pass credentials directly in code:
```python
from test_audio_realtime import OpenAIRealtimeTest

test = OpenAIRealtimeTest(
    api_key="your-openai-api-key",
    model="gpt-4o-realtime-preview-2024-10-01"
)
await test.connect_and_test()
```

## What the Test Does

The test script:
1. Connects to OpenAI Realtime API via WebSocket
2. Configures audio session with PCM16 format
3. Sends a test message requesting audio response
4. Monitors for audio chunks in the response
5. Reports success/failure of audio streaming

## Important Notes

- ⚠️ **API Access Required**: You need access to OpenAI's Realtime API (still rolling out)
- 🔑 **Authentication**: Uses Bearer token authentication with OpenAI API key
- 🎵 **Audio Format**: Tests PCM16 audio streaming (industry standard)
- 📊 **Comprehensive Testing**: Validates both connection and actual audio data flow
- 🚀 **Access Status**: If you get a 403 error, the Realtime API may not be available for your account yet

## Expected Output

If working correctly, you should see:
- Successful WebSocket connection
- Session configuration confirmation
- Audio chunks being received with byte counts
- Test PASSED message

## Based On

This implementation follows the official OpenAI Realtime API documentation:
https://platform.openai.com/docs/guides/realtime