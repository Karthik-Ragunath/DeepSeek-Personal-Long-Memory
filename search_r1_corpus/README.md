# Elara Life Dataset for Search-R1

This directory contains the Elara Life Dataset formatted for use with the Search-R1 framework.

## Files

1. `elara_corpus.jsonl` - The corpus file formatted according to Search-R1 requirements:
   - Each line is a JSON object with `id` and `contents` fields
   - `contents` follows the format: `"title"\ntext`

2. `elara_qa_dataset.jsonl` - The QA dataset for training:
   - Follows the required format for Search-R1 training data
   - Contains user prompts and ground truth responses
   - Split into train/test sets (80/20 split)

## How to Use

### Using the Corpus

1. **Index the Corpus**:
   ```bash
   cd /root/isc-demos
   bash search_r1/search/build_index.sh \
     --corpus_path search_r1_corpus/elara_corpus.jsonl \
     --retriever_name e5 \
     --retriever_model intfloat/e5-base
   ```

2. **Launch a Local Retrieval Server**:
   ```bash
   conda activate retriever
   bash retrieval_launch.sh
   ```

3. **Run RL Training with the Elara Dataset**:
   ```bash
   conda activate searchr1
   
   # Modify the config to use the Elara dataset
   # Replace the train dataset path in train_ppo.sh
   # Example: --train_file search_r1_corpus/elara_qa_dataset.jsonl
   
   bash train_ppo.sh
   ```

## Dataset Description

The Elara Life Dataset contains fictional autobiographical information about a character named Elara, including:

- Early life and childhood memories
- Education and career path
- Relationships and personal growth
- Life philosophy and reflections

This dataset is well-suited for testing the Search-R1 framework's ability to reason about and search for information about a consistent character, allowing models to learn to integrate search results with narrative reasoning.

## Example Entry

```json
{
  "id": "0",
  "contents": "\"Elara, can you tell me about your name and where you were born?\"\nMy mother always said she named me Elara after one of Jupiter's moons, a tiny speck of light in the vast darkness. I was born in a small coastal town called Port Blossom, known for its unpredictable weather and the scent of salt and wild roses that always hung in the air. It was the autumn of 1992, during a particularly fierce storm, or so the story goes."
}
``` 