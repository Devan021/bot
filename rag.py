from sentence_transformers import SentenceTransformer
from typing import List, Dict
import numpy as np
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class RAGSystem:
    def __init__(self, collection):
        self.model = SentenceTransformer('intfloat/e5-base-v2')
        self.collection = collection

    def get_embedding(self, text: str) -> List[float]:
        try:
            return self.model.encode(text, convert_to_tensor=False).tolist()
        except Exception as e:
            logger.error(f"Embedding error: {e}")
            return []

    def add_document(self, text: str, metadata: Dict = None):
        try:
            embedding = self.get_embedding(text)
            doc = {
                'text': text,
                'embedding': embedding,
                'metadata': metadata or {},
                'timestamp': datetime.utcnow()
            }
            self.collection.insert_one(doc)
        except Exception as e:
            logger.error(f"Document addition error: {e}")

    def search(self, query: str, limit: int = 5):
        try:
            query_embedding = self.get_embedding(query)
            results = self.collection.aggregate([
                {
                    "$addFields": {
                        "similarity": {
                            "$reduce": {
                                "input": {"$zip": {"inputs": ["$embedding", query_embedding]}},
                                "initialValue": 0,
                                "in": {"$add": ["$$value", {"$multiply": ["$$this.0", "$$this.1"]}]}
                            }
                        }
                    }
                },
                {"$sort": {"similarity": -1}},
                {"$limit": limit}
            ])
            return list(results)
        except Exception as e:
            logger.error(f"Search error: {e}")
            return []
