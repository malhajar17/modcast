#!/usr/bin/env python3
"""
Simple Example: Using the Real-time AI Orchestrator

This example shows how to create a basic multi-persona conversation
using the SimpleOrchestrator with minimal setup.
"""

import asyncio
import sys
import os

# Add src directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from simple_orchestrator import SimpleOrchestrator, PersonaConfig
from openai_config import OPENAI_REALTIME_CONFIG


async def main():
    """Run a simple orchestrated conversation"""
    
    # Define three personas with different personalities
    personas = [
        PersonaConfig(
            name="Professor",
            voice="alloy",
            instructions="""You are a knowledgeable professor who loves teaching. 
            Keep responses to 2-3 sentences. Be enthusiastic about sharing knowledge.
            After speaking, choose who should speak next based on the conversation flow.""",
            temperature=0.7,
            max_response_tokens=150
        ),
        PersonaConfig(
            name="Student",
            voice="echo",
            instructions="""You are a curious student eager to learn. 
            Ask thoughtful questions in 2-3 sentences. Show genuine interest.
            After speaking, choose who should speak next based on the conversation flow.""",
            temperature=0.8,
            max_response_tokens=150
        ),
        PersonaConfig(
            name="Assistant",
            voice="shimmer",
            instructions="""You are a helpful teaching assistant. 
            Provide practical examples and clarifications in 2-3 sentences.
            After speaking, choose who should speak next based on the conversation flow.""",
            temperature=0.6,
            max_response_tokens=150
        )
    ]
    
    # Create the orchestrator
    print("🎭 Creating orchestrator with 3 personas...")
    orchestrator = SimpleOrchestrator(personas, OPENAI_REALTIME_CONFIG)
    
    # Set up event handlers to see what's happening
    def on_persona_started(name):
        print(f"\n🎤 {name} is speaking...")
    
    def on_persona_finished(name, text, audio_data):
        print(f"✅ {name}: {text}")
        print(f"   (Generated {len(audio_data)} bytes of audio)")
    
    def on_conversation_complete():
        print("\n🎬 Conversation complete!")
    
    # Attach event handlers
    orchestrator.on_persona_started = on_persona_started
    orchestrator.on_persona_finished = on_persona_finished
    orchestrator.on_conversation_complete = on_conversation_complete
    
    # Configure conversation parameters
    orchestrator.max_turns = 6  # Each persona speaks twice
    orchestrator.turn_delay_seconds = 1.0  # 1 second pause between speakers
    
    # Start the conversation
    print("\n🚀 Starting conversation about artificial intelligence...\n")
    
    initial_topic = """Welcome to our educational discussion! 
    Today we're exploring the fascinating world of artificial intelligence. 
    Professor, could you start by explaining what AI is in simple terms?"""
    
    try:
        await orchestrator.start_conversation_async(initial_topic)
    except KeyboardInterrupt:
        print("\n\n⚠️ Conversation interrupted by user")
        orchestrator.stop_conversation()
    except Exception as e:
        print(f"\n❌ Error during conversation: {e}")
    
    # Print summary
    print("\n📊 Conversation Summary:")
    summary = orchestrator.get_conversation_summary()
    print(f"   Total turns: {summary['total_turns']}")
    print(f"   Personas involved: {', '.join(summary['personas'])}")
    
    print("\n💡 This example demonstrates:")
    print("   - Creating multiple personas with different personalities")
    print("   - Setting up event handlers to monitor the conversation")
    print("   - Starting an orchestrated conversation on a specific topic")
    print("   - Personas dynamically choosing who speaks next")


if __name__ == "__main__":
    print("=" * 60)
    print("🎙️ Modcast - Simple Example")
    print("=" * 60)
    
    # Check for API key
    if not OPENAI_REALTIME_CONFIG.api_key:
        print("\n❌ Error: OPENAI_API_KEY environment variable not set!")
        print("Please set your OpenAI API key:")
        print("  export OPENAI_API_KEY='your-key-here'")
        sys.exit(1)
    
    # Run the example
    asyncio.run(main()) 