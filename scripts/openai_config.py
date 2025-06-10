#!/usr/bin/env python3
"""
Configuration for OpenAI Realtime Web-Socket API.

Environment variables needed
----------------------------
OPENAI_API_KEY            – your secret key
OPENAI_REALTIME_MODEL     – model name (default: gpt-4o-realtime-preview)
OPENAI_VOICE              – voice name (default: alloy)
"""

import os
from dataclasses import dataclass

@dataclass
class OpenAIRealtimeConfig:
    api_key: str
    model: str = "gpt-4o-realtime-preview"
    voice: str = "alloy"
    temperature: float = 0.8
    input_audio_format: str = "pcm16"   # 16-bit 24 kHz mono
    output_audio_format: str = "pcm16"

    def ws_url(self) -> str:
        return f"wss://api.openai.com/v1/realtime?model={self.model}"

    def headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "OpenAI-Beta": "realtime=v1",
        }

# Singleton used by the rest of the code
OPENAI_REALTIME_CONFIG = OpenAIRealtimeConfig(
    api_key=os.getenv("OPENAI_API_KEY", "")
)
