"""
Alita — The Brain
Orchestrates personality, memory, and LLM to create the complete AI partner experience.
"""

import json
import re
import uuid
from datetime import datetime

from .llm import LLMProvider
from .memory import MemoryManager
from .personality import get_system_prompt, PROFILE_UPDATE_PROMPT, REFLECTION_PROMPT

# ─── Post-Processing: Clean LLM Output ──────────────────────────
# The LLM sometimes outputs emojis/markdown even when told not to.
# We strip them here so neither the text display nor TTS ever sees them.
EMOJI_RE = re.compile(
    "["
    "\U0001F600-\U0001F64F"
    "\U0001F300-\U0001F5FF"
    "\U0001F680-\U0001F6FF"
    "\U0001F1E0-\U0001F1FF"
    "\U00002702-\U000027B0"
    "\U000024C2-\U0001F251"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FA6F"
    "\U0001FA70-\U0001FAFF"
    "\U00002600-\U000026FF"
    "\U0000FE00-\U0000FE0F"
    "\U00010000-\U0010FFFF"
    "]+",
    flags=re.UNICODE,
)


def _clean_response(text: str) -> str:
    """Strip emojis and markdown from LLM response."""
    # Remove emojis completely
    text = EMOJI_RE.sub("", text)
    # Remove bold/italic markdown
    text = re.sub(r'\*{1,3}([^*\n]+)\*{1,3}', r'\1', text)
    # Remove markdown headers
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    # Clean up extra whitespace
    text = re.sub(r' {2,}', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


class Alita:
    """The main Alita brain — ties everything together."""

    def __init__(self, user_name: str = "Kundan"):
        self.user_name = user_name
        self.llm = LLMProvider()
        self.memory = MemoryManager()
        self.session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        self.conversation_turn = 0

        print(f"\n💜 Alita is awake. Session: {self.session_id}")
        print(f"   Memories: {self.memory.get_message_count()} messages stored")
        print(f"   Vector memories: {self.memory.memory_collection.count()}")
        print(f"   LLM: {self.llm.get_status()['primary']}\n")

    async def chat(self, user_message: str) -> str:
        """Process a user message and return Alita's response."""

        # 1. Save user message to memory
        self.memory.save_message("user", user_message, self.session_id)
        self.conversation_turn += 1

        # 2. Recall relevant memories (fewer = faster response)
        relevant_memories = self.memory.recall_memories(user_message, n_results=3)

        # 3. Build the system prompt with personality + memories + profile
        system_prompt = get_system_prompt(
            user_name=self.user_name,
            user_profile=self.memory.get_profile(),
            recent_memories=relevant_memories,
        )

        # 4. Get recent conversation for context (less = faster)
        recent_messages = self.memory.get_recent_messages(limit=10)
        chat_messages = [{"role": m["role"], "content": m["content"]} for m in recent_messages]

        # 5. Get Alita's response from LLM
        raw_response = await self.llm.chat(system_prompt, chat_messages)

        # 6. POST-PROCESS: clean emojis and markdown from response
        response = _clean_response(raw_response)
        if not response:
            response = raw_response  # fallback if cleaning removes everything

        # 7. Save Alita's response to memory
        self.memory.save_message("assistant", response, self.session_id)

        # 8. Background tasks: update profile and write reflection every 5 turns
        if self.conversation_turn % 5 == 0:
            await self._update_profile_background()
            await self._write_reflection_background()

        return response

    async def _update_profile_background(self):
        """Update the user profile based on recent conversation."""
        try:
            recent = self.memory.get_recent_messages(limit=10)
            conversation_text = "\n".join(f"{m['role']}: {m['content']}" for m in recent)

            prompt = PROFILE_UPDATE_PROMPT.format(
                user_name=self.user_name,
                current_profile=json.dumps(self.memory.get_profile(), indent=2),
                conversation=conversation_text,
            )

            new_profile = await self.llm.chat_json(prompt, [{"role": "user", "content": "Update the profile based on the conversation above."}])

            if new_profile:
                self.memory.update_profile(new_profile)
                print("🧠 Profile updated!")
        except Exception as e:
            print(f"⚠️ Profile update failed: {e}")

    async def _write_reflection_background(self):
        """Write a diary reflection about the recent conversation."""
        try:
            recent = self.memory.get_recent_messages(limit=10)
            conversation_text = "\n".join(f"{m['role']}: {m['content']}" for m in recent)

            prompt = REFLECTION_PROMPT.format(
                user_name=self.user_name,
                conversation=conversation_text,
            )

            reflection = await self.llm.chat(prompt, [{"role": "user", "content": "Write your reflection."}], temperature=0.7)

            if reflection:
                self.memory.save_reflection(reflection)
                print("📝 Reflection written!")
        except Exception as e:
            print(f"⚠️ Reflection failed: {e}")

    def get_stats(self) -> dict:
        """Get current status and stats."""
        return {
            "session_id": self.session_id,
            "conversation_turn": self.conversation_turn,
            "llm_status": self.llm.get_status(),
            "memory_stats": self.memory.get_memory_stats(),
            "user_profile": self.memory.get_profile(),
        }
