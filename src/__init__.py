"""
Real-time AI Orchestrator

A sophisticated system for orchestrating multi-persona AI conversations
using OpenAI's Realtime API with seamless audio streaming.
"""

from .simple_orchestrator import SimpleOrchestrator, PersonaConfig, AudioChunkManager
from .openai_config import OpenAIRealtimeConfig, OPENAI_REALTIME_CONFIG

__version__ = "1.0.0"
__author__ = "Real-time AI Orchestrator Team"

__all__ = [
    "SimpleOrchestrator",
    "PersonaConfig", 
    "AudioChunkManager",
    "OpenAIRealtimeConfig",
    "OPENAI_REALTIME_CONFIG"
] 