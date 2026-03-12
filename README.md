# DQ-Analyzer: AI-Powered Data Quality Insights

**DQ-Analyzer** AI-powered data quality exploration tool that integrates directly with PostgreSQL and performs column-level analysis across multiple tables concurrently by leveraging **asynchronous execution**. It utilizes local Large Language Models (via Ollama) to generate human-readable interpretations and remediation recommendations, empowering engineers to identify and resolve data quality issues faster.

---

### 🚀 What It Does
* **Automated Null Analysis:** Calculates null counts and percentages at both the column and table levels across your entire PostgreSQL schema.
* **Local LLM Integration:** Leverages local LLMs (Ollama) to transform statistical output into insightful natural language summaries.
* **Interactive Data Chat:** Interactive multi-turn chat session to ask questions to AI about table structure and data quality. AI can also generate SQL queries to delve deep into data quality issues.
* **Intelligent Prompting:** Uses a specialized "DQ Expert" system prompt to ensure LLM responses are technical, accurate, and actionable.
* **Formatted Reporting:** Generates neatly formatted data quality reports and LLM analysis.

---

### 🛠️ Tech Stack
* **Language:** Python 3.10+
* **Database:** PostgreSQL
* **ORM:** SQLAlchemy
* **AI/LLM:** Ollama (Local)
* **Concurrency:** asyncio & httpx (for high-performance, non-blocking LLM and DB operations)
* **Future Roadmap:** LangGraph for agentic data quality workflows.

---

### 🏗️ Architecture
The project follows a modular, **non-blocking design**. The `async_reporter` utilizes `asyncio` and ThreadPoolExecutor to orchestrate metadata retrieval across multiple tables concurrently, while `async_llm_client` uses `httpx` to communicate with the local Ollama API without stalling the main event loop. This allows the system to remain responsive even when processing large schemas or waiting for AI-generated interpretations. The `reporter` handles formatted reporting. The `prompts.py` module acts as the "brain," holding the system persona and logic to generate context-aware prompts for analysis. Conversation state is managed by `conversation` module and `chat_session` handles context-aware chat with LLM , while `main.py` orchestrates the entire pipeline.

---

### 📋 Prerequisites
* **Python 3.10+**
* **PostgreSQL** instance with read access.
* **Ollama** installed and running locally ([Download here](https://ollama.com/)).

---

### ⚙️ Setup
1. **Clone the repository:**
   ```bash
   git clone https://github.com/thedataengr/dq-analyzer.git
   cd dq-analyzer
   
2. **Setup virtual environment:**
   ```bash
    python -m venv .venv
    # Windows
    .venv\Scripts\activate
    # Mac/Linux
    source .venv/bin/activate

    pip install -r requirements.txt

3. **Configure Environment Variables:**
   * Copy .env.example to .env and add your database credentials.
   

4. **Set up sample database:**
```bash
   psql -U your_username -f scripts/setup_db.sql
```

5. **Pull Ollama model:**
   ```bash
   ollama pull llama3.2

---

### 💡 Usage
Run the analyzer with:

    python main.py

### Example Chat Queries
* "Which table needs the most attention based on the current null counts?"
* "Write SQL to check rows with null values in column user_email."

---

### 📂 Project Structure
    dq-analyzer/
    ├── .venv/            # Virtual environment
    ├── scripts/          # Database utility scripts (e.g., setup_db.sql)
    ├── src/              # Core application logic
    │   ├── __init__.py
    │   ├── async_llm_client.py   # Asynchronous communication with Ollama
    │   ├── async_reporter.py     # Asynchronous null statistics collection and analysis
    │   ├── chat_session.py       # Manages chat session with history and context of chat
    │   ├── conversation.py       # Handles chat history
    │   ├── database.py           # Database connection setup and querying
    │   ├── db_inspector.py       # Logic for schema exploration
    │   ├── llm_client.py         # Synchronous LLM wrapper
    │   ├── models.py             # Manages Table Profile
    │   ├── prompts.py            # AI system prompt and user prompt generation
    │   └── reporter.py           # Formatted report generation
    ├── .env.example      # Template for configuration
    ├── .gitignore        # Git ignore rules
    ├── main.py           # Main entry point
    └── requirements.txt  # Project dependencies

---

### 🗺️ Roadmap
* [ ] Multi-tool Data Quality Agent using LangGraph 
* [ ] Defining and running DQ checks programmatically using Great Expectations / Soda Core
* [ ] UI for interactive exploration

