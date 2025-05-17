import torch
import torch.distributed.checkpoint as dcp
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import LoraModel, LoraConfig
from fsdp_utils import AppState
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS
import os

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

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
        
        # Apply LoRA configuration
        lora_config = LoraConfig(
            r=16,
            lora_alpha=32,
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
            lora_dropout=0,
        )
        
        # Create LoRA model and move to GPU
        model = LoraModel(model, lora_config, adapter_name).to("cuda")
        
        # Initialize optimizer for checkpoint loading
        optimizer = torch.optim.AdamW(model.parameters(), lr=1e-5)
        
        # Load checkpoint
        logger.info(f"Loading checkpoint from: {CHECKPOINT_PATH}")
        state_dict = {"app": AppState(model, optimizer)}
        dcp.load(state_dict=state_dict, checkpoint_id=CHECKPOINT_PATH)
        
        # Store the model globally for reuse
        global_model = model
        
        logger.info("Model and checkpoint loaded successfully")
        return True
    except Exception as e:
        logger.error(f"Error loading model: {e}")
        return False


@app.route('/health', methods=['GET'])
def health_check():
    """Endpoint to check if the service is running and the model is loaded"""
    if global_model is not None and global_tokenizer is not None:
        return jsonify({
            "status": "healthy",
            "model": MODEL_NAME
        })
    else:
        return jsonify({
            "status": "unhealthy",
            "error": "Model not loaded"
        }), 500


@app.route('/generate', methods=['POST'])
def generate():
    """Endpoint to generate a response to a query using the LoRA model"""
    # Check if model is loaded
    if global_model is None or global_tokenizer is None:
        return jsonify({"error": "Model not loaded"}), 500
    
    # Get the query from the request
    data = request.json
    if not data or 'query' not in data:
        return jsonify({"error": "No query provided"}), 400
    
    query = data['query'].strip()
    logger.info(f"Received query: {query}")
    
    try:
        # Format input according to DeepSeek-R1 template
        # Check if custom template is provided
        template_type = data.get('template_type', 'default')
        max_new_tokens = data.get('max_new_tokens', 512)
        temperature = data.get('temperature', 0.8)
        
        if template_type == 'simple':
            # Simple Q&A template
            deepseek_input = f"Question: {query}, Answer:"
        else:
            # Default DeepSeek-R1 template
            deepseek_input = f'''
A conversation between User and Assistant. The user asks a question, and the Assistant solves it.
The assistant first thinks about the reasoning process in the mind and then provides the user
with the answer. The reasoning process and answer are enclosed within <think> </think> and
<answer> </answer> tags, respectively, i.e., <think> reasoning process here </think>
<answer> answer here </answer>. User: {query}. Assistant:'''
        
        # Tokenize the input
        encoding = global_tokenizer(deepseek_input, return_tensors="pt")
        input_ids = encoding['input_ids'].to("cuda")
        attention_mask = encoding['attention_mask'].to("cuda")
        
        # Generate response
        with torch.no_grad():
            generate_ids = global_model.generate(
                input_ids, 
                attention_mask=attention_mask, 
                pad_token_id=global_tokenizer.eos_token_id, 
                max_new_tokens=max_new_tokens, 
                do_sample=True, 
                temperature=temperature
            )
            
        # Decode the response
        answer = global_tokenizer.batch_decode(
            generate_ids, 
            skip_special_tokens=True, 
            clean_up_tokenization_spaces=False
        )
        
        logger.info("Response generated successfully")
        return jsonify({
            "success": True,
            "query": query,
            "response": answer[0],
            "model": MODEL_NAME
        })
    
    except Exception as e:
        logger.error(f"Error generating response: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


if __name__ == '__main__':
    # Load the model at startup
    is_model_loaded = load_model()
    
    if not is_model_loaded:
        logger.error("Failed to load model. Exiting.")
        exit(1)
    
    # Get port from environment or use default
    port = int(os.environ.get('PORT', 5600))
    
    # Log startup information
    logger.info(f"Starting LoRA inference API on port {port}")
    logger.info(f"Model: {MODEL_NAME}")
    logger.info(f"Checkpoint: {CHECKPOINT_PATH}")
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=port, debug=False) 