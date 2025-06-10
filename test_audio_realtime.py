#!/usr/bin/env python3
"""
Test script for Azure OpenAI Realtime API audio functionality
Based on official Azure samples: https://github.com/Azure-Samples/aoai-realtime-audio-sdk
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

class RealtimeAudioTest:
    def __init__(self, api_key: Optional[str] = None, azure_endpoint: Optional[str] = None, 
                 deployment_name: Optional[str] = None, api_version: Optional[str] = None):
        # Try parameters first, then environment variables
        self.api_key = api_key or os.getenv("AZURE_OPENAI_API_KEY")
        self.azure_endpoint = azure_endpoint or os.getenv("AZURE_OPENAI_ENDPOINT")
        self.deployment_name = deployment_name or os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o-realtime-preview")
        self.api_version = api_version or os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-01-preview")
        
        # Validate required configuration
        if not self.api_key:
            raise ValueError("API key not provided. Set AZURE_OPENAI_API_KEY environment variable or pass api_key parameter.")
        if not self.azure_endpoint:
            raise ValueError("Azure endpoint not provided. Set AZURE_OPENAI_ENDPOINT environment variable or pass azure_endpoint parameter.")
        if not self.deployment_name:
            raise ValueError("Deployment name not provided. Set AZURE_OPENAI_DEPLOYMENT_NAME environment variable or pass deployment_name parameter.")
        
        self.websocket = None
        self.is_connected = False
        self.received_audio_chunks = 0
        self.total_audio_bytes = 0
        
    def _build_websocket_url(self) -> str:
        """Build WebSocket URL like official samples"""
        base_url = self.azure_endpoint.replace("https://", "wss://").replace("http://", "ws://")
        if base_url.endswith("/"):
            base_url = base_url[:-1]
        
        # Official Azure pattern: API key in URL for WebSocket
        ws_url = f"{base_url}/openai/realtime?api-version={self.api_version}&deployment={self.deployment_name}&api-key={self.api_key}"
        return ws_url
    
    async def connect_and_test(self):
        """Connect and test audio functionality"""
        ws_url = self._build_websocket_url()
        safe_url = ws_url.replace(self.api_key, f"{self.api_key[:8]}...")
        logger.info(f"🔌 Connecting to: {safe_url}")
        
        try:
            self.websocket = await websockets.connect(
                ws_url,
                ping_interval=30,
                ping_timeout=10
            )
            
            self.is_connected = True
            logger.info("✅ Connected to Azure OpenAI Realtime API")
            
            # Configure session like official samples
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
                
        except Exception as ex:
            logger.error(f"❌ Test failed: {ex}")
            return False
    
    async def _configure_session(self):
        """Configure session like official samples"""
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
                        "text": "Please say hello and tell me that audio streaming is working. Give me a short 2-3 sentence response."
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
            logger.error(f"❌ API Error: {error_msg}")
            
        else:
            logger.debug(f"📥 Event: {message_type}")


async def main():
    """Run the audio test"""
    logger.info("🧪 Starting Azure OpenAI Realtime API Audio Test")
    logger.info("📖 Based on official patterns from: https://github.com/Azure-Samples/aoai-realtime-audio-sdk")
    
    try:
        # Initialize with environment variables (default)
        # Or pass parameters directly: RealtimeAudioTest(api_key="your_key", azure_endpoint="your_endpoint", ...)
        test = RealtimeAudioTest()
        success = await test.connect_and_test()
        
        if success:
            logger.info("🎉 Audio test PASSED - your implementation should work!")
        else:
            logger.error("💥 Audio test FAILED - check your configuration")
        
        return success
    
    except ValueError as e:
        logger.error(f"❌ Configuration error: {e}")
        logger.error("💡 Make sure to set your Azure OpenAI environment variables or pass them as parameters")
        return False

if __name__ == "__main__":
    asyncio.run(main()) 