import json

# Path to input file
input_file = "/root/isc-demos/deepseek/elara_life_dataset.jsonl"

# Read the Elara dataset
elara_entries = []
with open(input_file, 'r') as f:
    for line in f:
        elara_entries.append(json.loads(line))

# Convert to conversation format
print("# Elara Life Dataset in Conversation Format")
print()
print("```python")
print("from your_client_library import Client")
print()
print("# Initialize client")
print("client = Client()")
print()

# Process each entry
for i, entry in enumerate(elara_entries):
    instruction = entry['instruction']
    response = entry['response']
    
    # Format as conversation
    print(f"# Conversation {i+1}")
    print("messages = [")
    print(f"    {{\"role\": \"user\", \"content\": \"{instruction}\"}},")
    print(f"    {{\"role\": \"assistant\", \"content\": \"{response}\"}}")
    print("]")
    print("client.add(messages, user_id=\"elara\")")
    print()

print("# Example usage to retrieve conversations")
print("# retrieved_messages = client.get(user_id=\"elara\")")
print("```") 