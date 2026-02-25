import os
import asyncio
from dotenv import load_dotenv
from openai import OpenAI
import faiss
import numpy as np
import json

class AIAnalyzer:
    def __init__(self):
        load_dotenv()  # Load environment variables from .env file
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.index = None
        self.id_map = {}

    async def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for a list of text inputs.
        """
        batches = [texts[i:i+100] for i in range(0, len(texts), 100)]
        total_batches = len(batches)
        embeddings = []

        for i, batch in enumerate(batches):
            response = self.client.embeddings.create(
                model="text-embedding-3-small",
                input=batch
            )
            batch_embeddings = [item.embedding for item in response.data]
            embeddings.extend(batch_embeddings)
            print(f"Embedded batch {i+1}/{total_batches}...")

        return embeddings

    def build_faiss_index(self, embeddings, log_ids: list[str]):
        """
        Build a FAISS index for efficient similarity search.
        """
        # Create FAISS index with 1536 dimensions (matches text-embedding-3-small)
        index = faiss.IndexFlatIP(1536)
        np_array = np.array(embeddings, dtype=np.float32)
        index.add(np_array)
        self.index = index
        self.id_map = {i: log_id for i, log_id in enumerate(log_ids)}

    async def search_similar(self, query: str, k=5) -> list[str]:
        """
        Find the top k most similar log entries to the given query.
        """
        # Generate query embedding
        response = self.client.embeddings.create(
            model="text-embedding-3-small",
            input=[query]
        )
        query_embedding = np.array([response.data[0].embedding], dtype=np.float32)

        if self.index is None:
            return []

        # Search for nearest neighbors
        distances, indices = self.index.search(query_embedding, k)

        # Extract corresponding log IDs
        log_ids = [self.id_map[i] for i in indices[0]]
        return log_ids

    async def analyze_root_cause(self, logs, model="gpt-4o"):
        """
        Analyze logs using selected AI model to determine root cause and provide solutions.
        Supports gpt-4o, gpt-4-turbo, and gpt-3.5-turbo.
        """
        # Format logs into a string for the model
        formatted_logs = "\n\n".join([
            f"Log {i+1}:\n{log}"
            for i, log in enumerate(logs[:10])  # Use top 10 logs for better context
        ])

        # Prepare the system and user messages for Chat API
        messages = [
            {"role": "system", "content": "You are a professional system reliability engineer. Analyze logs and return results strictly in JSON format."},
            {"role": "user", "content": f"""
            Analyze the following logs to determine the root cause, impact, and solution.
            Return a JSON object with these keys:
            - cause: string, the identified root cause
            - impact: string, how this affects the system
            - solution: string, specific steps to fix it
            - confidence: string (HIGH/MEDIUM/LOW)
            - severity: string (CRITICAL/HIGH/MEDIUM/LOW)
            - affected_services: list of strings

            Logs:
            {formatted_logs}
            """}
        ]

        try:
            # Call the Chat Completion API
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                response_format={ "type": "json_object" } if model in ["gpt-4o", "gpt-4-turbo"] else None,
                max_tokens=800,
                temperature=0.3
            )
            
            # Parse the response
            content = response.choices[0].message.content
            analysis = json.loads(content)
        except Exception as e:
            print(f"AI Analysis error with {model}: {e}")
            analysis = {
                "cause": "Manual review required: AI analysis encountered an error.",
                "impact": "Unconfirmed",
                "solution": "Check service logs directly for immediate resolution.",
                "confidence": "LOW",
                "severity": "HIGH",
                "affected_services": []
            }

        return analysis
