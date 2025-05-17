import sys
import os
# Add the project root directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from flask import Flask, request, jsonify
from flask_cors import CORS
from mem0 import MemoryClient
import requests
import logging
from speech_processing.tts import text_to_speech_google

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Initialize the memory client
client = MemoryClient(api_key="m0-PxCfRoQH5BAgWj2UONAiq9d3rh1P5sVrVqz9VXKO")

# URL for the inference API
INFERENCE_API_URL = "http://localhost:5500/generate"

@app.route('/query', methods=['POST'])
def query_memory():
    """
    Endpoint to query the memory system and the inference API
    Expects JSON with 'query' field
    Returns both memory and inference responses
    """
    if not request.json or 'query' not in request.json:
        return jsonify({'error': 'No query provided'}), 400
    
    query = request.json['query']
    logger.info(f"Received query: {query}")
    
    response_data = {
        'success': True,
        'memory': None,
        'inference': None
    }
    
    # Step 1: Query memory system
    try:
        mem0_response = client.search(query, user_id="elara")
        logger.info("Memory query successful")
        
        if mem0_response and len(mem0_response) > 0:
            memory = mem0_response[0]['memory']
            response_data['memory'] = memory
            logger.info(f"Found memory: {memory[:100]}...")
        else:
            logger.info("No memory found")
    except Exception as e:
        logger.error(f"Error querying memory: {e}")
        response_data['memory_error'] = str(e)
    
    # Step 2: Query inference API
    try:
        logger.info(f"Calling inference API with query: {query}")
        inference_response = requests.post(
            INFERENCE_API_URL, 
            json={'query': query},
            timeout=60  # Increased timeout for LLM generation
        )
        
        if inference_response.status_code == 200:
            inference_data = inference_response.json()
            if inference_data.get('success'):
                response_data['inference'] = inference_data.get('response')
                logger.info(f"Got inference response with {inference_data.get('iterations')} iterations")
            else:
                response_data['inference_error'] = inference_data.get('error')
                logger.error(f"Inference API error: {inference_data.get('error')}")
        else:
            response_data['inference_error'] = f"HTTP error: {inference_response.status_code}"
            logger.error(f"Inference API HTTP error: {inference_response.status_code}")
    except requests.RequestException as e:
        logger.error(f"Error connecting to inference API: {e}")
        response_data['inference_error'] = f"Connection error: {str(e)}"
    
    # Generate speech from the inference response if available
    if response_data['inference']:
        try:
            logger.info(f"Generating audio response for: {response_data['inference']}")
            # Save the audio file in the same directory as the API
            output_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "response.mp3")
            # text_to_speech_google(response_data['inference'], output_file)
            text_to_speech_google(response_data['memory'], output_file)
            
            logger.info(f"Generated audio response at: {output_file}")
            response_data['audio_file'] = output_file
        except Exception as e:
            logger.error(f"Error generating speech: {e}")
            response_data['audio_error'] = str(e)
    
    # Return both responses, even if one failed
    return jsonify(response_data)

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    inference_api_status = "unknown"
    
    try:
        inference_response = requests.get("http://localhost:5500/health", timeout=5)
        if inference_response.status_code == 200:
            inference_api_status = "healthy"
        else:
            inference_api_status = f"unhealthy ({inference_response.status_code})"
    except requests.RequestException:
        inference_api_status = "unavailable"
    
    return jsonify({
        "memory_api": "healthy",
        "inference_api": inference_api_status
    })

if __name__ == '__main__':
    # Get port from environment or default to 5000
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"Starting memory API on port {port}")
    logger.info(f"Using inference API at {INFERENCE_API_URL}")
    
    # Run the app, listening on all interfaces (0.0.0.0)
    app.run(host='0.0.0.0', port=port, debug=True) 