#!/usr/bin/env python3
"""
Simple Orchestrator for Multiple Personas
Manages turn-based conversation in a chain: Persona1 -> Persona2 -> Persona3 -> repeat
"""

import asyncio
import logging
import time
from typing import List, Optional, Dict, Any, Callable
from dataclasses import dataclass
from datetime import datetime
import threading
import random  # Added for random speaker selection


@dataclass
class PersonaConfig:
    """Configuration for a single persona"""
    name: str
    voice: str = "ballard"  # Azure OpenAI voice
    instructions: str = "You are a friendly AI assistant in a podcast conversation."
    temperature: float = 0.8
    max_response_tokens: int = 1000


class AudioChunkManager:
    """Manages audio chunks and timing requirements (same as main orchestrator)"""
    
    def __init__(
        self,
        chunk_duration_ms: int = 655,  # 0.655 seconds per chunk
        logger: Optional[logging.Logger] = None
    ):
        self.chunk_duration_ms = chunk_duration_ms
        self.logger = logger or logging.getLogger(__name__)
        
        # Track chunks per persona
        self.persona_chunks: Dict[str, int] = {}
        
        self.logger.info(f"AudioChunkManager initialized with {chunk_duration_ms}ms per chunk")
    
    def track_persona_chunk(self, persona_name: str):
        """Track an audio chunk for a persona"""
        if persona_name not in self.persona_chunks:
            self.persona_chunks[persona_name] = 0
        
        self.persona_chunks[persona_name] += 1
        self.logger.debug(f"Tracked chunk for {persona_name}: {self.persona_chunks[persona_name]} total")
    
    def get_persona_chunks(self, persona_name: str) -> int:
        """Get chunk count for a persona"""
        return self.persona_chunks.get(persona_name, 0)
    
    def calculate_wait_time(self, persona_name: str) -> int:
        """Calculate wait time based on chunk count (chunks * 655ms)"""
        chunks = self.get_persona_chunks(persona_name)
        wait_time_ms = chunks * self.chunk_duration_ms
        
        self.logger.debug(f"Wait time for {persona_name}: {wait_time_ms}ms ({chunks} chunks)")
        return wait_time_ms
    
    def reset_persona_chunks(self, persona_name: str):
        """Reset chunk count for a persona"""
        if persona_name in self.persona_chunks:
            old_count = self.persona_chunks[persona_name]
            self.persona_chunks[persona_name] = 0
            self.logger.debug(f"Reset chunks for {persona_name} (was {old_count})")
    
    def clear_all_chunks(self):
        """Clear all persona chunk counts"""
        self.persona_chunks.clear()
        self.logger.info("Cleared all persona chunk counts")


class SimpleOrchestrator:
    """
    Simple orchestrator that cycles through personas in order
    Each persona speaks, then the next one responds, creating a natural conversation chain
    """
    
    def __init__(
        self,
        personas: List[PersonaConfig],
        openai_config,
        logger: Optional[logging.Logger] = None
    ):
        self.personas = personas
        self.openai_config = openai_config
        self.logger = logger or self._setup_logging()
        
        # State management
        self.current_persona_index = 0
        self.is_running = False
        self.conversation_history = []
        
        # Timing control
        self.turn_delay_seconds = 0.0  # No pause between speakers - continuous conversation
        self.current_speaker = None
        self.is_speaking = False
        
        # Audio chunk management (655ms per chunk)
        self.audio_chunk_manager = AudioChunkManager(chunk_duration_ms=655, logger=self.logger)
        self.is_audio_generating = False
        
        # Event handlers
        self.on_persona_started: Optional[Callable[[str], None]] = None
        self.on_persona_finished: Optional[Callable[[str, str, bytes], None]] = None
        self.on_conversation_complete: Optional[Callable[[], None]] = None
        self.on_audio_chunk: Optional[Callable[[str, str], None]] = None  # New: for streaming audio chunks
        
        # Conversation control
        self.max_turns = 12  # Stop after this many total turns (includes human turns)
        self.current_turn = 0
        
        # Human interaction
        self.human_response_received = False
        self.pending_human_response = None
        self.pending_human_audio = None
        self.is_human_turn = False
        
        # Dynamic speaker selection
        self.selected_next_speaker = None
        self.selection_reason = None
        
        # Event handlers for human interaction
        self.on_human_turn_started: Optional[Callable[[], None]] = None
        self.on_human_turn_ended: Optional[Callable[[], None]] = None
        
        self.logger.info(f"SimpleOrchestrator initialized with {len(personas)} personas + Human")
    
    def _setup_logging(self) -> logging.Logger:
        """Setup logging for the orchestrator"""
        logger = logging.getLogger("SimpleOrchestrator")
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    async def start_conversation_async(self, initial_topic: str = None):
        """Start the orchestrated conversation"""
        if self.is_running:
            self.logger.warning("Conversation already running")
            return
        
        self.is_running = True
        self.current_turn = 0
        self.current_persona_index = 0
        
        topic = initial_topic or "Welcome to our AI podcast! Let's have an engaging discussion about technology and society."
        
        self.logger.info("🎭 Starting orchestrated conversation...")
        self.logger.info(f"🎯 Initial topic: {topic}")
        
        # Start with the first persona
        await self._start_persona_turn(topic)
    
    async def _start_persona_turn(self, prompt: str = None):
        """Start a turn for the current persona"""
        if not self.is_running:
            return
        
        if self.current_turn >= self.max_turns:
            self.logger.info(f"🏁 Conversation complete after {self.current_turn} turns")
            await self._end_conversation()
            return
        
        # Get current persona
        persona = self.personas[self.current_persona_index]
        self.current_speaker = persona.name
        self.is_speaking = True
        self.current_turn += 1
        
        self.logger.info(f"🎤 Turn {self.current_turn}: {persona.name} speaking...")
        
        # Notify listeners
        if self.on_persona_started:
            self.on_persona_started(persona.name)
        
        try:
            # Create conversation context
            context = self._build_conversation_context()
            
            # Build the full prompt - FORCE function calling
            if prompt:
                full_prompt = f"""You are {persona.name} in a HEATED DEBATE about AI and programming.

{context}

1. First, give your passionate 2-sentence response to: {prompt}
2. Then you MUST call the select_next_speaker function to choose who argues next.

Be confrontational and pick someone who disagrees with you!"""
            else:
                full_prompt = f"""You are {persona.name} in a HEATED DEBATE about AI and programming.

{context}

1. First, give your passionate 2-sentence response to what was just said.
2. Then you MUST call the select_next_speaker function to choose who speaks next.

Pick someone you want to challenge or prove wrong!"""
            
            # Get response from Azure OpenAI
            response_text, audio_data = await self._get_persona_response(persona, full_prompt)
            
            # Add to conversation history
            self.conversation_history.append({
                'speaker': persona.name,
                'text': response_text,
                'timestamp': datetime.now(),
                'audio_length': len(audio_data) if audio_data else 0
            })
            
            self.logger.info(f"✅ {persona.name}: {response_text[:100]}...")
            
            # Notify listeners
            if self.on_persona_finished:
                self.on_persona_finished(persona.name, response_text, audio_data)
            
            # Wait for audio to complete using chunk-based timing (same as main orchestrator)
            await self._wait_for_audio_completion_async(persona.name)
            
            # Move to next persona
            await self._move_to_next_persona()
            
        except Exception as ex:
            self.logger.error(f"Error in persona turn: {ex}")
            await self._handle_persona_error(persona.name)
    
    async def _get_persona_response(self, persona: PersonaConfig, prompt: str) -> tuple[str, bytes]:
        """Get response from a persona using OpenAI Realtime API"""
        import websockets
        import json
        import base64
        
        # Build WebSocket URL and headers for OpenAI
        url = self.openai_config.ws_url()
        headers = self.openai_config.headers()
        
        try:
            async with websockets.connect(url, extra_headers=headers) as websocket:
                # Configure session with function calling
                session_config = {
                    "type": "session.update",
                    "session": {
                        "modalities": ["text", "audio"],
                        "instructions": persona.instructions,
                        "voice": persona.voice,
                        "input_audio_format": self.openai_config.input_audio_format,
                        "output_audio_format": self.openai_config.output_audio_format,
                        "temperature": persona.temperature,
                        "max_response_output_tokens": persona.max_response_tokens,
                        "tools": [
                            self._create_speaker_selection_function()
                        ]
                    }
                }
                
                await websocket.send(json.dumps(session_config))
                
                # Check if we have human audio to use as input
                if self.pending_human_audio:
                    self.logger.info(f"🎤 Using human audio input for {persona.name} ({len(self.pending_human_audio)} bytes)")
                    
                    # Send human audio directly as input
                    message = {
                        "type": "conversation.item.create",
                        "item": {
                            "type": "message",
                            "role": "user",
                            "content": [{"type": "input_audio", "audio": base64.b64encode(self.pending_human_audio).decode('utf-8')}]
                        }
                    }
                    
                    # Clear the pending audio so it's only used once
                    self.pending_human_audio = None
                else:
                    # Send text prompt as usual
                    message = {
                        "type": "conversation.item.create",
                        "item": {
                            "type": "message",
                            "role": "user",
                            "content": [{"type": "input_text", "text": prompt}]
                        }
                    }
                
                await websocket.send(json.dumps(message))
                
                # Request response
                response_request = {
                    "type": "response.create",
                    "response": {
                        "modalities": ["text", "audio"]
                    }
                }
                
                await websocket.send(json.dumps(response_request))
                
                # Reset chunk tracking for this persona
                self.audio_chunk_manager.reset_persona_chunks(persona.name)
                self.is_audio_generating = True
                
                # Collect response
                audio_chunks = []
                text_response = ""
                function_calls = []
                selected_next_speaker = None
                selection_reason = None
                
                async for message in websocket:
                    data = json.loads(message)
                    msg_type = data.get("type", "")
                    
                    # Debug: Log all message types to understand the flow
                    if msg_type not in ["response.audio.delta", "response.text.delta"]:
                        self.logger.info(f"📨 {persona.name} received: {msg_type}")
                    
                    if msg_type == "response.audio.delta":
                        audio_data = data.get("delta", "")
                        if audio_data:
                            audio_bytes = base64.b64decode(audio_data)
                            audio_chunks.append(audio_bytes)
                            # Track each chunk (like main orchestrator)
                            self.audio_chunk_manager.track_persona_chunk(persona.name)
                            
                            # CRITICAL: Emit audio chunk immediately for streaming
                            if self.on_audio_chunk:
                                # Convert chunk to WAV format for browser
                                wav_chunk = self._pcm16_to_wav(audio_bytes)
                                chunk_b64 = base64.b64encode(wav_chunk).decode('utf-8')
                                self.on_audio_chunk(persona.name, chunk_b64)
                    
                    elif msg_type == "response.text.delta":
                        text_delta = data.get("delta", "")
                        text_response += text_delta
                    
                    elif msg_type == "response.output_item.added":
                        # Check if this is a function call
                        item = data.get("item", {})
                        if item.get("type") == "function_call":
                            call_id = item.get("call_id")
                            name = item.get("name")
                            arguments = item.get("arguments", "{}")
                            
                            if name == "select_next_speaker":
                                try:
                                    args = json.loads(arguments)
                                    selected_next_speaker = args.get("next_speaker")
                                    selection_reason = args.get("reason")
                                    self.logger.info(f"🎯 {persona.name} selected: {selected_next_speaker} (Reason: {selection_reason})")
                                except Exception as e:
                                    self.logger.error(f"Error parsing function call arguments: {e}")
                    
                    elif msg_type == "response.function_call_arguments.done":
                        # Parse complete function call arguments
                        call_id = data.get("call_id")
                        name = data.get("name")
                        arguments = data.get("arguments", "{}")
                        
                        self.logger.info(f"🔧 Function call completed: {name} with args: {arguments}")
                        
                        if name == "select_next_speaker":
                            try:
                                args = json.loads(arguments)
                                selected_next_speaker = args.get("next_speaker")
                                selection_reason = args.get("reason")
                                self.logger.info(f"🎯 {persona.name} selected: {selected_next_speaker} (Reason: {selection_reason})")
                            except Exception as e:
                                self.logger.error(f"Error parsing function call arguments: {e}")
                    
                    elif msg_type.startswith("response.function_call"):
                        # Log all function call related messages for debugging
                        self.logger.info(f"🔧 Function call event: {msg_type} - {data}")
                    
                    elif msg_type == "response.done":
                        break
                    
                    elif msg_type == "error":
                        raise Exception(f"Azure OpenAI error: {data}")
                
                # Store the selected next speaker
                if selected_next_speaker:
                    self.selected_next_speaker = selected_next_speaker
                    self.selection_reason = selection_reason
                    self.logger.info(f"✅ {persona.name} successfully chose: {selected_next_speaker}")
                else:
                    # Default to random selection if no function call
                    available = [p.name for p in self.personas if p.name != persona.name] + ["Human"]
                    self.selected_next_speaker = random.choice(available)
                    self.selection_reason = "Random selection (no choice made)"
                    self.logger.warning(f"⚠️ {persona.name} didn't call select_next_speaker function! Using random: {self.selected_next_speaker}")
                
                # Mark audio generation as complete
                self.is_audio_generating = False
                
                # For backward compatibility, still return complete audio
                pcm_audio = b''.join(audio_chunks) if audio_chunks else b''
                wav_audio = self._pcm16_to_wav(pcm_audio)
                
                # Log chunk tracking info (like main orchestrator)
                chunk_count = self.audio_chunk_manager.get_persona_chunks(persona.name)
                self.logger.info(f"🎵 Total audio: {len(pcm_audio)} PCM16 bytes -> {len(wav_audio)} WAV bytes ({chunk_count} chunks tracked)")
                
                return text_response.strip(), wav_audio
                
        except Exception as ex:
            self.logger.error(f"Error getting response from {persona.name}: {ex}")
            return f"Hi, I'm {persona.name}. Great to be here!", b''
    
    def _pcm16_to_wav(self, pcm_data: bytes, sample_rate: int = 24000) -> bytes:
        """Convert PCM16 audio data to WAV format for browser playback"""
        import struct
        
        if not pcm_data:
            self.logger.warning("No PCM data to convert")
            return b''
        
        # Validate PCM data size (should be even for 16-bit samples)
        if len(pcm_data) % 2 != 0:
            self.logger.warning(f"PCM data size {len(pcm_data)} is odd, truncating")
            pcm_data = pcm_data[:-1]
        
        # WAV header parameters
        num_channels = 1  # Mono
        bits_per_sample = 16
        byte_rate = sample_rate * num_channels * bits_per_sample // 8
        block_align = num_channels * bits_per_sample // 8
        data_size = len(pcm_data)
        file_size = 36 + data_size
        
        self.logger.debug(f"WAV conversion: {data_size} PCM bytes -> {file_size + 8} WAV bytes ({sample_rate}Hz)")
        
        # Create WAV header (44 bytes total)
        wav_header = struct.pack('<4sL4s4sLHHLLHH4sL',
            b'RIFF',           # ChunkID (4 bytes)
            file_size,         # ChunkSize (4 bytes)  
            b'WAVE',           # Format (4 bytes)
            b'fmt ',           # Subchunk1ID (4 bytes)
            16,                # Subchunk1Size (4 bytes) - PCM
            1,                 # AudioFormat (2 bytes) - PCM
            num_channels,      # NumChannels (2 bytes)
            sample_rate,       # SampleRate (4 bytes)
            byte_rate,         # ByteRate (4 bytes)
            block_align,       # BlockAlign (2 bytes)
            bits_per_sample,   # BitsPerSample (2 bytes)
            b'data',           # Subchunk2ID (4 bytes)
            data_size          # Subchunk2Size (4 bytes)
        )
        
        wav_file = wav_header + pcm_data
        
        # Calculate expected duration for validation
        duration_ms = (len(pcm_data) / 2) / sample_rate * 1000
        self.logger.debug(f"WAV file created: {len(wav_file)} bytes, expected duration: {duration_ms:.1f}ms")
        
        return wav_file
    
    def _build_conversation_context(self) -> str:
        """Build context from recent conversation history with participant info"""
        context_lines = []
        
        # Add participant info
        participants = [p.name for p in self.personas] + ["Human"]
        context_lines.append(f"PARTICIPANTS: {', '.join(participants)}")
        context_lines.append("")
        
        if not self.conversation_history:
            context_lines.append("This is the beginning of our heated debate.")
        else:
            # Get last 4 exchanges for better context
            recent = self.conversation_history[-4:]
            context_lines.append("RECENT CONVERSATION:")
            
            for entry in recent:
                context_lines.append(f"{entry['speaker']}: {entry['text']}")
        
        return "\n".join(context_lines)
    
    async def _wait_for_audio_completion_async(self, persona_name: str):
        """Wait for audio generation and playback to complete (same as main orchestrator)"""
        self.logger.info(f"🕒 Waiting for audio completion for {persona_name}")
        
        # Get chunk count for this persona
        persona_chunks = self.audio_chunk_manager.get_persona_chunks(persona_name)
        
        # Calculate wait time (655ms per chunk)
        wait_time_ms = self.audio_chunk_manager.calculate_wait_time(persona_name)
        
        self.logger.info(f"🎵 Audio stats for {persona_name}: {persona_chunks} chunks × 655ms = {wait_time_ms}ms")
        
        # Wait locally (no media stream in simple orchestrator)
        if wait_time_ms > 0:
            await asyncio.sleep(wait_time_ms / 1000)
        
        # Safety check for ongoing audio
        safety_wait_count = 0
        while self.is_audio_generating and safety_wait_count < 50:
            await asyncio.sleep(0.1)
            safety_wait_count += 1
        
        if self.is_audio_generating:
            self.logger.warning(f"⚠️ Audio generation timeout for {persona_name} - proceeding anyway")
            self.is_audio_generating = False
        
        self.logger.info(f"🎯 Audio completion confirmed for {persona_name}")
    
    async def _move_to_next_persona(self):
        """Move to the dynamically selected next speaker"""
        self.is_speaking = False
        self.current_speaker = None
        self.is_human_turn = False
        
        # Use the selected next speaker and immediately clear it to avoid sticky selections
        next_speaker = self.selected_next_speaker
        self.selected_next_speaker = None  # Prevent repeated Human turns or stale selections
        if not next_speaker:
            # Fallback to first persona if no selection
            next_speaker = self.personas[0].name
        
        # Log the transition
        self.logger.info(f"🔄 Transitioning to {next_speaker} ({self.selection_reason or 'No reason given'})")
        
        # Update current persona index for the selected speaker
        if next_speaker != "Human":
            for i, persona in enumerate(self.personas):
                if persona.name == next_speaker:
                    self.current_persona_index = i
                    break
        
        # Pause between speakers
        if self.turn_delay_seconds > 0:
            self.logger.info(f"⏸️ Pausing {self.turn_delay_seconds}s before next speaker...")
            await asyncio.sleep(self.turn_delay_seconds)
        
        # Start next turn
        if next_speaker == "Human":
            await self._start_human_turn()
        else:
            await self._start_persona_turn()
        
        # After the human speaks, randomly choose an AI persona (never Human) to continue the discussion
        ai_personas = [p.name for p in self.personas]
        self.selected_next_speaker = random.choice(ai_personas)
        self.selection_reason = "Random AI persona after human turn"
    
    def _get_available_speakers(self) -> List[str]:
        """Get list of all available speakers (including Human)"""
        speakers = [persona.name for persona in self.personas]
        speakers.append("Human")
        return speakers
    
    def _create_speaker_selection_function(self) -> dict:
        """Create the function definition for speaker selection"""
        available_speakers = self._get_available_speakers()
        
        return {
            "type": "function",
            "name": "select_next_speaker",
            "description": "Choose who should speak next in this heated discussion. Pick strategically based on the conversation flow and who you want to challenge or respond to your points.",
            "parameters": {
                "type": "object",
                "properties": {
                    "next_speaker": {
                        "type": "string",
                        "enum": available_speakers,
                        "description": f"Choose from: {', '.join(available_speakers)}"
                    },
                    "reason": {
                        "type": "string", 
                        "description": "Why you chose this person to speak next (e.g., 'I want to challenge Sam's point about AI safety' or 'Jordan always has practical insights on this')"
                    }
                },
                "required": ["next_speaker", "reason"]
            }
        }
    
    async def _handle_persona_error(self, persona_name: str):
        """Handle errors in persona turns"""
        self.logger.error(f"❌ Error with {persona_name}, moving to next persona")
        
        self.is_speaking = False
        self.current_speaker = None
        
        # Add error to history
        self.conversation_history.append({
            'speaker': persona_name,
            'text': f"[ERROR: {persona_name} encountered an issue]",
            'timestamp': datetime.now(),
            'audio_length': 0
        })
        
        # Move to next persona after error
        await asyncio.sleep(1.0)
        await self._move_to_next_persona()
    
    async def _start_human_turn(self):
        """Start the human's turn to speak"""
        self.logger.info("=== STARTING HUMAN TURN ===")
        
        self.current_speaker = "Human"
        self.is_human_turn = True
        self.human_response_received = False
        self.current_turn += 1
        
        self.logger.info(f"🎤 Turn {self.current_turn}: Human speaking...")
        
        # Notify web interface to show microphone
        if self.on_human_turn_started:
            self.on_human_turn_started()
        
        # Wait for human response (with timeout)
        timeout_counter = 0
        max_timeout = 30  # 30 seconds to respond
        
        while not self.human_response_received and timeout_counter < max_timeout and self.is_running:
            await asyncio.sleep(0.5)
            timeout_counter += 0.5
        
        if timeout_counter >= max_timeout:
            self.logger.warning("⏰ Human response timeout - using default response")
            self.pending_human_response = "I think this is really interesting, please continue."
        
        # Add human response to conversation history
        if self.pending_human_response:
            self.conversation_history.append({
                'speaker': 'Human',
                'text': self.pending_human_response,
                'timestamp': datetime.now(),
                'audio_length': 0
            })
            
            self.logger.info(f"✅ Human: {self.pending_human_response}")
        
        # Notify web interface to hide microphone
        if self.on_human_turn_ended:
            self.on_human_turn_ended()
        
        self.is_human_turn = False
        self.current_speaker = None
        
        # Move to next persona
        await self._move_to_next_persona()
    
    def add_human_response(self, transcription: str):
        """Add a human response from transcription"""
        self.logger.info(f"🎤 Received human response: {transcription}")
        self.pending_human_response = transcription
        self.human_response_received = True
    
    def add_human_audio(self, audio_data: bytes):
        """Add a human response from raw audio - pass directly to next persona"""
        self.logger.info(f"🎤 Received human audio: {len(audio_data)} bytes - passing to next persona")
        
        # Store the audio data to be used as input for the next persona
        self.pending_human_audio = audio_data
        self.human_response_received = True
        
        # For conversation history, we'll mark it as audio input
        self.pending_human_response = "[Human spoke via microphone]"

    async def _end_conversation(self):
        """End the orchestrated conversation"""
        self.is_running = False
        self.is_speaking = False
        self.current_speaker = None
        self.is_human_turn = False
        
        self.logger.info("🎬 Conversation ended")
        self.logger.info(f"📊 Total turns: {len(self.conversation_history)}")
        
        # Notify listeners
        if self.on_conversation_complete:
            self.on_conversation_complete()
    
    # Control methods
    def stop_conversation(self):
        """Stop the conversation"""
        self.logger.info("🛑 Stopping conversation...")
        self.is_running = False
    
    def get_current_speaker(self) -> Optional[str]:
        """Get the name of the currently speaking persona"""
        return self.current_speaker
    
    def is_conversation_active(self) -> bool:
        """Check if conversation is currently active"""
        return self.is_running
    
    def get_conversation_summary(self) -> dict:
        """Get a summary of the conversation"""
        return {
            'total_turns': len(self.conversation_history),
            'current_turn': self.current_turn,
            'current_speaker': self.current_speaker,
            'personas': [p.name for p in self.personas],
            'is_active': self.is_running,
            'history': self.conversation_history[-5:]  # Last 5 entries
        }


# Example usage
async def example_orchestrator():
    """Example of how to use the SimpleOrchestrator"""
    
    # Define personas
    personas = [
        PersonaConfig(
            name="Alex",
            voice="ballard",
            instructions="You are Alex, an enthusiastic tech podcaster. Keep responses to 1-2 sentences and be engaging.",
            temperature=0.8
        ),
        PersonaConfig(
            name="Sam",
            voice="ash", 
            instructions="You are Sam, a thoughtful researcher. Provide analytical perspectives in 1-2 sentences.",
            temperature=0.7
        ),
        PersonaConfig(
            name="Jordan",
            voice="shimmer",
            instructions="You are Jordan, a practical developer. Give real-world insights in 1-2 sentences.",
            temperature=0.6
        )
    ]
    
    # OpenAI config
    from openai_config import OPENAI_REALTIME_CONFIG
    
    # Create orchestrator
    orchestrator = SimpleOrchestrator(personas, OPENAI_REALTIME_CONFIG)
    
    # Set up event handlers
    orchestrator.on_persona_started = lambda name: print(f"🎤 {name} is speaking...")
    orchestrator.on_persona_finished = lambda name, text, audio: print(f"✅ {name}: {text[:100]}... (audio: {len(audio)} bytes)")
    orchestrator.on_conversation_complete = lambda: print("🎬 Conversation complete!")
    
    # Start conversation
    await orchestrator.start_conversation_async(
        "Welcome everyone! Today we're discussing the future of AI in software development."
    )


if __name__ == "__main__":
    asyncio.run(example_orchestrator()) 