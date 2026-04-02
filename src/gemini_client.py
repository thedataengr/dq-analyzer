import os, json
from dotenv import load_dotenv
from google import genai
from google.genai import types, errors
from langsmith import traceable
from src.prompts import build_column_analysis_prompt, DQ_SYSTEM_PROMPT


class GeminiClient:
    """Wrap Gemini API calls used by the data quality workflows.

    Attributes:
        model: The Gemini model name used for requests.
        temperature: Sampling temperature for model responses.
        client: Configured Gemini API client instance.

    """
    def __init__(self, model: str = "gemini-2.5-flash", temperature: float = 0):
        """Configure the Gemini client and load credentials from the environment.

        Args:
            model: Gemini model name to use for requests.
            temperature: Sampling temperature for response generation.

        """
        self.model = model
        self.temperature = temperature

        load_dotenv()
        self.client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))


    def is_available(self) -> bool:
        """Check whether Gemini is reachable with the current configuration.

        Returns:
            bool: True if the API responds successfully; otherwise, False.

        """
        try:
            llm_response = self.client.models.generate_content(
                model=self.model,
                contents="Hi",
                config=types.GenerateContentConfig(max_output_tokens=5)
            )
            return bool(llm_response.text)
        except Exception as e:
            print(f"Connection to Gemini failed: {type(e).__name__} - {e}")
            return False

    def chat(self, system_prompt: str, user_message: str, json_mode: bool = False) -> str | None:
        """Send a prompt to Gemini and return the generated text response.

        Args:
            system_prompt: System instructions for the model.
            user_message: User prompt content to submit.
            json_mode: Whether to request a JSON-formatted response.

        Returns:
            str | None: The generated response text, or `None` on failure.

        """
        try:
            llm_response = self.client.models.generate_content(
                model=self.model,
                contents=user_message,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=self.temperature,
                    **({"response_mime_type": "application/json"} if json_mode else {})
                )
            )
            return llm_response.text
        except errors.ClientError as e:
            # 4xx Errors (e.g., 401 Unauthorized, 404 Not Found, 429 Rate Limit)
            print(f"Client Error (Check API Key/Model Name): {e.status} - {e.message}")
        except errors.ServerError as e:
            # 5xx Errors (e.g., 500 Internal Error, 503 Service Unavailable)
            print(f"Server Error (Google side issue): {e.status} - {e.message}")
        except Exception as e:
            # General network or unexpected errors
            print(f"Unexpected Error: {type(e).__name__} - {e}")

        return None

    def _convert_history(self, messages: list[dict]) -> list:
        """Convert application message history into Gemini content objects.

        Args:
            messages: Conversation history in the application's message format.

        Returns:
            list: Gemini `Content` objects representing the conversation history.

        """
        converted = []
        for msg in messages:
            role = "model" if msg["role"] == "assistant" else msg["role"]
            converted.append(
                types.Content(
                    role=role,
                    parts=[types.Part(text=msg["content"])]
                )
            )
        return converted

    def chat_with_history(self, history: list[dict]) -> str | None:
        """Send a full conversation history to Gemini.

        Args:
            history: Conversation history represented as message dictionaries.

        Returns:
            str | None: The generated response text, or `None` on failure.

        """
        try:
            llm_response = self.client.models.generate_content(
                model=self.model,
                contents=self._convert_history(history),
                config=types.GenerateContentConfig(
                    system_instruction="You are a data quality expert.",
                    temperature=self.temperature
                )
            )
            return llm_response.text
        except errors.ClientError as e:
            # 4xx Errors (e.g., 401 Unauthorized, 404 Not Found, 429 Rate Limit)
            print(f"Client Error (Check API Key/Model Name): {e.status} - {e.message}")
        except errors.ServerError as e:
            # 5xx Errors (e.g., 500 Internal Error, 503 Service Unavailable)
            print(f"Server Error (Google side issue): {e.status} - {e.message}")
        except Exception as e:
            # General network or unexpected errors
            print(f"Unexpected Error: {type(e).__name__} - {e}")

        return None

    @traceable(name="llm_analyse_table", tags=["llm", "analysis"])
    def analyse_table(self, table_name: str, null_stats: dict, row_count: int) -> dict | None:
        """Request structured Gemini analysis for a table's null statistics.

        Args:
            table_name: Name of the table being analyzed.
            null_stats: Null counts grouped by column.
            row_count: Total number of rows in the table.

        Returns:
            dict | None: Parsed analysis output, or `None` if analysis fails.

        """
        user_prompt = build_column_analysis_prompt(table_name, null_stats, row_count)
        llm_response = self.chat(DQ_SYSTEM_PROMPT, user_prompt, json_mode=True)
        if not llm_response:
            return None

        try:
            return json.loads(llm_response)
        except json.JSONDecodeError as e:
            print(f"Failed to parse LLM response as JSON: {e}")
            print(f"Raw response: {llm_response[:200]}")
            return None


