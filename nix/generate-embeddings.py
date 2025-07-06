#!/usr/bin/env python3
"""Generate embeddings for Nixpkgs packages."""

import json
import pickle
import sys
import os
from sentence_transformers import SentenceTransformer
import numpy as np

def main():
    if len(sys.argv) != 3:
        print("Usage: generate-embeddings.py <input.json> <output.pkl>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    # Load packages
    print("Loading packages...")
    with open(input_file, 'r') as f:
        packages = json.load(f)
    
    print(f"Loaded {len(packages)} packages")
    
    # Initialize model from local path
    print("Loading embedding model...")
    model_path = os.environ['SENTENCE_TRANSFORMER_MODEL']
    model = SentenceTransformer(model_path)
    
    # Prepare data for embedding
    package_names = []
    texts_to_embed = []
    
    for entry in packages:
        name = entry['key']
        desc = entry['value'].get('description', '')
        package_names.append(name)
        # Combine name and description for richer embeddings
        texts_to_embed.append(f"{name} {desc}")
    
    # Generate embeddings
    print("Generating embeddings...")
    embeddings = model.encode(texts_to_embed, show_progress_bar=True, batch_size=32)
    
    # Save embeddings
    print(f"Saving embeddings to {output_file}...")
    with open(output_file, 'wb') as f:
        pickle.dump({
            'embeddings': embeddings,
            'names': package_names,
            'packages': packages
        }, f)
    
    print("Done!")

if __name__ == "__main__":
    main()