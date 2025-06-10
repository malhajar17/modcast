#!/usr/bin/env python3
"""
Functional test for the OpenAI Realtime API (WebSockets + PCM-16 audio).

What it does
------------
1. Opens wss://api.openai.com/v1/realtime?model=<model>
2. Sends a `session.update` that asks for both *text* and *audio* output.
3. Creates a user message and a `response.create` request.
4. Waits ~10 s for audio chunks (`response.audio.delta`) and prints stats.

Pass/Fail
---------
✅ Pass  – at least one audio chunk arrives  
❌ Fail  – zero audio or any connection / auth error

Environment Variables
--------------------
OPENAI_API_KEY          - Required. Your OpenAI API key
OPENAI_REALTIME_MODEL   - Optional. Model to use (default: gpt-4o-realtime-preview)
"""

import asyncio
import base64
import json
import logging
import os
from typing import Optional

import websockets

# Try to load .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv not installed, that's fine
    pass

# -----------------------------------------------------------------------------
# Configure logging
logging.basicConfig(
    format="%(levelname)s | %(message)s", 
    level=logging.INFO
)
log = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Main test class
class OpenAIRealtimeAudioTest:
    """Test OpenAI Realtime API audio streaming functionality."""
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """Initialize the test.
        
        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            model: Model to use (defaults to OPENAI_REALTIME_MODEL env var or gpt-4o-realtime-preview)
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY environment variable not set")
        
        self.model = model or os.getenv("OPENAI_REALTIME_MODEL", "gpt-4o-realtime-preview")
        
        # Runtime counters
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._audio_chunks = 0
        self._audio_bytes = 0

    def _ws_url(self) -> str:
        """Build WebSocket URL for OpenAI Realtime API."""
        return f"wss://api.openai.com/v1/realtime?model={self.model}"

    def _headers(self) -> dict:
        """Build WebSocket headers for authentication."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "OpenAI-Beta": "realtime=v1",
        }

    async def run(self, timeout: float = 10.0) -> bool:
        """Run the audio streaming test.
        
        Args:
            timeout: How long to wait for audio chunks (seconds)
            
        Returns:
            True if audio chunks were received, False otherwise
        """
        log.info("🔌 Connecting to %s", self._ws_url())
        
        try:
            async with websockets.connect(
                self._ws_url(), 
                extra_headers=self._headers(), 
                ping_interval=20
            ) as ws:
                self._ws = ws
                await self._configure_session()
                await asyncio.sleep(1)
                await self._send_test_prompt()

                # Listen for audio chunks
                try:
                    await asyncio.wait_for(self._receive_loop(), timeout=timeout)
                except asyncio.TimeoutError:
                    log.info("⏰ Timeout reached, stopping test")

        except Exception as e:
            log.error("❌ Connection failed: %s", e)
            return False

        # Report results
        log.info("🎵 Received %d chunks (%d bytes total)", self._audio_chunks, self._audio_bytes)
        
        success = self._audio_chunks > 0
        if success:
            log.info("✅ Audio streaming is working!")
        else:
            log.error("❌ No audio received - check your API access and model availability")
        
        return success

    async def _configure_session(self):
        """Configure the realtime session for audio output."""
        payload = {
            "type": "session.update",
            "session": {
                "modalities": ["text", "audio"],
                "instructions": "You are a helpful assistant. Respond briefly in 1-2 sentences.",
                "voice": "alloy",
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "turn_detection": {"type": "server_vad"},
                "input_audio_transcription": {"model": "whisper-1"},
                "temperature": 0.7,
            },
        }
        await self._send(payload)
        log.debug("📋 Session configured")

    async def _send_test_prompt(self):
        """Send a test message to trigger audio response."""
        # Create user message
        await self._send({
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "user",
                "content": [{
                    "type": "input_text",
                    "text": "Hello! Please confirm that audio streaming works. Keep it brief."
                }],
            },
        })
        
        # Request response with audio
        await self._send({
            "type": "response.create",
            "response": {
                "modalities": ["text", "audio"],
                "voice": "alloy",
                "output_audio_format": "pcm16",
            },
        })
        log.debug("📤 Test prompt sent")

    async def _send(self, payload: dict):
        """Send JSON payload to WebSocket."""
        if not self._ws:
            raise RuntimeError("WebSocket not connected")
        await self._ws.send(json.dumps(payload))

    async def _receive_loop(self):
        """Process incoming WebSocket messages."""
        if not self._ws:
            return
            
        async for raw_message in self._ws:
            try:
                message = json.loads(raw_message)
                await self._handle_message(message)
            except json.JSONDecodeError:
                log.warning("⚠️ Invalid JSON: %.60s…", raw_message)
            except Exception as e:
                log.error("❌ Error processing message: %s", e)

    async def _handle_message(self, message: dict):
        """Handle incoming realtime API message."""
        msg_type = message.get("type", "")
        
        if msg_type == "response.audio.delta":
            # This is what we're testing for!
            audio_data = message.get("delta", "")
            if audio_data:
                try:
                    decoded = base64.b64decode(audio_data)
                    self._audio_chunks += 1
                    self._audio_bytes += len(decoded)
                    log.debug("🔊 Audio chunk #%d (%d bytes)", self._audio_chunks, len(decoded))
                except Exception as e:
                    log.error("❌ Failed to decode audio: %s", e)
                    
        elif msg_type == "response.text.delta":
            # Show text response for debugging
            text = message.get("delta", "").strip()
            if text:
                log.info("💬 %s", text)
                
        elif msg_type == "error":
            error_msg = message.get("error", {}).get("message", "Unknown error")
            log.error("❌ API Error: %s", error_msg)
            
        elif msg_type == "response.done":
            log.debug("✅ Response completed")
            
        # Other message types are ignored for brevity


async def main():
    """Main entry point for the test."""
    log.info("🧪 Starting OpenAI Realtime API Audio Test")
    log.info("📖 Testing model: %s", os.getenv("OPENAI_REALTIME_MODEL", "gpt-4o-realtime-preview"))
    
    try:
        tester = OpenAIRealtimeAudioTest()
        success = await tester.run()
        
        if success:
            log.info("🎉 Test PASSED! Audio streaming is functional.")
            return 0
        else:
            log.error("💥 Test FAILED! Audio streaming is not working.")
            return 1
            
    except RuntimeError as e:
        log.error("❌ Configuration error: %s", e)
        log.info("💡 Make sure to set OPENAI_API_KEY environment variable")
        return 1
    except Exception as e:
        log.error("❌ Unexpected error: %s", e)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
