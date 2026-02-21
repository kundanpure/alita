"""
Memory System for Alita (Neon DB / Postgres version)
Handles all persistent memory: exact chat history, user profile, and vector similarity search.
Completely serverless and ephemeral-safe.
"""

import json
import os
from datetime import datetime
from pathlib import Path

import psycopg2
from psycopg2.extras import Json
from pgvector.psycopg2 import register_vector
from sentence_transformers import SentenceTransformer

from dotenv import load_dotenv

load_dotenv()

# We only keep data_dir for fallback/temp, actual memory is in Postgres
DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)


class MemoryManager:
    """Manages all of Alita's memory connecting to Neon DB."""

    def __init__(self):
        self.db_url = os.getenv("DATABASE_URL")
        if not self.db_url:
            print("❌ WARNING: DATABASE_URL not found! Memory will not be saved.")
            self.conn = None
            return

        print("🔄 Connecting to Neon DB Memory...")
        try:
            self.conn = psycopg2.connect(self.db_url, application_name="Alita_Partner")
            self.conn.autocommit = True
            
            # Setup tables and pgvector
            self._init_db()
            
            # Initialize embedding model for semantic memory
            # all-MiniLM-L6-v2 produces 384-dimensional vectors
            import warnings
            warnings.filterwarnings("ignore", category=FutureWarning)
            self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
            
            # Load profile from remote DB into memory
            self._load_profile()
            print("✅ Neon DB Connected! Memory active.")
        except Exception as e:
            print(f"❌ Neon DB connection failed: {e}")
            self.conn = None

    def _init_db(self):
        """Initialize Postgres tables and extensions."""
        if not self.conn: return
        with self.conn.cursor() as cur:
            # 1. Enable pgvector
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            register_vector(self.conn)

            # 2. Chat History Table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id SERIAL PRIMARY KEY,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                    session_id TEXT,
                    mood TEXT
                );
            """)

            # 3. Vector Memory Table (for semantic search)
            # using vector(384) because all-MiniLM-L6-v2 outputs 384 dimensions
            cur.execute("""
                CREATE TABLE IF NOT EXISTS vector_memories (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    embedding vector(384),
                    type TEXT NOT NULL,
                    timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 4. User Profile Table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_profile (
                    id INT PRIMARY KEY DEFAULT 1,
                    data JSONB NOT NULL
                );
            """)
            
            # 5. Reflections Table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS reflections (
                    id SERIAL PRIMARY KEY,
                    content TEXT NOT NULL,
                    timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                );
            """)

    # ─── Chat History ────────────────────────────────────────────

    def save_message(self, role: str, content: str, session_id: str = None, mood: str = None):
        """Save a message to exactly chat history and semantic search."""
        if not self.conn: return

        # Exact history
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO messages (role, content, session_id, mood) VALUES (%s, %s, %s, %s)",
                (role, content, session_id, mood)
            )

        # Vector memory (only for user stuff to keep Alita focused on learning about the user)
        if role == "user":
            self._store_in_vector_memory(content, "user_message")

    def get_recent_messages(self, limit: int = 20) -> list[dict]:
        """Get recent exact chat messages context."""
        if not self.conn: return []
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT role, content, timestamp FROM messages ORDER BY id DESC LIMIT %s",
                (limit,)
            )
            rows = cur.fetchall()
            
        rows.reverse()
        return [{"role": r[0], "content": r[1], "timestamp": str(r[2])} for r in rows]

    def get_message_count(self) -> int:
        if not self.conn: return 0
        with self.conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM messages")
            return cur.fetchone()[0]

    # ─── Vector Semantic Memory ─────────────────────────────────

    def _store_in_vector_memory(self, text: str, mem_type: str):
        """Store text with its vector embedding in Neon."""
        if not self.conn: return
        try:
            vector = self.embedder.encode(text).tolist()
            doc_id = f"{mem_type}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
            
            with self.conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO vector_memories (id, content, embedding, type) VALUES (%s, %s, %s, %s)",
                    (doc_id, text, vector, mem_type)
                )
        except Exception as e:
            print(f"Vector save error: {e}")

    def recall_memories(self, query: str, n_results: int = 3) -> list[str]:
        """Search via cosine similarity inside Postgres."""
        if not self.conn: return []
        try:
            query_vector = self.embedder.encode(query).tolist()
            
            with self.conn.cursor() as cur:
                # <-> is the Euclidean distance operator in pgvector, which works great
                # <=> is cosine distance which is also excellent for semantic search
                cur.execute("""
                    SELECT content, timestamp 
                    FROM vector_memories 
                    ORDER BY embedding <=> %s::vector 
                    LIMIT %s;
                """, (query_vector, n_results))
                
                rows = cur.fetchall()
                
            memories = []
            for row in rows:
                content, timestamp = row
                try:
                    time_str = timestamp.strftime("%b %d, %Y at %I:%M %p")
                except:
                    time_str = str(timestamp)
                memories.append(f"[{time_str}] {content}")
                
            return memories
        except Exception as e:
            print(f"Memory recall error: {e}")
            return []

    # ─── User Profile ───────────────────────────────────────────

    def _load_profile(self):
        """Load profile from DB."""
        if not self.conn: 
            self._init_empty_profile()
            return
            
        with self.conn.cursor() as cur:
            cur.execute("SELECT data FROM user_profile WHERE id = 1")
            row = cur.fetchone()
            
            if row:
                self.user_profile = row[0]
            else:
                self._init_empty_profile()

    def _init_empty_profile(self):
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
        }
        self._save_profile()

    def _save_profile(self):
        """Save JSON profile to Neon DB."""
        if not self.conn: return
        self.user_profile["last_updated"] = datetime.now().isoformat()
        
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO user_profile (id, data) 
                VALUES (1, %s)
                ON CONFLICT (id) DO UPDATE SET data = EXCLUDED.data;
            """, (Json(self.user_profile),))

    def get_profile(self) -> dict:
        return getattr(self, "user_profile", {}).copy()

    def update_profile(self, new_profile: dict):
        if not hasattr(self, "user_profile"): return
        
        for key, value in new_profile.items():
            if key == "last_updated": continue
            if isinstance(value, list):
                existing = set(self.user_profile.get(key, []) or [])
                new_items = set(value or [])
                self.user_profile[key] = list(existing | new_items)
            elif isinstance(value, dict):
                existing = self.user_profile.get(key, {}) or {}
                existing.update(value or {})
                self.user_profile[key] = existing
            elif value is not None:
                self.user_profile[key] = value

        self._save_profile()

    # ─── Reflections ────────────────────────────────────────────

    def save_reflection(self, reflection: str):
        if not self.conn: return
        
        with self.conn.cursor() as cur:
            cur.execute("INSERT INTO reflections (content) VALUES (%s)", (reflection,))
            
        # Also vector memory
        self._store_in_vector_memory(reflection, "reflection")

    def get_recent_reflections(self, limit: int = 5) -> list[str]:
        if not self.conn: return []
        with self.conn.cursor() as cur:
            cur.execute("SELECT content FROM reflections ORDER BY id DESC LIMIT %s", (limit,))
            rows = cur.fetchall()
            return [r[0] for r in rows]

    def get_memory_stats(self) -> dict:
        if not self.conn: return {}
        with self.conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM messages")
            msg_count = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM vector_memories")
            vec_count = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM reflections")
            ref_count = cur.fetchone()[0]
            
        return {
            "total_messages": msg_count,
            "vector_memories": vec_count,
            "profile_filled": sum(1 for v in self.get_profile().values() if v),
            "reflections": ref_count,
        }
