from datasets import load_dataset, disable_progress_bars

repeat = 100

def preprocess_function(examples):
    # Combine instruction and response into a single text
    texts = [f"Question: {q}\nAnswer: {a}" for q, a in zip(examples['instruction'], examples['response'])]
    # Return a dictionary with the processed texts
    return {"text": texts}

dataset_path = "/root/isc-demos/deepseek/elara_life_dataset.jsonl"
dataset = load_dataset("json", data_files=dataset_path, cache_dir="/tmp/elara_life")
split_dataset = dataset["train"].train_test_split(test_size=0.2, seed=42)
dataset = {"train": split_dataset["train"], "test": split_dataset["test"]}
list_train = dataset["train"].map(
    preprocess_function, batched=True,
    remove_columns=dataset["train"].column_names, desc="Tokenizing and preprocessing train dataset"
)
list_test = dataset["test"].map(
    preprocess_function, batched=True,
    remove_columns=dataset["test"].column_names, desc="Tokenizing and preprocessing test dataset"
)

# print(dataset)
print("Training List:")
print(list_train)

print("-" * repeat)

print("Testing List:")
print(list_test)

print("-" * repeat)
