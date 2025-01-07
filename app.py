import os
import logging
from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
from pedalboard import Pedalboard, Reverb, Gain
from pedalboard.io import AudioFile
import tempfile
from werkzeug.utils import secure_filename
import traceback
from pydub import AudioSegment

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Use temporary directory instead of fixed paths
try:
    # Try to use a custom temp directory in a local path
    TEMP_DIR = os.path.join(os.path.expanduser('~'), 'AppData', 'Local', 'SLRVB', 'temp')
    if not os.path.exists(TEMP_DIR):
        os.makedirs(TEMP_DIR)
    logger.info(f"Created custom temp directory: {TEMP_DIR}")
except Exception as e:
    # Fall back to system temp directory if custom directory fails
    logger.warning(f"Failed to create custom temp directory, using system temp: {str(e)}")
    TEMP_DIR = tempfile.gettempdir()

logger.info(f"Using temporary directory: {TEMP_DIR}")

# Configuration
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max file size
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

# Speed and reverb presets
SPEED_AMOUNTS = [38000, 39000, 40000, 41000, 42000, 43000, 44000, 45000, 46000, 47000]
REVERB_AMOUNTS = [0.0, 0.10, 0.25, 0.5]

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'wav', 'mp3'}

def convert_to_wav(input_path, output_path):
    """Convert MP3 to WAV format"""
    try:
        logger.info(f"Converting {input_path} to WAV format")
        audio = AudioSegment.from_mp3(input_path)
        audio.export(output_path, format='wav')
        logger.info("Conversion successful")
    except Exception as e:
        logger.error(f"Error converting MP3 to WAV: {str(e)}")
        raise RuntimeError(f"Error converting audio file: {str(e)}")

def process_audio(input_path, output_path, room_size=0.25, sample_rate=40000):
    try:
        # Convert to absolute paths
        input_path = os.path.abspath(input_path)
        output_path = os.path.abspath(output_path)
        
        logger.info(f"Starting audio processing: input={input_path}, output={output_path}")
        logger.info(f"Parameters: room_size={room_size}, sample_rate={sample_rate}")

        # Verify input file exists and is readable
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Input file not found: {input_path}")
        
        # Verify output directory exists and is writable
        output_dir = os.path.dirname(output_path)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        
        # Test if we can write to output directory
        test_file = os.path.join(output_dir, 'test_write.tmp')
        try:
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            logger.info(f"Successfully verified write access to {output_dir}")
        except Exception as e:
            raise PermissionError(f"Cannot write to output directory {output_dir}: {str(e)}")

        logger.info("Opening input file for reading...")
        with AudioFile(input_path, 'r') as f:
            duration = f.frames / f.samplerate
            logger.info(f"Audio duration: {duration} seconds")
            
            if duration > 720:  # 12 minutes max
                raise ValueError("Audio file too long. Maximum duration is 12 minutes.")
            
            audio = f.read(f.frames)
            original_sample_rate = f.samplerate
            logger.info(f"Original sample rate: {original_sample_rate}")

        try:
            logger.info("Applying dreamy reverb effect...")
            board = Pedalboard([
                Reverb(
                    room_size=0.35,      # Larger room for dreaminess
                    damping=0.5,         # Smooth high frequencies
                    wet_level=0.45,      # Good amount of reverb
                    dry_level=0.6,       # Keep original sound clear
                    width=1.0            # Full stereo width
                ),
                Gain(                    # Add volume boost
                    gain_db=4.0
                )
            ])
            effected = board(audio, original_sample_rate)
            
            logger.info(f"Writing processed audio to {output_path}...")
            logger.info(f"Audio shape: {effected.shape}, Sample rate: {sample_rate}")
            
            # Ensure the output directory exists right before writing
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            with AudioFile(output_path, 'w', sample_rate, effected.shape[0]) as out:
                out.write(effected)
            
            # Verify the output file was created successfully
            if not os.path.exists(output_path):
                raise RuntimeError(f"Output file was not created: {output_path}")
            else:
                logger.info(f"Successfully created output file: {output_path}")
            
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
        logger.info(f"Received file: {file.filename}")
        
        if file.filename == '':
            logger.warning("No file selected")
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            logger.warning(f"Invalid file type: {file.filename}")
            return jsonify({'error': 'Only WAV and MP3 files are supported'}), 400
        
        # Get parameters first to validate them
        try:
            speed_index = int(request.form.get('speed', 2))
            reverb_index = int(request.form.get('reverb', 2))
            logger.info(f"Processing parameters: speed_index={speed_index}, reverb_index={reverb_index}")
        except ValueError as ve:
            logger.error(f"Invalid parameter values: {str(ve)}")
            return jsonify({'error': 'Invalid speed or reverb values'}), 400
        
        if speed_index < 0 or speed_index >= len(SPEED_AMOUNTS):
            logger.warning(f"Invalid speed value: {speed_index}")
            return jsonify({'error': 'Invalid speed value'}), 400
        
        if reverb_index < 0 or reverb_index >= len(REVERB_AMOUNTS):
            logger.warning(f"Invalid reverb value: {reverb_index}")
            return jsonify({'error': 'Invalid reverb value'}), 400
        
        speed = SPEED_AMOUNTS[speed_index]
        room_size = REVERB_AMOUNTS[reverb_index]
        
        # Check file size
        try:
            file.seek(0, os.SEEK_END)
            size = file.tell()
            file.seek(0)
            logger.info(f"File size: {size} bytes")
            
            if size > app.config['MAX_CONTENT_LENGTH']:
                logger.warning(f"File too large: {size} bytes")
                return jsonify({'error': 'File too large. Maximum size is 100MB'}), 413
        except Exception as e:
            logger.error(f"Error checking file size: {str(e)}")
            return jsonify({'error': 'Error checking file size'}), 500

        # Create temporary files with explicit close and error handling
        try:
            # Ensure temp directory exists
            os.makedirs(TEMP_DIR, exist_ok=True)
            
            # Create input file
            input_file = tempfile.NamedTemporaryFile(mode='w+b', delete=False, suffix='.wav', dir=TEMP_DIR)
            input_file.close()  # Close immediately to avoid file handle issues
            input_path = os.path.abspath(input_file.name)
            
            # Create output file
            output_file = tempfile.NamedTemporaryFile(mode='w+b', delete=False, suffix='.wav', dir=TEMP_DIR)
            output_file.close()  # Close immediately to avoid file handle issues
            output_path = os.path.abspath(output_file.name)
            
            logger.info(f"Created temporary files: input={input_path}, output={output_path}")
            logger.info(f"Temp directory contents: {os.listdir(TEMP_DIR)}")
        except Exception as e:
            logger.error(f"Error creating temporary files: {str(e)}")
            return jsonify({'error': f'Error creating temporary files: {str(e)}'}), 500

        try:
            logger.info("Saving uploaded file...")
            if file.filename.lower().endswith('.mp3'):
                # For MP3 files, save to temp file and convert to WAV
                temp_mp3 = tempfile.NamedTemporaryFile(mode='w+b', delete=False, suffix='.mp3', dir=TEMP_DIR)
                temp_mp3.close()  # Close immediately to avoid file handle issues
                file.save(temp_mp3.name)
                convert_to_wav(temp_mp3.name, input_path)
                try:
                    os.unlink(temp_mp3.name)
                except Exception as e:
                    logger.warning(f"Failed to delete temp MP3 file: {str(e)}")
            else:
                # For WAV files, save directly
                file.save(input_path)
            
            logger.info("Processing audio...")
            process_audio(input_path, output_path, room_size, speed)
            
            logger.info("Sending processed file...")
            return send_file(
                output_path,
                mimetype='audio/wav',
                as_attachment=True,
                download_name=f"slowreverb_{os.path.splitext(file.filename)[0]}.wav",
                max_age=0
            )
            
        except ValueError as ve:
            logger.error(f"Validation error: {str(ve)}")
            return jsonify({'error': str(ve)}), 400
        except Exception as e:
            logger.error(f"Error processing audio: {str(e)}")
            logger.error(traceback.format_exc())
            return jsonify({'error': f"Error processing audio: {str(e)}"}), 500
        finally:
            # Clean up temporary files
            try:
                logger.info("Cleaning up temporary files...")
                if os.path.exists(input_path):
                    os.unlink(input_path)
                if os.path.exists(output_path):
                    os.unlink(output_path)
            except Exception as e:
                logger.error(f"Error cleaning up files: {str(e)}")
                
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': f"Server error: {str(e)}"}), 500

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
            <input type="file" id="audioFile" accept=".wav, .mp3">
            <div class="info">Maximum file size: 100MB, Maximum duration: 12 minutes</div>
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

            async function processAudio() {
                const fileInput = document.getElementById('audioFile');
                const speedInput = document.getElementById('speed');
                const reverbInput = document.getElementById('reverb');
                
                hideError();
                
                if (!fileInput.files.length) {
                    showError('Please select a file');
                    return;
                }

                const file = fileInput.files[0];
                if (file.size > 100 * 1024 * 1024) {
                    showError('File too large. Maximum size is 100MB');
                    return;
                }
                
                const formData = new FormData();
                formData.append('file', file);
                formData.append('speed', speedInput.value);
                formData.append('reverb', reverbInput.value);
                
                setLoading(true);
                
                try {
                    const response = await fetch('/process', {
                        method: 'POST',
                        body: formData
                    });

                    if (!response.ok) {
                        const contentType = response.headers.get('content-type');
                        if (contentType && contentType.includes('application/json')) {
                            const errorData = await response.json();
                            throw new Error(errorData.error || 'Server error occurred');
                        } else {
                            throw new Error('Server error occurred. Please try again.');
                        }
                    }

                    const blob = await response.blob();
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = 'processed_audio.wav';
                    document.body.appendChild(a);
                    a.click();
                    window.URL.revokeObjectURL(url);
                    a.remove();
                } catch (error) {
                    showError(error.message);
                } finally {
                    setLoading(false);
                }
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
    # Configure app for production
    app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max file size
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
    
    # Run the app
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, threaded=True)