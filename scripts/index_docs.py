from src.vector_store import SchemaVectorStore
from dotenv import load_dotenv
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent  # scripts/ -> project root
CHROMA_DB_PATH = str(PROJECT_ROOT / "chroma_db")
SCHEMA_DOCS_PATH = str(PROJECT_ROOT / "docs" / "schema_docs.md")

if __name__ == "__main__":
    load_dotenv()
    api_key=os.environ.get("GEMINI_API_KEY")
    store = SchemaVectorStore(api_key, CHROMA_DB_PATH)

    if store.is_indexed():
        index = input("Docs are already indexed. Re-index? (y/n): ").strip().lower()
        if index not in ("yes", "y"):
            print("Skipping re-index. Using existing index.")
        else:
            store.index_documents(SCHEMA_DOCS_PATH)
    else:
        store.index_documents(SCHEMA_DOCS_PATH)

    # Test retrieval after indexing
    test_queries = [
        "why does orders have null customer IDs",
        "what does negative amount mean",
        "when does the ETL job run"
    ]

    print("\nTesting retrieval:")
    for query in test_queries:
        results = store.search(query, n_results=1)
        print(f"\nQ: {query}")
        print(f"A: {results[0]['text'][:200]}...")