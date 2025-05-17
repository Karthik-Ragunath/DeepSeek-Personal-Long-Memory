from mem0 import MemoryClient
client = MemoryClient(api_key="m0-PxCfRoQH5BAgWj2UONAiq9d3rh1P5sVrVqz9VXKO")
query = "What's your most vivid early childhood memory?"
response = client.search(query, user_id="elara")[0]['memory']
print(response)