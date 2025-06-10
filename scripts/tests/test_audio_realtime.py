#!/usr/bin/env python3
"""
Test script for OpenAI Realtime API audio functionality
Based on official OpenAI Realtime API: https://platform.openai.com/docs/guides/realtime
"""

import asyncio
import json
import base64
import websockets
import logging
import os
from typing import Optional

# Try to load .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv not installed, that's fine
    pass

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OpenAIRealtimeTest:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        # Try parameters first, then environment variables
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model or "gpt-4o-realtime-preview-2024-10-01"
        
        # Validate required configuration
        if not self.api_key:
            raise ValueError("API key not provided. Set OPENAI_API_KEY environment variable or pass api_key parameter.")
        
        self.websocket = None
        self.is_connected = False
        self.received_audio_chunks = 0
        self.total_audio_bytes = 0
        
    def _build_websocket_url(self) -> str:
        """Build WebSocket URL for OpenAI Realtime API"""
        return f"wss://api.openai.com/v1/realtime?model={self.model}"
    
    def _get_headers(self) -> dict:
        """Get headers for OpenAI WebSocket connection"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "OpenAI-Beta": "realtime=v1"
        }
    
    async def connect_and_test(self):
        """Connect and test audio functionality"""
        ws_url = self._build_websocket_url()
        headers = self._get_headers()
        
        # Hide API key in logs
        safe_url = ws_url.replace(self.api_key, f"{self.api_key[:8]}...")
        logger.info(f"🔌 Connecting to OpenAI Realtime API: {safe_url}")
        
        try:
            self.websocket = await websockets.connect(
                ws_url,
                extra_headers=headers,
                ping_interval=30,
                ping_timeout=10
            )
            
            self.is_connected = True
            logger.info("✅ Connected to OpenAI Realtime API")
            
            # Configure session
            await self._configure_session()
            
            # Start message handling
            receive_task = asyncio.create_task(self._receive_loop())
            
            # Send test message after short delay
            await asyncio.sleep(1)
            await self._send_test_message()
            
            # Wait for response
            await asyncio.sleep(10)
            
            # Cleanup
            receive_task.cancel()
            await self.websocket.close()
            
            # Report results
            logger.info(f"🎵 Test Results:")
            logger.info(f"   Audio chunks received: {self.received_audio_chunks}")
            logger.info(f"   Total audio bytes: {self.total_audio_bytes}")
            
            if self.received_audio_chunks > 0:
                logger.info("✅ Audio streaming is working!")
                return True
            else:
                logger.error("❌ No audio received - something is wrong")
                return False
                
        except websockets.exceptions.WebSocketException as e:
            if "403" in str(e):
                logger.error("❌ 403 Forbidden - You don't have access to the Realtime API yet")
                logger.error("💡 The Realtime API is still rolling out. Check https://platform.openai.com/playground for access")
                return False
            else:
                logger.error(f"❌ WebSocket error: {e}")
                return False
        except Exception as ex:
            logger.error(f"❌ Test failed: {ex}")
            return False
    
    async def _configure_session(self):
        """Configure session for OpenAI Realtime API"""
        session_config = {
            "type": "session.update",
            "session": {
                "modalities": ["text", "audio"],
                "instructions": "You are a helpful assistant. Give a brief 2-3 sentence response to test audio functionality.",
                "voice": "alloy",
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.5,
                    "prefix_padding_ms": 300,
                    "silence_duration_ms": 500
                },
                "temperature": 0.8,
                "max_response_output_tokens": 500
            }
        }
        
        await self._send_message(session_config)
        logger.info("📋 Session configured")
    
    async def _send_test_message(self):
        """Send test message that should generate audio response"""
        # Create conversation item
        item_message = {
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "user", 
                "content": [
                    {
                        "type": "input_text",
                        "text": "Please say hello and tell me that OpenAI Realtime API audio streaming is working. Give me a short 2-3 sentence response."
                    }
                ]
            }
        }
        
        await self._send_message(item_message)
        
        # Request response with audio
        response_message = {
            "type": "response.create",
            "response": {
                "modalities": ["text", "audio"],
                "voice": "alloy",
                "output_audio_format": "pcm16"
            }
        }
        
        await self._send_message(response_message)
        logger.info("📤 Sent test message requesting audio response")
    
    async def _send_message(self, message):
        """Send JSON message to WebSocket"""
        if self.websocket and self.is_connected:
            await self.websocket.send(json.dumps(message))
    
    async def _receive_loop(self):
        """Handle incoming messages"""
        try:
            async for message in self.websocket:
                if not self.is_connected:
                    break
                
                try:
                    data = json.loads(message)
                    await self._handle_message(data)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON: {message[:100]}")
                except Exception as ex:
                    logger.error(f"Error processing message: {ex}")
                    
        except websockets.exceptions.ConnectionClosed:
            logger.info("🔌 Connection closed")
        except Exception as ex:
            logger.error(f"Receive loop error: {ex}")
    
    async def _handle_message(self, data):
        """Handle incoming message"""
        message_type = data.get("type", "unknown")
        
        if message_type == "session.created":
            logger.info("✅ Session created")
            
        elif message_type == "session.updated":
            logger.info("✅ Session updated")
            
        elif message_type == "response.created":
            logger.info("🎤 Response started")
            
        elif message_type == "response.audio.delta":
            # This is the key test - are we receiving audio?
            audio_data = data.get("delta", "")
            if audio_data:
                try:
                    audio_bytes = base64.b64decode(audio_data)
                    self.received_audio_chunks += 1
                    self.total_audio_bytes += len(audio_bytes)
                    logger.info(f"🔊 Audio chunk {self.received_audio_chunks}: {len(audio_bytes)} bytes")
                except Exception as ex:
                    logger.error(f"Error decoding audio: {ex}")
                    
        elif message_type == "response.audio.done":
            logger.info("🎵 Audio response completed")
            
        elif message_type == "response.text.delta":
            text_delta = data.get("delta", "")
            if text_delta:
                logger.info(f"💬 Text: {text_delta}")
                
        elif message_type == "response.done":
            logger.info("✅ Response completed")
            
        elif message_type == "error":
            error_msg = data.get("error", {}).get("message", "Unknown error")
            error_code = data.get("error", {}).get("code", "")
            logger.error(f"❌ API Error ({error_code}): {error_msg}")
            
        else:
            logger.debug(f"📥 Event: {message_type}")


async def main():
    """Run the audio test"""
    logger.info("🧪 Starting OpenAI Realtime API Audio Test")
    logger.info("📖 Based on: https://platform.openai.com/docs/guides/realtime")
    
    try:
        # Initialize with environment variables (default)
        # Or pass parameters directly: OpenAIRealtimeTest(api_key="your_key", model="gpt-4o-realtime-preview-2024-10-01")
        test = OpenAIRealtimeTest()
        success = await test.connect_and_test()
        
        if success:
            logger.info("🎉 Audio test PASSED - OpenAI Realtime API is working!")
        else:
            logger.error("💥 Audio test FAILED - check your configuration or API access")
        
        return success
    
    except ValueError as e:
        logger.error(f"❌ Configuration error: {e}")
        logger.error("💡 Make sure to set your OPENAI_API_KEY environment variable or pass it as a parameter")
        return False

if __name__ == "__main__":
    asyncio.run(main()) 