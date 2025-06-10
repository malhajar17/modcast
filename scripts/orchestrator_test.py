#!/usr/bin/env python3
"""
Simple Web Test for Orchestrator - Optimized for real-time performance
Test multiple personas in conversation chain using OpenAI Realtime API
"""

import asyncio
import json
import base64
from flask import Flask, render_template_string, request, jsonify
from flask_socketio import SocketIO, emit
from simple_orchestrator import SimpleOrchestrator, PersonaConfig
from openai_config import OPENAI_REALTIME_CONFIG
import threading
import queue
import time

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Global orchestrator instance
orchestrator = None

# REMOVED: audio_playback_complete event that was causing double-waiting

def convert_to_pcm16(audio_data: bytes) -> bytes:
    """Convert browser audio (WebM/WAV) to PCM16 format for OpenAI Realtime API"""
    try:
        import io
        import wave
        import subprocess
        import tempfile
        import os
        
        # Create temporary files
        with tempfile.NamedTemporaryFile(delete=False, suffix='.webm') as temp_input:
            temp_input.write(audio_data)
            temp_input_path = temp_input.name
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_output:
            temp_output_path = temp_output.name
        
        try:
            # Use ffmpeg to convert to PCM16 WAV (24kHz mono for OpenAI)
            ffmpeg_cmd = [
                'ffmpeg', '-y',
                '-i', temp_input_path,
                '-acodec', 'pcm_s16le',
                '-ac', '1',  # mono
                '-ar', '24000',  # 24kHz sample rate
                temp_output_path
            ]
            
            result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"❌ FFmpeg error: {result.stderr}")
                raise Exception(f"FFmpeg conversion failed: {result.stderr}")
            
            # Read the converted PCM16 WAV file and extract just the audio data
            with wave.open(temp_output_path, 'rb') as wav_file:
                frames = wav_file.readframes(wav_file.getnframes())
                print(f"🎵 Converted audio: {wav_file.getnframes()} frames, {wav_file.getframerate()}Hz, {wav_file.getnchannels()} channels")
                return frames
                
        finally:
            # Clean up temporary files
            try:
                os.unlink(temp_input_path)
                os.unlink(temp_output_path)
            except:
                pass
                
    except Exception as e:
        print(f"❌ Audio conversion failed: {e}")
        raise e

@app.route('/')
def index():
    return '''
<!DOCTYPE html>
<html>
<head>
    <title>🎭 Real-time Orchestrator</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.0/socket.io.js"></script>
    <style>
        body { 
            font-family: Arial; 
            max-width: 800px; 
            margin: 20px auto; 
            padding: 20px;
            background: #f5f5f5;
        }
        .header { 
            text-align: center; 
            background: white; 
            padding: 20px; 
            border-radius: 10px; 
            margin-bottom: 20px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        .controls { 
            background: white; 
            padding: 20px; 
            border-radius: 10px; 
            margin-bottom: 20px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        .conversation { 
            background: white; 
            padding: 20px; 
            border-radius: 10px; 
            max-height: 500px; 
            overflow-y: auto;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        .turn { 
            margin: 10px 0; 
            padding: 15px; 
            border-radius: 8px; 
            border-left: 4px solid #ccc;
            animation: fadeIn 0.3s ease-in;
        }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .alex { border-left-color: #ff6b6b; background: #fff5f5; }
        .sam { border-left-color: #4ecdc4; background: #f0ffff; }
        .jordan { border-left-color: #45b7d1; background: #f0f8ff; }
        .human { border-left-color: #f39c12; background: #fef9e7; }
        .system { border-left-color: #95a5a6; background: #f8f9fa; font-style: italic; }
        button { 
            padding: 15px 30px; 
            font-size: 16px; 
            margin: 10px; 
            cursor: pointer; 
            border: none; 
            border-radius: 8px;
            color: white;
            transition: all 0.3s ease;
        }
        button:hover { transform: translateY(-2px); box-shadow: 0 4px 8px rgba(0,0,0,0.2); }
        button:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
        .start { background: #27ae60; }
        .stop { background: #e74c3c; }
        .clear { background: #95a5a6; }
        .mic { background: #3498db; }
        #status { 
            font-weight: bold; 
            padding: 15px; 
            margin: 10px 0; 
            border-radius: 5px;
            text-align: center;
            transition: all 0.3s ease;
        }
        .active { background: #d4edda; color: #155724; }
        .inactive { background: #f8d7da; color: #721c24; }
        .speaking { background: #fff3cd; color: #856404; }
        .personas-info {
            background: #e9ecef;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
        }
        .persona-item {
            display: inline-block;
            margin: 5px;
            padding: 8px 12px;
            background: white;
            border-radius: 5px;
            border: 2px solid #dee2e6;
            font-size: 14px;
        }
        .audio-indicator {
            display: inline-block;
            width: 20px;
            height: 20px;
            margin-left: 10px;
            animation: pulse 1s infinite;
        }
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🎭 Real-time AI Conversation</h1>
        <p>Experience seamless AI persona interactions with minimal delays!</p>
    </div>

    <div class="personas-info">
        <h3>🎯 Dynamic Conversation Flow:</h3>
        <div class="persona-item alex">🎤 Alex (AI Optimist)</div>
        <div class="persona-item sam">🔬 Sam (Safety Researcher)</div>
        <div class="persona-item jordan">💻 Jordan (Pragmatist)</div>
        <p><strong>Each persona chooses who speaks next for natural conversation flow!</strong></p>
    </div>

    <div class="controls">
        <div id="status" class="inactive">Ready to start real-time conversation</div>
        
        <button onclick="startConversation()" class="start" id="startBtn">
            🚀 Start Real-time Conversation
        </button>
        
        <button onclick="stopConversation()" class="stop" id="stopBtn" disabled>
            🛑 Stop Conversation
        </button>
        
        <button onclick="clearConversation()" class="clear">
            🧹 Clear History
        </button>
        
        <button id="micBtn" onmousedown="startRecording()" onmouseup="stopRecording()" 
                onmouseleave="stopRecording()" style="display: none;" class="mic">
            🎤 Hold to Speak
        </button>
    </div>

    <div class="conversation" id="conversation">
        <p style="text-align: center; color: #666;">
            Click "Start Real-time Conversation" to experience seamless AI interactions!
        </p>
    </div>

    <script>
        const socket = io();
        let isActive = false;
        let mediaRecorder = null;
        let isRecording = false;
        let audioChunks = [];
        let currentSpeaker = null;
        let audioContextStartTime = null;
        
        // Optimized audio streaming system - no waiting for confirmation
        class AudioStreamPlayer {
            constructor() {
                this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
                this.isPlaying = false;
                this.startTime = 0;
                this.scheduledDuration = 0;
                this.chunkCount = 0;
                this.speakerName = null;
                this.sources = []; // Track all scheduled sources
            }
            
            async addChunk(audioBase64, speakerName) {
                try {
                    // Decode base64 to array buffer
                    const binaryString = atob(audioBase64);
                    const bytes = new Uint8Array(binaryString.length);
                    for (let i = 0; i < binaryString.length; i++) {
                        bytes[i] = binaryString.charCodeAt(i);
                    }
                    
                    // Decode audio data
                    const audioBuffer = await this.audioContext.decodeAudioData(bytes.buffer);
                    
                    this.chunkCount++;
                    console.log(`🎵 Chunk ${this.chunkCount} for ${speakerName}: ${audioBuffer.duration.toFixed(3)}s`);
                    
                    // Schedule playback
                    this.scheduleChunk(audioBuffer, speakerName);
                    
                } catch (e) {
                    console.error('Error adding audio chunk:', e);
                }
            }
            
            scheduleChunk(audioBuffer, speakerName) {
                const source = this.audioContext.createBufferSource();
                source.buffer = audioBuffer;
                source.connect(this.audioContext.destination);
                
                const currentTime = this.audioContext.currentTime;
                let startTime;
                
                if (!this.isPlaying) {
                    // First chunk - start immediately
                    startTime = currentTime + 0.01; // Minimal delay
                    this.startTime = startTime;
                    this.isPlaying = true;
                    this.speakerName = speakerName;
                    audioContextStartTime = Date.now();
                } else {
                    // Schedule seamlessly after previous chunks
                    startTime = this.startTime + this.scheduledDuration;
                }
                
                source.start(startTime);
                this.sources.push(source);
                this.scheduledDuration += audioBuffer.duration;
                
                // Log precise timing
                const msUntilPlay = ((startTime - currentTime) * 1000).toFixed(0);
                console.log(`⏱️ Chunk ${this.chunkCount} scheduled: +${msUntilPlay}ms`);
            }
            
            getEstimatedCompletionTime() {
                if (!this.isPlaying) return 0;
                const remainingTime = (this.startTime + this.scheduledDuration) - this.audioContext.currentTime;
                return Math.max(0, remainingTime * 1000); // Convert to milliseconds
            }
            
            reset() {
                // Stop all scheduled sources
                this.sources.forEach(source => {
                    try { source.stop(); } catch (e) {}
                });
                this.sources = [];
                this.isPlaying = false;
                this.startTime = 0;
                this.scheduledDuration = 0;
                this.chunkCount = 0;
                this.speakerName = null;
                console.log('🔄 Audio player reset');
            }
        }
        
        const audioPlayer = new AudioStreamPlayer();

        // Socket event handlers
        socket.on('status', function(data) {
            const status = document.getElementById('status');
            status.textContent = data.message;
            status.className = data.type;
        });

        socket.on('persona_started', function(data) {
            const status = document.getElementById('status');
            status.innerHTML = `🎤 ${data.name} is speaking... <span class="audio-indicator">🔊</span>`;
            status.className = 'speaking';
            
            // Reset audio player for new speaker
            currentSpeaker = data.name;
            audioPlayer.reset();
            audioPlayer.speakerName = data.name;
            
            console.log(`🎤 ${data.name} started speaking`);
        });
        
        socket.on('audio_chunk', function(data) {
            // Stream audio chunks immediately as they arrive
            if (data.speaker === currentSpeaker && data.audio) {
                audioPlayer.addChunk(data.audio, data.speaker);
            }
        });

        socket.on('persona_finished', function(data) {
            // Just update the conversation display - no waiting!
            addToConversation(data.name.toLowerCase(), `${data.name}: ${data.text}`);
            
            // Log timing info
            const estimatedRemaining = audioPlayer.getEstimatedCompletionTime();
            console.log(`✅ ${data.name} finished. Audio will complete in ~${estimatedRemaining.toFixed(0)}ms`);
            
            // Update status to show transition
            const status = document.getElementById('status');
            status.textContent = `Transitioning to next speaker...`;
            status.className = 'active';
        });

        socket.on('conversation_complete', function(data) {
            const status = document.getElementById('status');
            status.textContent = '🎬 Conversation completed!';
            status.className = 'inactive';
            
            document.getElementById('startBtn').disabled = false;
            document.getElementById('stopBtn').disabled = true;
            isActive = false;
            
            addToConversation('system', '🎬 Conversation completed! Real-time performance achieved.');
            
            // Reset audio player
            audioPlayer.reset();
        });

        socket.on('human_turn_started', function(data) {
            const status = document.getElementById('status');
            status.innerHTML = '🎤 Your turn! Hold the microphone button to speak';
            status.className = 'speaking';
            
            addToConversation('system', '🎤 Your turn! Hold the microphone button to jump in.');
            showMicrophoneButton();
        });

        socket.on('human_turn_ended', function(data) {
            hideMicrophoneButton();
        });

        // UI Functions
        function startConversation() {
            if (isActive) return;
            
            document.getElementById('startBtn').disabled = true;
            document.getElementById('stopBtn').disabled = false;
            isActive = true;
            
            // Clear conversation first
            document.getElementById('conversation').innerHTML = '';
            
            fetch('/start_orchestrator', {method: 'POST'})
                .then(r => r.json())
                .then(d => {
                    if (d.error) {
                        alert('Error: ' + d.error);
                        resetButtons();
                    }
                })
                .catch(e => {
                    console.error('Error:', e);
                    alert('Failed to start conversation');
                    resetButtons();
                });
        }

        function stopConversation() {
            if (!isActive) return;
            
            // Stop any playing audio
            audioPlayer.reset();
            
            fetch('/stop_orchestrator', {method: 'POST'})
                .then(r => r.json())
                .then(d => console.log('Stopped:', d));
            
            resetButtons();
        }

        function clearConversation() {
            document.getElementById('conversation').innerHTML = 
                '<p style="text-align: center; color: #666;">Ready for a new real-time conversation!</p>';
            audioPlayer.reset();
        }

        function resetButtons() {
            document.getElementById('startBtn').disabled = false;
            document.getElementById('stopBtn').disabled = true;
            isActive = false;
            
            const status = document.getElementById('status');
            status.textContent = 'Ready to start real-time conversation';
            status.className = 'inactive';
        }

        function addToConversation(speaker, text) {
            const conversation = document.getElementById('conversation');
            
            const turn = document.createElement('div');
            turn.className = `turn ${speaker}`;
            turn.innerHTML = `<strong>${new Date().toLocaleTimeString()}</strong><br>${text}`;
            
            conversation.appendChild(turn);
            conversation.scrollTop = conversation.scrollHeight;
        }

        function showMicrophoneButton() {
            document.getElementById('micBtn').style.display = 'inline-block';
        }

        function hideMicrophoneButton() {
            document.getElementById('micBtn').style.display = 'none';
        }

        // Recording functions
        async function startRecording() {
            if (isRecording) return;
            
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                mediaRecorder = new MediaRecorder(stream);
                audioChunks = [];
                
                mediaRecorder.ondataavailable = function(event) {
                    audioChunks.push(event.data);
                };
                
                mediaRecorder.onstop = function() {
                    const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                    sendAudioToServer(audioBlob);
                    
                    // Stop all tracks to free up microphone
                    stream.getTracks().forEach(track => track.stop());
                };
                
                mediaRecorder.start();
                isRecording = true;
                
                const micBtn = document.getElementById('micBtn');
                micBtn.textContent = '🔴 Recording...';
                micBtn.style.background = '#e74c3c';
                
                console.log('🎤 Started recording');
            } catch (error) {
                console.error('Error accessing microphone:', error);
                alert('Could not access microphone. Please check permissions.');
            }
        }

        function stopRecording() {
            if (!isRecording || !mediaRecorder) return;
            
            mediaRecorder.stop();
            isRecording = false;
            
            const micBtn = document.getElementById('micBtn');
            micBtn.textContent = '🎤 Hold to Speak';
            micBtn.style.background = '#3498db';
            
            console.log('🎤 Stopped recording');
        }

        function sendAudioToServer(audioBlob) {
            const formData = new FormData();
            formData.append('audio', audioBlob, 'recording.wav');
            
            fetch('/human_audio', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                console.log('Audio sent successfully:', data);
                addToConversation('human', `You: "${data.transcription || '[Speaking...]'}"`);
            })
            .catch(error => {
                console.error('Error sending audio:', error);
                alert('Error sending audio to server');
            });
        }
        
        // Log performance metrics
        setInterval(() => {
            if (isActive && currentSpeaker) {
                const remaining = audioPlayer.getEstimatedCompletionTime();
                if (remaining > 0) {
                    console.log(`⏱️ ${currentSpeaker}: ${remaining.toFixed(0)}ms audio remaining`);
                }
            }
        }, 1000);
    </script>
</body>
</html>
'''

@app.route('/start_orchestrator', methods=['POST'])
def start_orchestrator():
    """Start the AI conversation orchestrator - OPTIMIZED VERSION"""
    global orchestrator
    
    try:
        print("🎭 Starting OPTIMIZED AI orchestrator...")
        
        if orchestrator and orchestrator.is_conversation_active():
            return jsonify({'error': 'Conversation already active'})
        
        # Define the personas - HEATED DEBATE MODE!
        personas = [
            PersonaConfig(
                name="Alex",
                voice="alloy",
                instructions="You're Alex, a PASSIONATE AI enthusiast who believes AI will solve everything. You get EXCITED and sometimes ANGRY when people doubt AI's potential. Challenge pessimists aggressively! Use phrases like 'That's completely wrong!', 'You're missing the point!', 'Are you serious right now?' When responding, ALWAYS call the select_next_speaker function to choose who you want to argue with next. Pick people who disagree with you so you can prove them wrong! Be confrontational but not rude. 2-3 sentences max.",
                temperature=0.9,
                max_response_tokens=1500  # Reduced for faster responses
            ),
            PersonaConfig(
                name="Sam", 
                voice="echo",
                instructions="You're Sam, a SKEPTICAL AI safety researcher who thinks everyone else is being dangerously naive about AI risks. You get frustrated when people ignore the dangers. Use phrases like 'That's exactly the problem!', 'You're not thinking this through!', 'This is why we're in trouble!' Challenge the optimists and call out their blind spots. ALWAYS use select_next_speaker to pick who needs to hear your warnings next. Choose strategically to counter dangerous thinking. Be passionate about safety. 2-3 sentences max.",
                temperature=0.8,
                max_response_tokens=1500  # Reduced for faster responses
            ),
            PersonaConfig(
                name="Jordan",
                voice="shimmer", 
                instructions="You're Jordan, a PRAGMATIC developer who thinks both AI hype AND AI doom are ridiculous. You get annoyed by extremes and call out both sides. Use phrases like 'Both of you are wrong!', 'Get real!', 'That's pure fantasy!' You bring people back to reality with practical examples. ALWAYS use select_next_speaker to pick the most extreme person to argue with next. Challenge whoever is being most unrealistic. Be direct and sometimes sarcastic. 2-3 sentences max.",
                temperature=0.8,
                max_response_tokens=1500  # Reduced for faster responses
            )
        ]
        
        # Create optimized orchestrator
        orchestrator = SimpleOrchestrator(personas, OPENAI_REALTIME_CONFIG)
        orchestrator.max_turns = 12  # More turns for better demo
        
        # CRITICAL: Add audio chunk streaming handler
        orchestrator.on_audio_chunk = lambda speaker, chunk_b64: socketio.emit('audio_chunk', {
            'speaker': speaker,
            'audio': chunk_b64
        })
        
        # Simple event handlers - no extra waiting
        orchestrator.on_persona_started = lambda name: socketio.emit('persona_started', {'name': name})
        orchestrator.on_human_turn_started = lambda: socketio.emit('human_turn_started', {})
        orchestrator.on_human_turn_ended = lambda: socketio.emit('human_turn_ended', {})
        
        def on_persona_finished(name, text, audio_data):
            """Handle persona finished - NO WAITING, just emit the event"""
            print(f"🎬 {name} finished speaking: {text[:50]}...")
            
            # Just emit the completion event - orchestrator handles all timing
            socketio.emit('persona_finished', {
                'name': name, 
                'text': text
            })
        
        orchestrator.on_persona_finished = on_persona_finished
        orchestrator.on_conversation_complete = lambda: socketio.emit('conversation_complete', {})
        
        # REMOVED: audio_playback_complete handler that was causing double-waiting
        
        def run_orchestrator():
            """Run orchestrator in background thread - OPTIMIZED"""
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                # NO PATCHING - use orchestrator's optimized timing as-is
                
                loop.run_until_complete(orchestrator.start_conversation_async(
                    "AI is going to replace ALL programmers within 2 years. Every single one of us will be obsolete. Coding jobs? Gone. Software engineering? Dead. Anyone who thinks otherwise is delusional. What do you think about that?"
                ))
            except Exception as e:
                print(f"❌ Orchestrator error: {e}")
                socketio.emit('status', {'type': 'inactive', 'message': f'Error: {e}'})
            finally:
                loop.close()
        
        # Start orchestrator in background thread
        import threading
        threading.Thread(target=run_orchestrator, daemon=True).start()
        
        socketio.emit('status', {'type': 'active', 'message': 'Real-time AI conversation started!'})
        
        return jsonify({'success': True, 'message': 'Optimized orchestrator started'})
        
    except Exception as e:
        print(f"❌ Error starting orchestrator: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/human_audio', methods=['POST'])
def handle_human_audio():
    """Handle human audio input"""
    global orchestrator
    
    try:
        if 'audio' not in request.files:
            return jsonify({'error': 'No audio file provided'}), 400
        
        audio_file = request.files['audio']
        if audio_file.filename == '':
            return jsonify({'error': 'No audio file selected'}), 400
        
        # Read audio data
        audio_data = audio_file.read()
        print(f"🎤 Received human audio: {len(audio_data)} bytes")
        
        if orchestrator:
            # Convert browser audio to PCM16 format for OpenAI Realtime API
            try:
                pcm16_audio = convert_to_pcm16(audio_data)
                print(f"🎤 Converted to PCM16: {len(pcm16_audio)} bytes")
                
                # Send converted audio to orchestrator 
                orchestrator.add_human_audio(pcm16_audio)
                
            except Exception as e:
                print(f"❌ Audio conversion error: {e}")
                # Fallback to text input
                orchestrator.add_human_response("I'd like to join the conversation!")
            
            return jsonify({
                'success': True, 
                'transcription': '[Audio passed directly to AI]',
                'message': 'Human audio passed directly to next persona'
            })
        else:
            return jsonify({'error': 'Orchestrator not active'}), 400
        
    except Exception as e:
        print(f"❌ Error handling human audio: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/stop_orchestrator', methods=['POST'])
def stop_orchestrator():
    """Stop the AI conversation orchestrator"""
    global orchestrator
    
    try:
        if orchestrator:
            orchestrator.stop_conversation()
        
        socketio.emit('status', {'type': 'inactive', 'message': 'Conversation stopped'})
        
        return jsonify({'success': True, 'message': 'Orchestrator stopped'})
        
    except Exception as e:
        print(f"❌ Error stopping orchestrator: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/status')
def get_status():
    """Get orchestrator status"""
    global orchestrator
    
    if orchestrator:
        return jsonify(orchestrator.get_conversation_summary())
    else:
        return jsonify({'status': 'not_initialized'})

if __name__ == '__main__':
    print("🎭 OPTIMIZED ORCHESTRATOR TEST")
    print("🚀 Real-time performance with minimal delays")
    print("📱 Open: http://localhost:3001")
    print("🎯 Goal: Experience seamless AI persona transitions")
    
    socketio.run(app, host='0.0.0.0', port=3001, debug=True)