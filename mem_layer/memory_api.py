from flask import Flask, request, jsonify
from flask_cors import CORS
from mem0 import MemoryClient
import os

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Initialize the memory client
client = MemoryClient(api_key="m0-PxCfRoQH5BAgWj2UONAiq9d3rh1P5sVrVqz9VXKO")

@app.route('/query', methods=['POST'])
def query_memory():
    """
    Endpoint to query the memory system
    Expects JSON with 'query' field
    Returns the memory response
    """
    if not request.json or 'query' not in request.json:
        return jsonify({'error': 'No query provided'}), 400
    
    query = request.json['query']
    try:
        # Get response from memory system
        response = client.search(query, user_id="elara")
        print(response)
        if response and len(response) > 0:
            memory = response[0]['memory']
            return jsonify({
                'success': True,
                'memory': memory
            })
        else:
            return jsonify({
                'success': False,
                'error': 'No memory found'
            }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    # Get port from environment or default to 5000
    port = int(os.environ.get('PORT', 5000))
    # Run the app, listening on all interfaces (0.0.0.0)
    app.run(host='0.0.0.0', port=port, debug=True) 