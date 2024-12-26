import os
from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
from pedalboard import Pedalboard, Reverb
from pedalboard.io import AudioFile
import tempfile
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'wav'}

# Create necessary folders
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Speed and reverb presets from the original implementation
SPEED_AMOUNTS = [38000, 39000, 40000, 41000, 42000, 43000, 44000, 45000, 46000, 47000]
REVERB_AMOUNTS = [0.0, 0.10, 0.25, 0.5]

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def process_audio(input_path, output_path, room_size=0.25, sample_rate=40000):
    try:
        # Ensure output directory exists
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            
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
        
        # Create temporary directory if it doesn't exist
        temp_dir = os.path.join(os.getcwd(), 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        
        # Use absolute paths for temporary files
        input_path = os.path.join(temp_dir, f'input_{secure_filename(file.filename)}')
        output_path = os.path.join(temp_dir, f'output_{secure_filename(file.filename)}')
        
        # Save uploaded file
        file.save(input_path)
        
        # Process the audio
        process_audio(input_path, output_path, room_size, speed)
        
        # Send the processed file
        response = send_file(
            output_path,
            as_attachment=True,
            download_name=f"slowreverb_{os.path.splitext(file.filename)[0]}.wav"
        )
        
        # Clean up temporary files after sending
        @response.call_on_close
        def cleanup():
            try:
                if os.path.exists(input_path):
                    os.remove(input_path)
                if os.path.exists(output_path):
                    os.remove(output_path)
            except Exception as e:
                print(f"Error during cleanup: {str(e)}")
        
        return response
    
    except Exception as e:
        # Cleanup in case of error
        try:
            if os.path.exists(input_path):
                os.remove(input_path)
            if os.path.exists(output_path):
                os.remove(output_path)
        except:
            pass
        return jsonify({'error': str(e)}), 500

@app.route('/')
def index():
    return '''
    <html>
        <head>
            <title>Slow and Reverbifier</title>
            <style>
                body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
                .container { text-align: center; }
                .upload-form { margin: 20px 0; padding: 20px; border: 2px dashed #ccc; border-radius: 10px; }
                .button { background: #4CAF50; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; }
                .button:hover { background: #45a049; }
                select, input[type="range"] { padding: 10px; margin: 10px; width: 200px; }
                .slider-container { margin: 20px 0; }
                label { display: inline-block; width: 120px; text-align: right; margin-right: 10px; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Slow and Reverbifier</h1>
                <div class="upload-form">
                    <form action="/process" method="post" enctype="multipart/form-data">
                        <div>
                            <input type="file" name="file" accept=".wav" required><br><br>
                        </div>
                        <div class="slider-container">
                            <label>Speed:</label>
                            <input type="range" name="speed" min="0" max="9" value="2" step="1"><br>
                            <small>38000Hz - 47000Hz</small>
                        </div>
                        <div class="slider-container">
                            <label>Reverb:</label>
                            <input type="range" name="reverb" min="0" max="3" value="2" step="1"><br>
                            <small>0.0 - 0.5</small>
                        </div>
                        <input type="submit" value="Process Audio" class="button">
                    </form>
                </div>
            </div>
        </body>
    </html>
    '''

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)