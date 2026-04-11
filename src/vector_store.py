import re
from pathlib import Path
import chromadb
from google import genai

class GeminiEmbeddingFunction:
    """Custom embedding function using Google's text-embedding-004 model"""

    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)
        self.model = "models/gemini-embedding-001"

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        embeddings = []
        for text in texts:
            result = self.client.models.embed_content(
                model=self.model,
                contents=text
            )
            embeddings.append(result.embeddings[0].values)
        return embeddings

    def embed_query(self, text: str) -> list[float]:
        result = self.client.models.embed_content(
            model=self.model,
            contents=text
        )
        return result.embeddings[0].values


class SchemaVectorStore:
    def __init__(self,api_key, persist_path="./chroma_db"):
        """creates ChromaDB client and Gemini embedding function"""
        self.embedding_func = GeminiEmbeddingFunction(api_key=api_key)
        self.client = chromadb.PersistentClient(path=persist_path) # Create a local persistent client

        # Create a collection — like a table for embeddings
        self.collection = self.client.get_or_create_collection(name="schema_docs")

    def index_documents(self,docs_path: str):
        """reads the markdown file, splits by table section (split on `## Table:`),
        embeds each section, stores in ChromaDB with metadata `{"table": table_name}`"""
        docs_file = Path(docs_path)
        if not docs_file.exists():
            raise FileNotFoundError(f"Schema docs file not found: {docs_path}")

        contents = docs_file.read_text(encoding="utf-8").strip()
        if not contents:
            return

        raw_sections = re.split(r"(?=^## Table:\s+)", contents, flags=re.MULTILINE)
        table_docs = []

        for section in raw_sections:
            section = section.strip()
            if not section.startswith("## Table:"):
                continue

            table_docs.append(section)

        if not table_docs:
            return

        print("Indexing schema documentation...")
        for doc in table_docs:
            first_line = doc.splitlines()[0]
            match = re.match(r"## Table:\s+(.+)", first_line)
            if not match:
                continue

            table_name = match.group(1).strip()
            print(f"→ Processing: Table: {table_name}")
            embedding_vector = self.embedding_func.embed_documents([doc])
            self.collection.upsert(
                documents=[doc],
                embeddings=embedding_vector,
                ids=[f"table:{table_name}"],
                metadatas=[{"source": docs_file.stem, "table": table_name}]
            )

        print(f"Indexed {self.collection.count()} documents successfully")

    def search(self,query: str, n_results: int = 3) -> list[dict]:
        """embeds the query, retrieves top N results, returns list of dicts with `text` and `metadata` keys"""
        # Query for similar documents

        query_embedding = self.embedding_func.embed_query(query)
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results  # return top n most similar chunks
        )
        return [
            {
                "text": doc,
                "metadata": meta
            }
            for doc, meta in zip(
                results["documents"][0],
                results["metadatas"][0]
            )
        ]


    def is_indexed(self) -> bool:
        """returns True if the collection already has documents, False if empty"""
        return self.collection.count() > 0

    def get_collection_stats(self) -> dict:
        """returns {"total_documents": N, "collection_name": "..."}"""
        return {
            "total_documents": self.collection.count(),
            "collection_name": self.collection.name
        }
