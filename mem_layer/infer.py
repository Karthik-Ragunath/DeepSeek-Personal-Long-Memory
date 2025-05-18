from mem0 import MemoryClient
client = MemoryClient(api_key="m0-PxCfRoQH5BAgWj2UONAiq9d3rh1P5sVrVqz9VXKO")
query = "Describe your early experiences in art school and the city."
response = client.search(query, user_id="elara")
print(response)
response_answer = client.search(query, user_id="elara")[0]['memory']
print(response_answer)