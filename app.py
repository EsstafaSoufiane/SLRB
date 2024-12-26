import os
import logging
from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
from pedalboard import Pedalboard, Reverb
from pedalboard.io import AudioFile
import tempfile
from werkzeug.utils import secure_filename
import traceback

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Use temporary directory instead of fixed paths
TEMP_DIR = tempfile.gettempdir()

# Configuration
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
CHUNK_SIZE = 1024 * 1024  # 1MB chunks for processing

# Speed and reverb presets from the original implementation
SPEED_AMOUNTS = [38000, 39000, 40000, 41000, 42000, 43000, 44000, 45000, 46000, 47000]
REVERB_AMOUNTS = [0.0, 0.10, 0.25, 0.5]

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'wav'}

def process_audio(input_path, output_path, room_size=0.25, sample_rate=40000):
    try:
        logger.info(f"Starting audio processing: input={input_path}, output={output_path}")
        logger.info(f"Parameters: room_size={room_size}, sample_rate={sample_rate}")

        # Process audio in chunks to reduce memory usage
        with AudioFile(input_path, 'r') as f:
            duration = f.frames / f.samplerate
            logger.info(f"Audio duration: {duration} seconds")
            
            if duration > 600:  # 10 minutes max
                raise ValueError("Audio file too long. Maximum duration is 10 minutes.")
            
            # Read the audio in chunks
            audio = f.read(f.frames)
            original_sample_rate = f.samplerate
            logger.info(f"Original sample rate: {original_sample_rate}")

        # Create and apply effects
        try:
            logger.info("Applying audio effects...")
            board = Pedalboard([Reverb(room_size=room_size)])
            effected = board(audio, original_sample_rate)
            
            # Write the processed audio
            logger.info("Writing processed audio...")
            with AudioFile(output_path, 'w', sample_rate, effected.shape[0]) as out:
                out.write(effected)
            
            logger.info("Audio processing completed successfully")
            
        except Exception as e:
            logger.error(f"Error during audio processing: {str(e)}")
            logger.error(traceback.format_exc())
            raise RuntimeError(f"Error processing audio: {str(e)}")
            
    except Exception as e:
        logger.error(f"Error in process_audio: {str(e)}")
        logger.error(traceback.format_exc())
        raise

@app.route('/process', methods=['POST'])
def process_song():
    try:
        logger.info("Received process request")
        
        if 'file' not in request.files:
            logger.warning("No file provided in request")
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            logger.warning("No file selected")
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            logger.warning(f"Invalid file type: {file.filename}")
            return jsonify({'error': 'Only WAV files are supported'}), 400
        
        # Check file size before processing
        file.seek(0, os.SEEK_END)
        size = file.tell()
        file.seek(0)
        
        logger.info(f"File size: {size} bytes")
        
        if size > app.config['MAX_CONTENT_LENGTH']:
            logger.warning(f"File too large: {size} bytes")
            return jsonify({'error': 'File too large. Maximum size is 50MB'}), 413
        
        # Get parameters
        speed_index = int(request.form.get('speed', 2))  # Default to 40000
        reverb_index = int(request.form.get('reverb', 2))  # Default to 0.25
        
        logger.info(f"Processing parameters: speed_index={speed_index}, reverb_index={reverb_index}")
        
        if speed_index < 0 or speed_index >= len(SPEED_AMOUNTS):
            logger.warning(f"Invalid speed value: {speed_index}")
            return jsonify({'error': 'Invalid speed value'}), 400
        
        if reverb_index < 0 or reverb_index >= len(REVERB_AMOUNTS):
            logger.warning(f"Invalid reverb value: {reverb_index}")
            return jsonify({'error': 'Invalid reverb value'}), 400
        
        speed = SPEED_AMOUNTS[speed_index]
        room_size = REVERB_AMOUNTS[reverb_index]
        
        # Create temporary files with unique names
        input_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav', dir=TEMP_DIR)
        output_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav', dir=TEMP_DIR)
        
        try:
            logger.info("Saving uploaded file...")
            # Save uploaded file
            file.save(input_file.name)
            
            logger.info("Processing audio...")
            # Process the audio
            process_audio(input_file.name, output_file.name, room_size, speed)
            
            logger.info("Sending processed file...")
            # Send the processed file
            return send_file(
                output_file.name,
                as_attachment=True,
                download_name=f"slowreverb_{os.path.splitext(file.filename)[0]}.wav",
                max_age=0
            )
            
        except ValueError as ve:
            logger.error(f"Validation error: {str(ve)}")
            return jsonify({'error': str(ve)}), 400
        except RuntimeError as re:
            logger.error(f"Runtime error: {str(re)}")
            return jsonify({'error': str(re)}), 500
        finally:
            # Clean up temporary files
            try:
                logger.info("Cleaning up temporary files...")
                os.unlink(input_file.name)
                os.unlink(output_file.name)
            except Exception as e:
                logger.error(f"Error cleaning up files: {str(e)}")
                
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': f"Unexpected error: {str(e)}"}), 500

@app.route('/')
def index():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Slow and Reverbifier</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
                text-align: center;
            }
            .container {
                border: 2px dashed #ccc;
                padding: 20px;
                margin: 20px 0;
            }
            .slider {
                width: 80%;
                margin: 10px 0;
            }
            button {
                background-color: #4CAF50;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
            }
            button:hover {
                background-color: #45a049;
            }
            button:disabled {
                background-color: #cccccc;
                cursor: not-allowed;
            }
            .error {
                color: #ff0000;
                margin: 10px 0;
                display: none;
            }
            .loading {
                display: none;
                margin: 10px 0;
            }
            .info {
                color: #666;
                font-size: 0.9em;
                margin: 10px 0;
            }
        </style>
    </head>
    <body>
        <h1>Slow and Reverbifier</h1>
        <div class="container">
            <input type="file" id="audioFile" accept=".wav">
            <div class="info">Maximum file size: 50MB, Maximum duration: 10 minutes</div>
            <br><br>
            <label for="speed">Speed:</label><br>
            <input type="range" id="speed" class="slider" min="0" max="9" value="2">
            <div id="speedValue">38000Hz - 47000Hz</div>
            <br>
            <label for="reverb">Reverb:</label><br>
            <input type="range" id="reverb" class="slider" min="0" max="3" value="2">
            <div id="reverbValue">0.0 - 0.5</div>
            <br>
            <button id="processButton" onclick="processAudio()">Process Audio</button>
            <div id="loading" class="loading">Processing... Please wait...</div>
            <div id="error" class="error"></div>
        </div>
        <script>
            const SPEED_AMOUNTS = [38000, 39000, 40000, 41000, 42000, 43000, 44000, 45000, 46000, 47000];
            const REVERB_AMOUNTS = [0.0, 0.10, 0.25, 0.5];

            function showError(message) {
                const errorDiv = document.getElementById('error');
                errorDiv.textContent = message;
                errorDiv.style.display = 'block';
            }

            function hideError() {
                document.getElementById('error').style.display = 'none';
            }

            function setLoading(isLoading) {
                const button = document.getElementById('processButton');
                const loading = document.getElementById('loading');
                button.disabled = isLoading;
                loading.style.display = isLoading ? 'block' : 'none';
            }

            function processAudio() {
                const fileInput = document.getElementById('audioFile');
                const speedInput = document.getElementById('speed');
                const reverbInput = document.getElementById('reverb');
                
                hideError();
                
                if (!fileInput.files.length) {
                    showError('Please select a file');
                    return;
                }

                const file = fileInput.files[0];
                if (file.size > 50 * 1024 * 1024) {
                    showError('File too large. Maximum size is 50MB');
                    return;
                }
                
                const formData = new FormData();
                formData.append('file', file);
                formData.append('speed', speedInput.value);
                formData.append('reverb', reverbInput.value);
                
                setLoading(true);
                
                fetch('/process', {
                    method: 'POST',
                    body: formData
                })
                .then(response => {
                    if (!response.ok) {
                        return response.json().then(err => { throw new Error(err.error) });
                    }
                    return response.blob();
                })
                .then(blob => {
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = 'processed_audio.wav';
                    document.body.appendChild(a);
                    a.click();
                    window.URL.revokeObjectURL(url);
                    a.remove();
                })
                .catch(error => {
                    showError('Error: ' + error.message);
                })
                .finally(() => {
                    setLoading(false);
                });
            }

            // Update speed and reverb values display
            document.getElementById('speed').addEventListener('input', function(e) {
                const speed = SPEED_AMOUNTS[e.target.value];
                document.getElementById('speedValue').textContent = speed + 'Hz';
            });

            document.getElementById('reverb').addEventListener('input', function(e) {
                const reverb = REVERB_AMOUNTS[e.target.value];
                document.getElementById('reverbValue').textContent = reverb.toFixed(2);
            });
        </script>
    </body>
    </html>
    ''', 200, {'Content-Type': 'text/html'}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))