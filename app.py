import os
from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
from pedalboard import Pedalboard, Reverb
from pedalboard.io import AudioFile
import tempfile
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)

# Use temporary directory instead of fixed paths
TEMP_DIR = tempfile.gettempdir()

# Speed and reverb presets from the original implementation
SPEED_AMOUNTS = [38000, 39000, 40000, 41000, 42000, 43000, 44000, 45000, 46000, 47000]
REVERB_AMOUNTS = [0.0, 0.10, 0.25, 0.5]

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'wav'}

def process_audio(input_path, output_path, room_size=0.25, sample_rate=40000):
    try:
        # Read the audio file
        with AudioFile(input_path, 'r') as f:
            audio = f.read(f.frames)
            original_sample_rate = f.samplerate
        
        # Create and apply effects
        board = Pedalboard([Reverb(room_size=room_size)])
        effected = board(audio, original_sample_rate)
        
        # Write the processed audio
        with AudioFile(output_path, 'w', sample_rate, effected.shape[0]) as out:
            out.write(effected)
    except Exception as e:
        print(f"Error processing audio: {str(e)}")
        raise

@app.route('/process', methods=['POST'])
def process_song():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'Only WAV files are supported'}), 400
    
    try:
        # Get parameters
        speed_index = int(request.form.get('speed', 2))  # Default to 40000
        reverb_index = int(request.form.get('reverb', 2))  # Default to 0.25
        
        speed = SPEED_AMOUNTS[speed_index]
        room_size = REVERB_AMOUNTS[reverb_index]
        
        # Create temporary files with unique names
        input_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav', dir=TEMP_DIR)
        output_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav', dir=TEMP_DIR)
        
        try:
            # Save uploaded file
            file.save(input_file.name)
            
            # Process the audio
            process_audio(input_file.name, output_file.name, room_size, speed)
            
            # Send the processed file
            return send_file(
                output_file.name,
                as_attachment=True,
                download_name=f"slowreverb_{os.path.splitext(file.filename)[0]}.wav"
            )
        finally:
            # Clean up temporary files
            try:
                os.unlink(input_file.name)
                os.unlink(output_file.name)
            except:
                pass
                
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
        </style>
    </head>
    <body>
        <h1>Slow and Reverbifier</h1>
        <div class="container">
            <input type="file" id="audioFile" accept=".wav">
            <br><br>
            <label for="speed">Speed:</label><br>
            <input type="range" id="speed" class="slider" min="0" max="9" value="2">
            <div id="speedValue">38000Hz - 47000Hz</div>
            <br>
            <label for="reverb">Reverb:</label><br>
            <input type="range" id="reverb" class="slider" min="0" max="3" value="2">
            <div id="reverbValue">0.0 - 0.5</div>
            <br>
            <button onclick="processAudio()">Process Audio</button>
        </div>
        <script>
            function processAudio() {
                const fileInput = document.getElementById('audioFile');
                const speedInput = document.getElementById('speed');
                const reverbInput = document.getElementById('reverb');
                
                if (!fileInput.files.length) {
                    alert('Please select a file');
                    return;
                }
                
                const formData = new FormData();
                formData.append('file', fileInput.files[0]);
                formData.append('speed', speedInput.value);
                formData.append('reverb', reverbInput.value);
                
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
                    alert('Error: ' + error.message);
                });
            }
        </script>
    </body>
    </html>
    '''

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))