import transformers
import torch
import re
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
import logging
import re

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Model configuration
MODEL_ID = "PeterJinGo/SearchR1-nq_hotpotqa_train-qwen2.5-7b-em-ppo"
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
CACHE_DIR = "/scratch/hub/"  # Directory to cache model files
EOS_TOKENS = [151645, 151643]  # EOS tokens for Qwen2.5 series models
SEARCH_TEMPLATE = '\n\n{output_text}<information>{search_results}</information>\n\n'
RETRIEVAL_URL = "http://127.0.0.1:8000/retrieve"  # URL for the retrieval service

# Define the custom stopping criterion for search tags
class StopOnSequence(transformers.StoppingCriteria):
    def __init__(self, target_sequences, tokenizer):
        # Encode the string so we have the exact token-IDs pattern
        self.target_ids = [tokenizer.encode(target_sequence, add_special_tokens=False) for target_sequence in target_sequences]
        self.target_lengths = [len(target_id) for target_id in self.target_ids]
        self._tokenizer = tokenizer

    def __call__(self, input_ids, scores, **kwargs):
        # Make sure the target IDs are on the same device
        targets = [torch.as_tensor(target_id, device=input_ids.device) for target_id in self.target_ids]

        if input_ids.shape[1] < min(self.target_lengths):
            return False

        # Compare the tail of input_ids with our target_ids
        for i, target in enumerate(targets):
            if torch.equal(input_ids[0, -self.target_lengths[i]:], target):
                return True

        return False

# Function to extract search query from generated text
def get_query(text):
    pattern = re.compile(r"<search>(.*?)</search>", re.DOTALL)
    matches = pattern.findall(text)
    if matches:
        return matches[-1]
    else:
        return None

# Function to search for information
def search(query: str):
    payload = {
        "queries": [query],
        "topk": 3,
        "return_scores": True
    }
    try:
        results = requests.post(RETRIEVAL_URL, json=payload).json()['result']
        
        def _passages2string(retrieval_result):
            format_reference = ''
            for idx, doc_item in enumerate(retrieval_result):
                content = doc_item['document']['contents']
                title = content.split("\n")[0]
                text = "\n".join(content.split("\n")[1:])
                format_reference += f"Doc {idx+1}(Title: {title}) {text}\n"
            return format_reference

        return _passages2string(results[0])
    except Exception as e:
        logger.error(f"Error during search: {e}")
        return "Search error: Could not retrieve information."

# Initialize the model and tokenizer at startup (only once)
logger.info("Loading model and tokenizer...")
try:
    tokenizer = transformers.AutoTokenizer.from_pretrained(MODEL_ID, cache_dir=CACHE_DIR)
    model = transformers.AutoModelForCausalLM.from_pretrained(
        MODEL_ID, 
        torch_dtype=torch.bfloat16, 
        device_map="auto", 
        cache_dir=CACHE_DIR
    )
    logger.info("Model and tokenizer loaded successfully")
    
    # Setup stopping criteria for search tags
    target_sequences = ["</search>", " </search>", "</search>\n", " </search>\n", "</search>\n\n", " </search>\n\n"]
    stopping_criteria = transformers.StoppingCriteriaList([StopOnSequence(target_sequences, tokenizer)])
    
    model_loaded = True
except Exception as e:
    logger.error(f"Error loading model: {e}")
    model_loaded = False

@app.route('/health', methods=['GET'])
def health_check():
    """Endpoint to check if the service is running and the model is loaded"""
    return jsonify({
        "status": "healthy" if model_loaded else "unhealthy",
        "model_id": MODEL_ID,
        "device": str(DEVICE)
    })

@app.route('/generate', methods=['POST'])
def generate():
    """Endpoint to generate a response for a given query"""
    if not model_loaded:
        return jsonify({"error": "Model not loaded"}), 500
    
    # Get the query from the request
    data = request.json
    if not data or 'query' not in data:
        return jsonify({"error": "No query provided"}), 400
    
    query = data['query'].strip()
    logger.info(f"Received query: {query}")
    
    # Add question mark if not present
    if query[-1] != '?':
        query += '?'
    
    # Build the prompt
    prompt = f"""Answer the given question. \
You must conduct reasoning inside <think> and </think> first every time you get new information. \
After reasoning, if you find you lack some knowledge, you can call a search engine by <search> query </search> and it will return the top searched results between <information> and </information>. \
You can search as many times as your want. \
If you find no further external knowledge needed, you can directly provide the answer inside <answer> and </answer>, without detailed illustrations. For example, <answer> Beijing </answer>. Question: {query}\n"""

    # Apply chat template if available
    if tokenizer.chat_template:
        prompt = tokenizer.apply_chat_template([{"role": "user", "content": prompt}], add_generation_prompt=True, tokenize=False)
    
    full_response = ""
    generation_count = 0
    
    try:
        # Generation loop
        while True:
            if generation_count > 5:  # Limit iterations to prevent infinite loops
                break
                
            # Tokenize the prompt
            input_ids = tokenizer.encode(prompt, return_tensors='pt').to(DEVICE)
            attention_mask = torch.ones_like(input_ids)
            
            # Generate text
            outputs = model.generate(
                input_ids,
                attention_mask=attention_mask,
                max_new_tokens=1024,
                stopping_criteria=stopping_criteria,
                pad_token_id=tokenizer.eos_token_id,
                do_sample=True,
                temperature=0.7
            )
            
            # Check if generation is complete
            if outputs[0][-1].item() in EOS_TOKENS:
                generated_tokens = outputs[0][input_ids.shape[1]:]
                output_text = tokenizer.decode(generated_tokens, skip_special_tokens=True)
                full_response += output_text
                break
            
            # Get generated text and check for search queries
            generated_tokens = outputs[0][input_ids.shape[1]:]
            output_text = tokenizer.decode(generated_tokens, skip_special_tokens=True)
            
            # Check if there's a search query
            tmp_query = get_query(tokenizer.decode(outputs[0], skip_special_tokens=True))
            if tmp_query:
                logger.info(f"Searching for: {tmp_query}")
                search_results = search(tmp_query)
            else:
                search_results = ''
            
            # Update prompt and continue generation
            search_text = SEARCH_TEMPLATE.format(output_text=output_text, search_results=search_results)
            prompt += search_text
            full_response += output_text
            
            if search_results:
                full_response += f"\n[SEARCH RESULTS: '{tmp_query}']\n{search_results}\n"
            
            generation_count += 1
        # Extract final answer from response if present
        answer_pattern = re.compile(r'<answer>(.*?)</answer>', re.DOTALL)
        answer_match = answer_pattern.search(full_response)
        if answer_match:
            final_answer = answer_match.group(1).strip()
        logger.info("Response generation completed")
        logger.info(f"Full response: {full_response}")
        return jsonify({
            "success": True,
            "full_response": full_response,
            "iterations": generation_count,
            "response": final_answer
        })
        
    except Exception as e:
        logger.error(f"Error generating response: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

if __name__ == '__main__':
    # Get port from environment or default to 5500 (different from memory API)
    import os
    port = int(os.environ.get('PORT', 5500))
    
    # Log startup information
    logger.info(f"Starting inference API on port {port}")
    logger.info(f"Model ID: {MODEL_ID}")
    logger.info(f"Device: {DEVICE}")
    
    # Run the app
    app.run(host='0.0.0.0', port=port, debug=False) 