
import ollama
import time

model = "llama3.1:8b"
prompt = "Is this video about science? Title: Black Holes Explained"
system = "You are a triage classifier. Return JSON: {'category': 'KNOWLEDGE', 'confidence': 0.9, 'reason': 'test'}"

print(f"Calling Ollama with model {model}...")
start = time.time()
try:
    response = ollama.chat(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        options={"temperature": 0.1}
    )
    print(f"Response received in {time.time() - start:.2f}s")
    print(response['message']['content'])
except Exception as e:
    print(f"Error: {e}")
