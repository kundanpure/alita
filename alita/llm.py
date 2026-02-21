"""
LLM Integration for Alita — Multi-Key Rotation
Supports multiple API keys per provider. Auto-rotates on rate limit errors.
Groq (primary, fastest) → Google Gemini (backup).
"""

import json
import os
import asyncio
import random
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


class LLMProvider:
    """Manages LLM API calls with multi-key rotation and auto-fallback."""

    def __init__(self):
        # Parse multiple keys — comma-separated in .env
        self.groq_keys = self._parse_keys("GROQ_API_KEY")
        self.google_keys = self._parse_keys("GOOGLE_API_KEY")

        self.groq_clients = []
        self.google_clients = []
        self.groq_idx = 0
        self.google_idx = 0

        # Initialize Groq clients
        if self.groq_keys:
            try:
                from groq import Groq
                for i, key in enumerate(self.groq_keys):
                    client = Groq(api_key=key)
                    self.groq_clients.append(client)
                print(f"✅ Groq API connected — {len(self.groq_clients)} key(s) loaded")
            except Exception as e:
                print(f"⚠️ Groq init failed: {e}")

        # Initialize Google clients
        if self.google_keys:
            try:
                from google import genai
                for i, key in enumerate(self.google_keys):
                    client = genai.Client(api_key=key)
                    self.google_clients.append(client)
                print(f"✅ Google AI connected — {len(self.google_clients)} key(s) loaded")
            except Exception as e:
                print(f"⚠️ Google AI init failed: {e}")

        if not self.groq_clients and not self.google_clients:
            print("❌ No LLM API keys found! Add keys to .env file.")

    def _parse_keys(self, env_var: str) -> list[str]:
        """Parse comma-separated API keys from env variable."""
        raw = os.getenv(env_var, "")
        if not raw:
            return []
        keys = [k.strip() for k in raw.split(",") if k.strip()]
        # Filter out placeholder keys
        keys = [k for k in keys if k not in ("gsk_your_key_here", "your_key_here", "")]
        return keys

    def _next_groq(self):
        """Rotate to next Groq key."""
        self.groq_idx = (self.groq_idx + 1) % len(self.groq_clients)

    def _next_google(self):
        """Rotate to next Google key."""
        self.google_idx = (self.google_idx + 1) % len(self.google_clients)

    async def chat(self, system_prompt: str, messages: list[dict], temperature: float = 0.85) -> str:
        """Send chat request. Tries all Groq keys, then all Google keys."""

        # Try ALL Groq keys
        if self.groq_clients:
            for attempt in range(len(self.groq_clients)):
                try:
                    client = self.groq_clients[self.groq_idx]
                    result = await self._chat_groq(client, system_prompt, messages, temperature)
                    self._next_groq()  # rotate for next request
                    return result
                except Exception as e:
                    err = str(e).lower()
                    print(f"⚠️ Groq key #{self.groq_idx + 1} failed: {str(e)[:80]}")
                    self._next_groq()
                    # If it's a rate limit, try next key
                    if "rate" in err or "limit" in err or "429" in err or "quota" in err:
                        continue
                    # If it's another error, also try next (could be temp failure)
                    continue

        # Try ALL Google keys
        if self.google_clients:
            for attempt in range(len(self.google_clients)):
                try:
                    client = self.google_clients[self.google_idx]
                    result = await self._chat_google(client, system_prompt, messages, temperature)
                    self._next_google()
                    return result
                except Exception as e:
                    err = str(e).lower()
                    print(f"⚠️ Google key #{self.google_idx + 1} failed: {str(e)[:80]}")
                    self._next_google()
                    if "rate" in err or "limit" in err or "429" in err or "quota" in err:
                        continue
                    continue

        return "Abhi connection mein problem aa rahi hai. Thodi der baad try kar."

    async def chat_json(self, system_prompt: str, messages: list[dict]) -> dict | None:
        """Send a chat request expecting a JSON response."""
        response = await self.chat(system_prompt, messages, temperature=0.3)
        try:
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            return json.loads(response.strip())
        except json.JSONDecodeError:
            print(f"⚠️ JSON parse failed: {response[:100]}...")
            return None

    async def _chat_groq(self, client, system_prompt: str, messages: list[dict], temperature: float) -> str:
        """Chat using Groq API."""
        formatted = [{"role": "system", "content": system_prompt}]
        for msg in messages:
            formatted.append({"role": msg["role"], "content": msg["content"]})

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.chat.completions.create(
                model="llama-3.1-8b-instant",  # High rate limits, valid model name
                messages=formatted,
                temperature=temperature,
                max_tokens=512,  # shorter = faster
            ),
        )
        return response.choices[0].message.content

    async def _chat_google(self, client, system_prompt: str, messages: list[dict], temperature: float) -> str:
        """Chat using Google AI Studio (Gemini)."""
        from google.genai import types

        contents = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            contents.append(types.Content(role=role, parts=[types.Part(text=msg["content"])]))

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.models.generate_content(
                model="gemini-2.0-flash",
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=temperature,
                    max_output_tokens=512,
                ),
            ),
        )
        return response.text

    def get_status(self) -> dict:
        return {
            "groq": f"{len(self.groq_clients)} keys" if self.groq_clients else "none",
            "google": f"{len(self.google_clients)} keys" if self.google_clients else "none",
            "primary": "groq" if self.groq_clients else ("google" if self.google_clients else "none"),
        }
