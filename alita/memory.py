"""
Memory System for Alita
Handles all persistent memory: ChromaDB vectors, SQLite chat history, user profile, and reflections.
"""

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

import chromadb
from chromadb.config import Settings

# Base data directory
DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)


class MemoryManager:
    """Manages all of Alita's memory systems."""

    def __init__(self):
        self.data_dir = DATA_DIR
        self.profile_path = self.data_dir / "user_profile.json"
        self.reflections_dir = self.data_dir / "reflections"
        self.reflections_dir.mkdir(exist_ok=True)

        # Initialize all memory systems
        self._init_sqlite()
        self._init_chromadb()
        self._load_profile()

    # ─── SQLite: Chat History ────────────────────────────────────

    def _init_sqlite(self):
        """Initialize SQLite database for exact chat history."""
        db_path = self.data_dir / "chat_history.db"
        self.db = sqlite3.connect(str(db_path), check_same_thread=False)
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                session_id TEXT,
                mood TEXT
            )
        """)
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                started_at TEXT NOT NULL,
                summary TEXT
            )
        """)
        self.db.commit()

    def save_message(self, role: str, content: str, session_id: str = None, mood: str = None):
        """Save a message to chat history."""
        self.db.execute(
            "INSERT INTO messages (role, content, timestamp, session_id, mood) VALUES (?, ?, ?, ?, ?)",
            (role, content, datetime.now().isoformat(), session_id, mood),
        )
        self.db.commit()

        # Also store in ChromaDB for semantic search
        if role == "user":
            self._store_in_vector_memory(content)

    def get_recent_messages(self, limit: int = 20) -> list[dict]:
        """Get recent chat messages."""
        cursor = self.db.execute(
            "SELECT role, content, timestamp FROM messages ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        rows = cursor.fetchall()
        rows.reverse()  # Chronological order
        return [{"role": r[0], "content": r[1], "timestamp": r[2]} for r in rows]

    def get_all_messages_for_session(self, session_id: str) -> list[dict]:
        """Get all messages from a specific session."""
        cursor = self.db.execute(
            "SELECT role, content, timestamp FROM messages WHERE session_id = ? ORDER BY id",
            (session_id,),
        )
        return [{"role": r[0], "content": r[1], "timestamp": r[2]} for r in cursor.fetchall()]

    def get_message_count(self) -> int:
        """Get total number of messages."""
        cursor = self.db.execute("SELECT COUNT(*) FROM messages")
        return cursor.fetchone()[0]

    # ─── ChromaDB: Semantic / Vector Memory ──────────────────────

    def _init_chromadb(self):
        """Initialize ChromaDB for semantic memory search."""
        chroma_dir = self.data_dir / "chroma"
        chroma_dir.mkdir(exist_ok=True)
        self.chroma_client = chromadb.PersistentClient(path=str(chroma_dir))
        self.memory_collection = self.chroma_client.get_or_create_collection(
            name="alita_memories",
            metadata={"description": "All of Alita's memories about the user"},
        )

    def _store_in_vector_memory(self, text: str):
        """Store a piece of text in vector memory for semantic recall."""
        doc_id = f"msg_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        self.memory_collection.add(
            documents=[text],
            ids=[doc_id],
            metadatas=[{"timestamp": datetime.now().isoformat(), "type": "user_message"}],
        )

    def recall_memories(self, query: str, n_results: int = 5) -> list[str]:
        """Search for relevant memories based on a query."""
        if self.memory_collection.count() == 0:
            return []

        results = self.memory_collection.query(
            query_texts=[query],
            n_results=min(n_results, self.memory_collection.count()),
        )

        memories = []
        if results and results["documents"]:
            for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
                timestamp = meta.get("timestamp", "unknown time")
                # Format nicely
                try:
                    dt = datetime.fromisoformat(timestamp)
                    time_str = dt.strftime("%b %d, %Y at %I:%M %p")
                except Exception:
                    time_str = timestamp
                memories.append(f"[{time_str}] {doc}")

        return memories

    # ─── User Profile: Core Memory ───────────────────────────────

    def _load_profile(self):
        """Load or create the user profile."""
        if self.profile_path.exists():
            with open(self.profile_path, "r", encoding="utf-8") as f:
                self.user_profile = json.load(f)
        else:
            self.user_profile = {
                "name": None,
                "nickname": None,
                "birthday": None,
                "personality_notes": None,
                "current_goals": [],
                "likes": [],
                "dislikes": [],
                "relationships": {},
                "recent_mood": None,
                "important_dates": {},
                "extra_notes": [],
                "last_updated": None,
            }
            self._save_profile()

    def _save_profile(self):
        """Save the user profile to disk."""
        self.user_profile["last_updated"] = datetime.now().isoformat()
        with open(self.profile_path, "w", encoding="utf-8") as f:
            json.dump(self.user_profile, f, indent=2, ensure_ascii=False)

    def get_profile(self) -> dict:
        """Get the current user profile."""
        return self.user_profile.copy()

    def update_profile(self, new_profile: dict):
        """Update the user profile with new information."""
        # Merge: keep existing data, add new
        for key, value in new_profile.items():
            if key == "last_updated":
                continue
            if isinstance(value, list):
                # Merge lists, avoid duplicates
                existing = set(self.user_profile.get(key, []) or [])
                new_items = set(value or [])
                self.user_profile[key] = list(existing | new_items)
            elif isinstance(value, dict):
                # Merge dicts
                existing = self.user_profile.get(key, {}) or {}
                existing.update(value or {})
                self.user_profile[key] = existing
            elif value is not None:
                self.user_profile[key] = value

        self._save_profile()

    # ─── Reflections: Alita's Diary ──────────────────────────────

    def save_reflection(self, reflection: str):
        """Save a reflection (diary entry) from Alita."""
        date_str = datetime.now().strftime("%Y-%m-%d")
        time_str = datetime.now().strftime("%H:%M")
        filepath = self.reflections_dir / f"{date_str}.md"

        with open(filepath, "a", encoding="utf-8") as f:
            f.write(f"\n## {time_str}\n{reflection}\n")

        # Also store in vector memory for recall
        self.memory_collection.add(
            documents=[reflection],
            ids=[f"reflection_{datetime.now().strftime('%Y%m%d_%H%M%S')}"],
            metadatas=[{"timestamp": datetime.now().isoformat(), "type": "reflection"}],
        )

    def get_recent_reflections(self, limit: int = 5) -> list[str]:
        """Get recent reflections."""
        reflections = []
        files = sorted(self.reflections_dir.glob("*.md"), reverse=True)
        for f in files[:limit]:
            with open(f, "r", encoding="utf-8") as fp:
                reflections.append(fp.read().strip())
        return reflections

    # ─── Utility ─────────────────────────────────────────────────

    def get_memory_stats(self) -> dict:
        """Get statistics about Alita's memory."""
        return {
            "total_messages": self.get_message_count(),
            "vector_memories": self.memory_collection.count(),
            "profile_filled": sum(1 for v in self.user_profile.values() if v),
            "reflections": len(list(self.reflections_dir.glob("*.md"))),
        }
