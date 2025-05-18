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
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch
# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Initialize the memory client
client = MemoryClient(api_key="m0-PxCfRoQH5BAgWj2UONAiq9d3rh1P5sVrVqz9VXKO")

# URL for the inference API
INFERENCE_API_URL = "http://localhost:5500/generate"

# Global variables to store the model and tokenizer
global_model = None
global_tokenizer = None
adapter_name = "ExampleLora"

# Model configuration
model_weight_ids = {
    "DeepSeek-R1-Distill-Llama-70B": "uds-quilled-branch-catboat-250513",
    "DeepSeek-R1-Distill-Llama-8B": "uds-unruly-jungle-offer-250513",
    "DeepSeek-R1-Distill-Qwen-1.5B": "uds-plural-branch-bag-250513",
    "DeepSeek-R1-Distill-Qwen-14B": "uds-brazen-meowing-munchkin-250513",
    "DeepSeek-R1-Distill-Qwen-32B": "uds-golden-unequaled-prepared-250513",
    "DeepSeek-R1-Distill-Qwen-7B": "uds-leaf-various-bosworth-250513",
}

# CONFIG - Set your model and checkpoint path here
MODEL_NAME = "DeepSeek-R1-Distill-Llama-8B"  # Change to your model
CHECKPOINT_PATH = "/shared/artifacts/exp-sponge-busy-pearl-250517/checkpoints/AtomicDirectory_checkpoint_99"  # Change to your checkpoint path


def load_model():
    """Load the model and tokenizer once at server startup"""
    global global_model, global_tokenizer
    
    try:
        logger.info(f"Loading model: {MODEL_NAME}")
        mounted_dataset_path = f"/data/{model_weight_ids[MODEL_NAME]}"
        
        # Load tokenizer
        global_tokenizer = AutoTokenizer.from_pretrained(mounted_dataset_path)
        
        # Load model
        model = AutoModelForCausalLM.from_pretrained(
            mounted_dataset_path, 
            use_cache=False, 
            torch_dtype=torch.bfloat16
        )
        
        # Store the model globally for reuse
        global_model = model
        
        logger.info("Model and checkpoint loaded successfully")
        return True
    except Exception as e:
        logger.error(f"Error loading model: {e}")
        return False

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
    
    # Step 3: Collate results using DeepSeek model
    if response_data['memory'] or response_data['inference']:
        try:
            # URL for the DeepSeek model API
            DEEPSEEK_API_URL = "http://localhost:5600/generate"
            
            # Prepare the context and prompt
            memory_text = response_data['memory'] if response_data['memory'] else "No memory found."
            inference_text = response_data['inference'] if response_data['inference'] else "No inference generated."
            
            collation_prompt = f"""
You are an AI assistant tasked with providing the best possible response by combining information from memory and reasoning.

MEMORY CONTEXT:
{memory_text}

REASONING OUTPUT:
{inference_text}

INSTRUCTIONS:
1. Review both the memory context and reasoning output.
2. Create a coherent, unified response that gives higher priority to the reasoning output.
3. Use memory information only when it adds relevant context or details.
4. Ensure the final answer is accurate, concise, and helpful.
5. If there are contradictions, trust the reasoning output more than memory.

COMBINED RESPONSE:
"""
            
            # Call the DeepSeek model API
            logger.info("Calling DeepSeek model to collate responses")
            # collation_response = requests.post(
            #     DEEPSEEK_API_URL,
            #     json={
            #         'query': collation_prompt,
            #         'max_new_tokens': 1024,
            #         'temperature': 0.7,
            #         'template_type': 'simple'  # Use simple template to avoid extra formatting
            #     },
            #     timeout=60
            # )
            # Tokenize the input
            encoding = global_tokenizer(collation_prompt, return_tensors="pt")
            input_ids = encoding['input_ids'].to("cuda")
            attention_mask = encoding['attention_mask'].to("cuda")
            
            # Generate response
            with torch.no_grad():
                generate_ids = global_model.generate(
                    input_ids, 
                    attention_mask=attention_mask, 
                    pad_token_id=global_tokenizer.eos_token_id, 
                    max_new_tokens=500, 
                    do_sample=True, 
                    temperature=0.8
                )
                
            # Decode the response
            answer = global_tokenizer.batch_decode(
                generate_ids, 
                skip_special_tokens=True, 
                clean_up_tokenization_spaces=False
            )
            combined_text = answer[0]
 
            # Extract just the part after "COMBINED RESPONSE:"
            if "COMBINED RESPONSE:" in combined_text:
                combined_text = combined_text.split("COMBINED RESPONSE:")[1].strip()
            
            response_data['inference'] = combined_text
            logger.info("Successfully collated memory and inference responses")
            
            # Use the collated response for TTS instead of just inference
            if combined_text:
                output_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "response.mp3")
                text_to_speech_google(combined_text, output_file)
                logger.info(f"Generated audio from collated response: {output_file}")
                response_data['audio_file'] = output_file
                
        except requests.RequestException as e:
            logger.error(f"Error connecting to DeepSeek API: {e}")
            response_data['collation_error'] = f"Connection error: {str(e)}"
        except Exception as e:
            logger.error(f"Error during collation: {e}")
            response_data['collation_error'] = str(e)
    
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
    is_model_loaded = load_model()
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"Starting memory API on port {port}")
    logger.info(f"Using inference API at {INFERENCE_API_URL}")
    
    # Run the app, listening on all interfaces (0.0.0.0)
    app.run(host='0.0.0.0', port=port, debug=True) 