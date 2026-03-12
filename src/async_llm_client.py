import httpx
import json
from src.prompts import build_column_analysis_prompt, DQ_SYSTEM_PROMPT

URL = "http://localhost:11434"
CHAT_URL = URL+"/api/chat"

class AsyncLLMClient:
    def __init__(self, model: str = "llama3.2:latest", temperature: float = 0):
        self.model = model
        self.temperature = temperature

    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=180) as client:
                response = await client.get(URL)
                return response.is_success
        except httpx.RequestError:
            return False

    async def chat(self, system_prompt: str, user_message: str) -> str | None:
        try:
            async with httpx.AsyncClient(timeout=180) as client:
                response = await client.post(
                    CHAT_URL,
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_message}
                        ],
                        "stream": False,
                        "options": {
                            "temperature": self.temperature
                        }
                    }
                )
                data = response.json()
                return data["message"]["content"]
        except httpx.RequestError as e:
            print(f"LLM request failed: {e}")
            return None

    async def chat_with_history(self, history: list[dict]) -> str | None:
        """Send a full conversation history to the LLM"""
        try:
            async with httpx.AsyncClient(timeout=180) as client:
                response = await client.post(
                    CHAT_URL,
                    json={
                        "model": self.model,
                        "messages": history,
                        "stream": False,
                        "options": {
                            "temperature": self.temperature
                        }
                    }
                )
                data = response.json()
                return data["message"]["content"]
        except httpx.RequestError as e:
            print(f"LLM request failed: {e}")
            return None

    async def analyse_table(self, table_name: str, null_stats: dict, row_count: int) -> dict | None:
        user_prompt = build_column_analysis_prompt(table_name, null_stats, row_count)
        response = await self.chat(DQ_SYSTEM_PROMPT, user_prompt)
        cleaned_response = self.clean_model_output(response)

        try:
            return json.loads(cleaned_response)
        except json.JSONDecodeError as e:
            print(f"Failed to parse LLM response as JSON: {e}")
            print(f"Raw response: {cleaned_response[:200]}")
            return None

    def clean_model_output(self, raw: str) -> str:
        """ Clean up response in case model adds markdown code fences """

        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        return raw.strip()