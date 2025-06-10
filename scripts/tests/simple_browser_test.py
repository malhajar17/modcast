#!/usr/bin/env python3
"""
EXACT replication of openai-realtime-py flow for OpenAI Realtime API
Based on https://github.com/p-i-/openai-realtime-py
"""
import asyncio
import websockets
import json
import base64
import tempfile
import os
import struct
import math
import subprocess
import threading
from pathlib import Path
from flask import Flask, jsonify, request
from flask_socketio import SocketIO, emit

# Try to load .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ---------------------------------------------------------------- CONSTANTS
API_KEY = os.getenv("OPENAI_API_KEY")
MODEL = "gpt-4o-realtime-preview"
VOICE = "alloy"
TARGET_SR = 24000  # Back to 24kHz as used in openai-realtime-py

# Flask app setup
app = Flask(__name__)
app.config['SECRET_KEY'] = 'simple-test-key'
socketio = SocketIO(app, cors_allowed_origins="*")

def log(*args):
    print("🔹", *args, flush=True)

def convert_webm_to_pcm16(webm_data, target_sample_rate=TARGET_SR):
    """Convert WebM to PCM16 using the exact approach from openai-realtime-py"""
    if len(webm_data) < 1000:
        log("WebM data too small, using silence fallback")
        return b"\x00\x00" * int(target_sample_rate * 0.5)  # 500ms silence
    
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as temp_input:
        temp_input.write(webm_data)
        temp_input_path = temp_input.name
    
    try:
        # Use subprocess for maximum compatibility (like openai-realtime-py)
        cmd = [
            'ffmpeg', '-y', '-i', temp_input_path,
            '-acodec', 'pcm_s16le',  # 16-bit PCM little endian
            '-ac', '1',              # Mono
            '-ar', str(target_sample_rate),  # Sample rate
            '-f', 's16le',           # Raw PCM16 format
            'pipe:1'
        ]
        
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        if result.returncode != 0:
            log(f"FFmpeg error: {result.stderr.decode()[:200]}")
            raise RuntimeError("FFmpeg conversion failed")
        
        pcm_data = result.stdout
        
        if len(pcm_data) < 2:
            raise RuntimeError("No PCM data produced")
        
        # Calculate duration
        samples = len(pcm_data) // 2
        duration_ms = (samples / target_sample_rate) * 1000
        
        log(f"Converted: {len(pcm_data)} bytes PCM, {duration_ms:.1f}ms, {samples} samples")
        
        # Ensure minimum 100ms for OpenAI
        min_duration_ms = 100
        min_samples = int((min_duration_ms / 1000) * target_sample_rate)
        min_bytes = min_samples * 2
        
        if len(pcm_data) < min_bytes:
            log(f"Padding audio from {duration_ms:.1f}ms to {min_duration_ms}ms")
            padding = min_bytes - len(pcm_data)
            pcm_data = pcm_data + b'\x00' * padding
        
        return pcm_data
        
    except Exception as e:
        log(f"Audio conversion error: {e}")
        # Fallback: 500ms of silence
        samples = int(target_sample_rate * 0.5)
        return b'\x00\x00' * samples
    finally:
        try:
            os.unlink(temp_input_path)
        except:
            pass

async def call_openai_realtime(audio_pcm16: bytes):
    """Call OpenAI Realtime API using the exact flow from openai-realtime-py"""
    if not API_KEY:
        raise RuntimeError("OPENAI_API_KEY missing")
    
    url = f"wss://api.openai.com/v1/realtime?model={MODEL}"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "OpenAI-Beta": "realtime=v1",
    }
    
    log("Connecting to OpenAI Realtime API...")
    
    async with websockets.connect(url, extra_headers=headers) as ws:
        log("✅ Connected to OpenAI")
        
        # 1. Configure session (exact format from openai-realtime-py)
        session_config = {
            "type": "session.update",
            "session": {
                "modalities": ["text", "audio"],
                "instructions": "You are a helpful AI assistant. Please respond naturally and helpfully.",
                "voice": VOICE,
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.5,
                    "prefix_padding_ms": 300,
                    "silence_duration_ms": 200
                },
                "temperature": 0.8
            }
        }
        
        await ws.send(json.dumps(session_config))
        log("📋 Session configured")
        
        # 2. Create conversation item with audio (exact format from openai-realtime-py)
        audio_b64 = base64.b64encode(audio_pcm16).decode('utf-8')
        
        conversation_item = {
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "user",
                "content": [
                    {
                        "type": "input_audio",
                        "audio": audio_b64
                    }
                ]
            }
        }
        
        await ws.send(json.dumps(conversation_item))
        log("🎤 Audio message created")
        
        # 3. Request response
        response_request = {
            "type": "response.create",
            "response": {
                "modalities": ["text", "audio"]
            }
        }
        
        await ws.send(json.dumps(response_request))
        log("🤖 Response requested")
        
        # Notify browser to reset audio streaming
        socketio.emit('status', {
            'type': 'info',
            'message': '🤖 Response requested - streaming audio...'
        })
        
        # 4. Collect audio response chunks
        audio_chunks = []
        text_parts = []
        
        async for message in ws:
            data = json.loads(message)
            msg_type = data.get("type", "")
            
            log(f"📨 Received: {msg_type}")
            
            if msg_type == "response.audio.delta":
                audio_chunk = data.get("delta", "")
                if audio_chunk:
                    decoded_chunk = base64.b64decode(audio_chunk)
                    audio_chunks.append(decoded_chunk)
                    log(f"🎵 Audio chunk: {len(decoded_chunk)} bytes")
                    
                    # 🎵 STREAM EACH DELTA IMMEDIATELY
                    socketio.emit('ai_audio_delta', {
                        'audio_data': audio_chunk,  # Send base64 directly
                        'chunk_bytes': len(decoded_chunk)
                    })
            
            elif msg_type == "response.text.delta":
                text_delta = data.get("delta", "")
                if text_delta:
                    text_parts.append(text_delta)
                    log(f"📝 Text: '{text_delta}'")
            
            elif msg_type == "response.audio.done":
                log("🏁 Audio response complete")
                # Send final status
                socketio.emit('ai_audio_complete', {
                    'total_chunks': len(audio_chunks),
                    'total_bytes': sum(len(chunk) for chunk in audio_chunks),
                    'text': "".join(text_parts)
                })
                break
            
            elif msg_type == "error":
                log(f"❌ OpenAI error: {data}")
                raise RuntimeError(f"OpenAI error: {data}")
        
        final_audio = b"".join(audio_chunks)
        final_text = "".join(text_parts)
        
        log(f"✅ Response complete: {len(final_audio)} bytes audio, text: '{final_text}'")
        
        return final_audio, final_text

@app.route('/')
def index():
    return '''
<!DOCTYPE html>
<html>
<head>
    <title>OpenAI Realtime Test (openai-realtime-py style)</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.0/socket.io.js"></script>
    <style>
        body { font-family: Arial; max-width: 600px; margin: 50px auto; text-align: center; background: #f0f0f0; }
        button { padding: 20px 40px; font-size: 20px; margin: 20px; cursor: pointer; border: none; border-radius: 10px; }
        #status { padding: 20px; font-size: 18px; background: white; border-radius: 10px; margin: 20px 0; }
        .success { color: green; }
        .error { color: red; }
        .info { color: blue; }
        .beep-btn { background: #2196F3; color: white; }
        .mic-btn { background: #4CAF50; color: white; }
        .stop-btn { background: #f44336; color: white; }
        .disabled { opacity: 0.5; cursor: not-allowed; }
    </style>
</head>
<body>
    <h1>🎤 OpenAI Realtime Test</h1>
    <p><em>Using exact flow from openai-realtime-py</em></p>
    <div id="status">Ready to test OpenAI Realtime API</div>
    
    <button onclick="testBeep()" class="beep-btn">
        🔊 TEST BEEP
    </button>
    
    <button onclick="startRecording()" id="recordBtn" class="mic-btn">
        🎤 RECORD & SEND
    </button>
    
    <button onclick="stopRecording()" id="stopBtn" class="stop-btn disabled" disabled>
        ⏹️ STOP
    </button>
    
    <script>
        const socket = io();
        let mediaRecorder;
        let audioChunks = [];
        
        // 🎵 ENHANCED AUDIO STREAMING SYSTEM
        let audioContext = null;
        let audioWorkletNode = null;
        let audioQueue = [];
        let isPlaying = false;
        let currentSource = null;
        let nextPlayTime = 0;
        let isFirstChunk = true;
        let totalChunks = 0;
        let debugAudio = true;
        
        // Audio state management
        const AudioState = {
            IDLE: 'idle',
            STREAMING: 'streaming', 
            PLAYING: 'playing',
            ERROR: 'error'
        };
        let audioState = AudioState.IDLE;
        
        // Initialize comprehensive audio context with user gesture
        async function initializeAudio() {
            if (audioContext && audioContext.state !== 'closed') {
                return; // Already initialized
            }
            
            try {
                // Create new audio context
                audioContext = new (window.AudioContext || window.webkitAudioContext)({
                    sampleRate: 24000,
                    latencyHint: 'interactive'
                });
                
                console.log('🎵 Audio context initialized:', {
                    sampleRate: audioContext.sampleRate,
                    state: audioContext.state,
                    baseLatency: audioContext.baseLatency,
                    outputLatency: audioContext.outputLatency
                });
                
                // Resume if suspended
                if (audioContext.state === 'suspended') {
                    await audioContext.resume();
                    console.log('🎵 Audio context resumed');
                }
                
                // Add event listeners for audio context state changes
                audioContext.addEventListener('statechange', () => {
                    console.log('🎵 Audio context state changed to:', audioContext.state);
                });
                
                audioState = AudioState.IDLE;
                
            } catch (error) {
                console.error('❌ Audio context initialization failed:', error);
                audioState = AudioState.ERROR;
                throw error;
            }
        }
        
        // Enhanced audio chunk processing with Blob URL approach
        socket.on('ai_audio_delta', function(data) {
            console.log('🎵 Streaming audio delta:', data.chunk_bytes, 'bytes');
            processAudioDelta(data.audio_data);
        });
        
        socket.on('ai_audio_complete', function(data) {
            console.log('🏁 Audio stream complete:', data.total_chunks, 'chunks,', data.total_bytes, 'bytes');
            document.getElementById('status').textContent = 
                `✅ AI responded! (${data.total_chunks} chunks, ${data.total_bytes} bytes)`;
            document.getElementById('status').className = 'success';
            
            if (data.text) {
                console.log('📝 Full response text:', data.text);
            }
            
            // Finalize audio streaming
            finalizeAudioStream();
        });
        
        socket.on('ai_audio', function(data) {
            // Legacy handler for beep test
            console.log('🎵 AI Audio (legacy):', data.total_bytes, 'bytes');
            playAudioLegacy(data.audio_data);
        });
        
        socket.on('status', function(data) {
            document.getElementById('status').textContent = data.message;
            document.getElementById('status').className = data.type;
            
            // Reset audio streaming on new requests
            if (data.message.includes('🤖 Response requested')) {
                resetAudioStream();
            }
        });
        
        async function resetAudioStream() {
            console.log('🔄 Resetting audio stream');
            
            try {
                // Stop current playback
                if (currentSource) {
                    try {
                        currentSource.stop();
                        currentSource.disconnect();
                    } catch (e) {
                        console.warn('⚠️ Error stopping audio source:', e);
                    }
                    currentSource = null;
                }
                
                // Clear audio queue
                audioQueue.forEach(item => {
                    if (item.source) {
                        try {
                            item.source.stop();
                            item.source.disconnect();
                        } catch (e) {}
                    }
                    if (item.blobUrl) {
                        URL.revokeObjectURL(item.blobUrl);
                    }
                });
                audioQueue = [];
                
                // Reset state
                isPlaying = false;
                nextPlayTime = 0;
                isFirstChunk = true;
                totalChunks = 0;
                audioState = AudioState.IDLE;
                
                // Ensure audio context is ready
                await initializeAudio();
                
                console.log('✅ Audio stream reset complete');
                
            } catch (error) {
                console.error('❌ Error during audio reset:', error);
                audioState = AudioState.ERROR;
            }
        }
        
        async function processAudioDelta(base64Audio) {
            try {
                // Ensure audio context is ready
                if (!audioContext || audioContext.state === 'closed') {
                    await initializeAudio();
                }
                
                if (audioContext.state === 'suspended') {
                    await audioContext.resume();
                }
                
                // Convert base64 to ArrayBuffer
                const binaryString = atob(base64Audio);
                const audioData = new Uint8Array(binaryString.length);
                for (let i = 0; i < binaryString.length; i++) {
                    audioData[i] = binaryString.charCodeAt(i);
                }
                
                // Skip tiny chunks that might cause issues
                if (audioData.length < 4) {
                    console.log('⚠️ Skipping tiny audio chunk');
                    return;
                }
                
                // Method 1: Enhanced AudioBuffer approach with better error handling
                await playAudioDeltaEnhanced(audioData);
                
            } catch (error) {
                console.error('❌ Error processing audio delta:', error);
                // Try to recover
                if (error.name === 'NotAllowedError') {
                    console.log('🔄 Attempting audio context recovery...');
                    await initializeAudio();
                }
            }
        }
        
        async function playAudioDeltaEnhanced(audioData) {
            try {
                // Create audio buffer from PCM16 data
                const audioBuffer = audioContext.createBuffer(1, audioData.length / 2, 24000);
                const channelData = audioBuffer.getChannelData(0);
                
                // Convert PCM16 to float32 with better error handling
                for (let i = 0; i < channelData.length; i++) {
                    if (i * 2 + 1 < audioData.length) {
                        const sample = (audioData[i * 2] | (audioData[i * 2 + 1] << 8));
                        channelData[i] = sample < 32768 ? sample / 32768 : (sample - 65536) / 32768;
                    }
                }
                
                // Apply gentle fade-in to prevent pops
                const fadeLength = Math.min(64, channelData.length / 20);
                for (let i = 0; i < fadeLength; i++) {
                    const fadeIn = i / fadeLength;
                    channelData[i] *= fadeIn;
                }
                
                // Create and configure audio source
                const source = audioContext.createBufferSource();
                source.buffer = audioBuffer;
                
                // Add gain node for volume control
                const gainNode = audioContext.createGain();
                gainNode.gain.value = 1.0;
                
                source.connect(gainNode);
                gainNode.connect(audioContext.destination);
                
                // Calculate timing for seamless playback
                const currentTime = audioContext.currentTime;
                let startTime;
                
                if (isFirstChunk) {
                    // Start first chunk with minimal delay
                    startTime = currentTime + 0.02;
                    nextPlayTime = startTime;
                    isFirstChunk = false;
                    audioState = AudioState.STREAMING;
                    console.log('🎬 Starting first audio chunk');
                } else {
                    // Schedule subsequent chunks seamlessly
                    if (nextPlayTime < currentTime) {
                        // We're behind, catch up with small buffer
                        startTime = currentTime + 0.01;
                        console.log('⏰ Audio timing catch-up');
                    } else {
                        startTime = nextPlayTime;
                    }
                }
                
                // Start audio playback
                source.start(startTime);
                currentSource = source;
                totalChunks++;
                
                // Enhanced event handlers
                source.onended = () => {
                    if (debugAudio) {
                        console.log(`▶️ Chunk ${totalChunks} ended`);
                    }
                    if (currentSource === source) {
                        currentSource = null;
                    }
                };
                
                source.onerror = (error) => {
                    console.error('❌ Audio source error:', error);
                    audioState = AudioState.ERROR;
                };
                
                // Update next play time with small overlap to prevent gaps
                const overlap = 0.003; // 3ms overlap
                nextPlayTime = startTime + audioBuffer.duration - overlap;
                
                if (debugAudio) {
                    console.log(`▶️ Chunk ${totalChunks}: ${(audioBuffer.duration * 1000).toFixed(1)}ms at ${startTime.toFixed(3)}s`);
                }
                
            } catch (error) {
                console.error('❌ Enhanced audio playback error:', error);
                audioState = AudioState.ERROR;
                
                // Reset timing on error to recover
                isFirstChunk = true;
                nextPlayTime = 0;
                
                throw error;
            }
        }
        
        async function finalizeAudioStream() {
            console.log('🏁 Finalizing audio stream');
            
            // Wait a bit for any remaining audio to complete
            setTimeout(() => {
                console.log('🔄 Audio stream finalization complete');
                audioState = AudioState.IDLE;
                
                // Clean up any remaining resources
                if (currentSource) {
                    currentSource = null;
                }
            }, 1000);
        }
        
        // Legacy audio playback for beep test
        async function playAudioLegacy(base64Audio) {
            try {
                // Ensure audio context
                if (!audioContext || audioContext.state === 'closed') {
                    await initializeAudio();
                }
                
                if (audioContext.state === 'suspended') {
                    await audioContext.resume();
                }
                
                const binaryString = atob(base64Audio);
                const audioData = new Uint8Array(binaryString.length);
                for (let i = 0; i < binaryString.length; i++) {
                    audioData[i] = binaryString.charCodeAt(i);
                }
                
                const audioBuffer = audioContext.createBuffer(1, audioData.length / 2, 24000);
                const channelData = audioBuffer.getChannelData(0);
                
                for (let i = 0; i < channelData.length; i++) {
                    if (i * 2 + 1 < audioData.length) {
                        const sample = (audioData[i * 2] | (audioData[i * 2 + 1] << 8));
                        channelData[i] = sample < 32768 ? sample / 32768 : (sample - 65536) / 32768;
                    }
                }
                
                const source = audioContext.createBufferSource();
                source.buffer = audioBuffer;
                source.connect(audioContext.destination);
                source.start(0);
                
                console.log('✅ Legacy audio played successfully');
                
            } catch (error) {
                console.error('❌ Legacy audio playback error:', error);
            }
        }
        
        async function testBeep() {
            try {
                // Initialize audio with user gesture
                await initializeAudio();
                
                document.getElementById('status').textContent = '🔊 Testing beep...';
                document.getElementById('status').className = 'info';
                
                const response = await fetch('/test_beep', {method: 'POST'});
                const result = await response.json();
                console.log('Beep result:', result);
                
            } catch (error) {
                console.error('❌ Beep test error:', error);
                document.getElementById('status').textContent = 'Beep test error: ' + error.message;
                document.getElementById('status').className = 'error';
            }
        }
        
        async function startRecording() {
            try {
                // Initialize audio context with user gesture
                await initializeAudio();
                
                document.getElementById('status').textContent = '🎤 Getting microphone...';
                document.getElementById('status').className = 'info';
                
                const stream = await navigator.mediaDevices.getUserMedia({ 
                    audio: {
                        sampleRate: 24000,
                        channelCount: 1,
                        echoCancellation: true,
                        noiseSuppression: true,
                        autoGainControl: true
                    } 
                });
                
                const settings = stream.getAudioTracks()[0].getSettings();
                console.log('🎤 Microphone settings:', settings);
                
                mediaRecorder = new MediaRecorder(stream, {
                    mimeType: 'audio/webm;codecs=opus'
                });
                
                audioChunks = [];
                
                mediaRecorder.ondataavailable = event => {
                    if (event.data.size > 0) {
                        audioChunks.push(event.data);
                    }
                };
                
                mediaRecorder.onstop = async () => {
                    const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                    console.log('🎵 Audio blob:', audioBlob.size, 'bytes');
                    await sendToOpenAI(audioBlob);
                    stream.getTracks().forEach(track => track.stop());
                };
                
                mediaRecorder.onerror = (error) => {
                    console.error('❌ MediaRecorder error:', error);
                    document.getElementById('status').textContent = 'Recording error: ' + error.error;
                    document.getElementById('status').className = 'error';
                };
                
                mediaRecorder.start();
                
                document.getElementById('status').textContent = `🎤 RECORDING (${settings.sampleRate}Hz) - Speak now!`;
                document.getElementById('status').className = 'info';
                document.getElementById('recordBtn').disabled = true;
                document.getElementById('recordBtn').classList.add('disabled');
                document.getElementById('stopBtn').disabled = false;
                document.getElementById('stopBtn').classList.remove('disabled');
                
            } catch (error) {
                console.error('❌ Microphone error:', error);
                document.getElementById('status').textContent = 'Microphone error: ' + error.message;
                document.getElementById('status').className = 'error';
            }
        }
        
        function stopRecording() {
            if (mediaRecorder && mediaRecorder.state !== 'inactive') {
                mediaRecorder.stop();
                document.getElementById('status').textContent = '🤖 Processing with OpenAI...';
                document.getElementById('status').className = 'info';
                document.getElementById('recordBtn').disabled = false;
                document.getElementById('recordBtn').classList.remove('disabled');
                document.getElementById('stopBtn').disabled = true;
                document.getElementById('stopBtn').classList.add('disabled');
            }
        }
        
        async function sendToOpenAI(audioBlob) {
            try {
                const formData = new FormData();
                formData.append('audio', audioBlob);
                
                const response = await fetch('/talk_to_ai', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                console.log('OpenAI response:', result);
                
                if (!result.success) {
                    document.getElementById('status').textContent = 'Error: ' + result.error;
                    document.getElementById('status').className = 'error';
                }
                
            } catch (error) {
                console.error('❌ Request error:', error);
                document.getElementById('status').textContent = 'Request error: ' + error.message;
                document.getElementById('status').className = 'error';
            }
        }
        
        // Cleanup on page unload
        window.addEventListener('beforeunload', () => {
            if (audioContext && audioContext.state !== 'closed') {
                audioContext.close();
            }
        });
        
        // Debug function to check audio state
        function checkAudioState() {
            console.log('🔍 Audio State Debug:', {
                audioContext: audioContext ? {
                    state: audioContext.state,
                    sampleRate: audioContext.sampleRate,
                    currentTime: audioContext.currentTime
                } : 'null',
                audioState: audioState,
                isPlaying: isPlaying,
                currentSource: currentSource ? 'active' : 'null',
                totalChunks: totalChunks,
                nextPlayTime: nextPlayTime
            });
        }
        
        // Expose debug function globally
        window.checkAudioState = checkAudioState;
    </script>
</body>
</html>
    '''

@app.route('/test_beep', methods=['POST'])
def test_beep():
    """Generate a simple beep"""
    try:
        # Generate 440Hz beep for 1 second
        sample_rate = TARGET_SR
        duration = 1.0
        frequency = 440
        
        beep_data = bytearray()
        for i in range(int(sample_rate * duration)):
            sample = int(32767 * 0.3 * math.sin(2 * math.pi * frequency * i / sample_rate))
            beep_data.extend(struct.pack('<h', sample))
        
        audio_b64 = base64.b64encode(beep_data).decode('utf-8')
        socketio.emit('ai_audio', {
            'audio_data': audio_b64,
            'total_bytes': len(beep_data)
        })
        
        socketio.emit('status', {
            'type': 'success', 
            'message': f'🔊 Beep played! ({len(beep_data)} bytes at {sample_rate}Hz)'
        })
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/talk_to_ai', methods=['POST'])
def talk_to_ai():
    """Voice conversation with OpenAI using exact openai-realtime-py flow"""
    try:
        if 'audio' not in request.files:
            return jsonify({'error': 'No audio file'}), 400
        
        audio_file = request.files['audio']
        webm_data = audio_file.read()
        
        log(f"🎤 Received audio: {len(webm_data)} bytes")
        
        def process_audio():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                # Convert WebM to PCM16
                pcm_audio = convert_webm_to_pcm16(webm_data)
                
                # Call OpenAI Realtime API
                audio_response, text_response = loop.run_until_complete(call_openai_realtime(pcm_audio))
                
                # Response is now streamed in real-time via ai_audio_delta events
                # No need to send final audio since it's already been streamed
                log(f"✅ Streaming complete: {len(audio_response) if audio_response else 0} bytes total")
                
            except Exception as e:
                log(f"❌ Processing error: {e}")
                socketio.emit('status', {
                    'type': 'error',
                    'message': f'Processing error: {e}'
                })
            finally:
                loop.close()
        
        # Run in background thread
        threading.Thread(target=process_audio, daemon=True).start()
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    if not API_KEY:
        print("❌ OPENAI_API_KEY not set!")
        print("💡 Set it: export OPENAI_API_KEY='your-key'")
        exit(1)
    
    print("🚀 OpenAI Realtime Test (openai-realtime-py style)")
    print("📱 Open: http://localhost:3001")
    print("🎯 Click 'RECORD & SEND' to test voice interaction")
    
    socketio.run(app, debug=True, host='0.0.0.0', port=3001)

