#!/usr/bin/env python3
"""
Hybrid Semantic + Lexical Memory Indexer for organize-bookmarks.

Provides fast, 100% local, zero-dependency indexing and search across project memory
files, rules, maintenance guides, and session history using:
1. SQLite FTS5 (BM25 full-text ranking with Porter stemming)
2. Deterministic Local Feature-Hashed Subword, Bigram & Character N-Gram Embeddings (384-dim)
3. Hybrid Cosine Similarity + FTS5 BM25 Rank Fusion.
"""

import hashlib
import json
import math
import os
import re
import sqlite3
import time
from typing import Dict, List, Tuple

MEMORY_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_ROOT = os.path.abspath(os.path.join(MEMORY_DIR, "..", ".."))
DB_PATH = os.path.join(MEMORY_DIR, "memory_index.sqlite")

LOCAL_DIM = 384  # Dimension for deterministic local feature-hashed embeddings
LOCAL_PROVIDER = f"local:feature-hash-{LOCAL_DIM}d"

DEFAULT_INDEXED_FILES = [
    "AGENTS.md",
    "MAINTENANCE.md",
    "ai_agent_server/MAINTENANCE.md",
    ".agents/memory/project_memory.md",
    ".agents/memory/session_state.json",
    ".agents/skills/bookmark-lookup/SKILL.md",
]


class EmbeddingProvider:
    """
    Deterministic Local Subword/Bigram/Char-Ngram Feature-Hashed Vector Engine (384-dim, zero network calls).
    """

    @classmethod
    def embed_local_deterministic(cls, text: str, dim: int = LOCAL_DIM) -> List[float]:
        """
        Compute a 384-dimensional L2-normalized semantic feature vector using
        Signed Random Projection (Weinberger et al. feature hashing) over:
        - Lowercased word unigrams (weight 2.0) and sub-tokens (weight 1.6)
        - Word bigrams (weight 2.5)
        - Character 3-grams and 4-grams within words (weight 0.8, captures morphology/typos)
        """
        vec = [0.0] * dim
        clean = re.sub(r"[^a-z0-9_\-/\.]+", " ", text.lower())
        tokens = [t for t in clean.split() if len(t) >= 2]
        if not tokens:
            return vec

        features: List[Tuple[str, float]] = []
        # 1. Word unigrams & sub-tokens (split on - _ / .)
        expanded_tokens: List[str] = []
        for tok in tokens:
            features.append((f"w:{tok}", 2.0))
            parts = [p for p in re.split(r"[-_/\.]", tok) if len(p) >= 2]
            for p in parts:
                expanded_tokens.append(p)
                if p != tok:
                    features.append((f"sub:{p}", 1.6))

        # 2. Word bigrams
        for i in range(len(expanded_tokens) - 1):
            features.append((f"bi:{expanded_tokens[i]}_{expanded_tokens[i+1]}", 2.5))

        # 3. Character n-grams (3 and 4) for morphological & prefix/suffix similarity
        for tok in set(expanded_tokens):
            padded = f"<{tok}>"
            for n in (3, 4):
                for i in range(max(0, len(padded) - n + 1)):
                    features.append((f"c{n}:{padded[i:i+n]}", 0.8))

        for feat, weight in features:
            h = int(hashlib.md5(feat.encode("utf-8")).hexdigest()[:16], 16)
            idx = h % dim
            sign = 1.0 if ((h >> 16) & 1) == 0 else -1.0
            vec[idx] += sign * weight

        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [round(v / norm, 6) for v in vec]
        return vec

    @classmethod
    def embed(cls, text: str) -> Tuple[List[float], str]:
        """Returns (embedding_vector, provider_name)."""
        return cls.embed_local_deterministic(text), LOCAL_PROVIDER


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    return max(0.0, min(1.0, dot))


def chunk_markdown(rel_path: str, content: str) -> List[Dict[str, str]]:
    """Splits a Markdown file into semantic sections by headings."""
    lines = content.splitlines()
    chunks: List[Dict[str, str]] = []
    cur_title = os.path.basename(rel_path)
    cur_lines: List[str] = []
    start_line = 1

    def flush(end_line: int):
        body = "\n".join(cur_lines).strip()
        if len(body) >= 25:
            chunks.append(
                {
                    "source_file": rel_path,
                    "section_title": cur_title,
                    "line_range": f"L{start_line}-L{end_line}",
                    "content": body,
                }
            )

    for idx, line in enumerate(lines, 1):
        m = re.match(r"^(#{1,3})\s+(.+)$", line)
        if m:
            flush(idx - 1)
            cur_title = m.group(2).strip()
            cur_lines = [line]
            start_line = idx
        else:
            cur_lines.append(line)
    flush(len(lines))
    return chunks


def chunk_session_json(rel_path: str, content: str) -> List[Dict[str, str]]:
    """Converts session_state.json into searchable memory chunks."""
    try:
        data = json.loads(content)
    except Exception:
        return []
    chunks = []
    goal = data.get("active_goal", "")
    done = data.get("completed_steps", [])
    pending = data.get("pending_steps", [])
    notes = data.get("working_notes", [])

    summary_text = f"Active Session Goal: {goal}\n"
    if done:
        summary_text += "Completed Steps:\n- " + "\n- ".join(done) + "\n"
    if pending:
        summary_text += "Pending Steps:\n- " + "\n- ".join(pending) + "\n"
    chunks.append(
        {
            "source_file": rel_path,
            "section_title": "Active Session State & Steps",
            "line_range": "L1-L20",
            "content": summary_text.strip(),
        }
    )
    if notes:
        notes_text = "Session Working Notes:\n- " + "\n- ".join(notes)
        chunks.append(
            {
                "source_file": rel_path,
                "section_title": "Session Working Notes",
                "line_range": "L15-L35",
                "content": notes_text.strip(),
            }
        )
    return chunks


class MemoryVectorStore:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with self._connect() as con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_chunks (
                    chunk_id TEXT PRIMARY KEY,
                    source_file TEXT NOT NULL,
                    section_title TEXT NOT NULL,
                    line_range TEXT NOT NULL,
                    content TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    embedding_json TEXT NOT NULL,
                    embedding_provider TEXT NOT NULL,
                    updated_at REAL NOT NULL
                )
                """
            )
            con.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
                    chunk_id UNINDEXED,
                    source_file,
                    section_title,
                    content,
                    tokenize='porter unicode61'
                )
                """
            )
            con.commit()

    def index_all(self, force: bool = False) -> Dict[str, int]:
        stats = {
            "files": 0,
            "chunks_total": 0,
            "chunks_embedded": 0,
            "chunks_cached": 0,
            "provider": LOCAL_PROVIDER,
        }
        all_chunks: List[Dict[str, str]] = []

        for rel_path in DEFAULT_INDEXED_FILES:
            abs_path = os.path.join(WORKSPACE_ROOT, rel_path)
            if not os.path.exists(abs_path):
                continue
            stats["files"] += 1
            with open(abs_path, "r", encoding="utf-8") as f:
                raw = f.read()
            if rel_path.endswith(".json"):
                all_chunks.extend(chunk_session_json(rel_path, raw))
            else:
                all_chunks.extend(chunk_markdown(rel_path, raw))

        migrated_provider = False
        with self._connect() as con:
            existing = {
                row[0]: (row[1], row[2])
                for row in con.execute(
                    "SELECT chunk_id, content_hash, embedding_provider FROM memory_chunks"
                )
            }
            seen_ids = set()

            for c in all_chunks:
                stats["chunks_total"] += 1
                cid = hashlib.sha1(
                    f"{c['source_file']}::{c['section_title']}::{c['line_range']}".encode("utf-8")
                ).hexdigest()[:16]
                seen_ids.add(cid)
                chash = hashlib.sha1(c["content"].encode("utf-8")).hexdigest()[:16]

                if (
                    not force
                    and cid in existing
                    and existing[cid][0] == chash
                    and existing[cid][1] == LOCAL_PROVIDER
                ):
                    stats["chunks_cached"] += 1
                    continue

                if cid in existing and existing[cid][1] != LOCAL_PROVIDER:
                    migrated_provider = True

                embed_input = f"{c['section_title']}\n{c['content']}"
                vec, provider = EmbeddingProvider.embed(embed_input)
                stats["provider"] = provider
                stats["chunks_embedded"] += 1

                con.execute(
                    """
                    INSERT OR REPLACE INTO memory_chunks
                    (chunk_id, source_file, section_title, line_range, content, content_hash, embedding_json, embedding_provider, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        cid,
                        c["source_file"],
                        c["section_title"],
                        c["line_range"],
                        c["content"],
                        chash,
                        json.dumps(vec),
                        provider,
                        time.time(),
                    ),
                )
                con.execute("DELETE FROM memory_fts WHERE chunk_id = ?", (cid,))
                con.execute(
                    """
                    INSERT INTO memory_fts (chunk_id, source_file, section_title, content)
                    VALUES (?, ?, ?, ?)
                    """,
                    (cid, c["source_file"], c["section_title"], c["content"]),
                )

            # Prune deleted chunks
            pruned = set(existing.keys()) - seen_ids
            for old_id in pruned:
                con.execute("DELETE FROM memory_chunks WHERE chunk_id = ?", (old_id,))
                con.execute("DELETE FROM memory_fts WHERE chunk_id = ?", (old_id,))

            con.commit()
            if migrated_provider or pruned:
                con.execute("VACUUM")
        return stats

    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        # Ensure index is fresh lazily at search time
        self.index_all(force=False)

        with self._connect() as con:
            rows = con.execute(
                """
                SELECT chunk_id, source_file, section_title, line_range, content, embedding_json, embedding_provider
                FROM memory_chunks
                """
            ).fetchall()

            if not rows:
                return []

            q_vec = EmbeddingProvider.embed_local_deterministic(query)

            # 1. FTS5 BM25 lexical search
            fts_tokens = [
                re.sub(r"[^a-zA-Z0-9_]", "", t)
                for t in query.split()
                if len(re.sub(r"[^a-zA-Z0-9_]", "", t)) >= 2
            ]
            fts_ranks: Dict[str, float] = {}
            if fts_tokens:
                fts_query = " OR ".join(f'"{t}"*' for t in fts_tokens)
                try:
                    fts_rows = con.execute(
                        """
                        SELECT chunk_id, bm25(memory_fts, 1.0, 2.5, 1.0) AS score
                        FROM memory_fts
                        WHERE memory_fts MATCH ?
                        ORDER BY score
                        LIMIT 20
                        """,
                        (fts_query,),
                    ).fetchall()
                    for rank_idx, (cid, bm25_raw) in enumerate(fts_rows):
                        fts_ranks[cid] = 1.0 / (rank_idx + 1) + min(1.0, abs(bm25_raw) / 15.0)
                except Exception:
                    pass

            # 2. Vector Cosine Similarity + Hybrid Fusion
            scored_results = []
            for cid, sfile, stitle, lrange, content, emb_json, provider in rows:
                c_vec = json.loads(emb_json)
                if len(c_vec) != len(q_vec):
                    c_vec = EmbeddingProvider.embed_local_deterministic(f"{stitle}\n{content}")
                cos_sim = cosine_similarity(q_vec, c_vec)
                lex_score = fts_ranks.get(cid, 0.0)

                # Hybrid score: 55% Vector Similarity + 45% FTS5 BM25 Rank
                hybrid_score = (0.55 * cos_sim) + (0.45 * (lex_score / 2.0))
                scored_results.append(
                    {
                        "chunk_id": cid,
                        "source_file": sfile,
                        "section_title": stitle,
                        "line_range": lrange,
                        "content": content,
                        "hybrid_score": round(hybrid_score, 4),
                        "vector_sim": round(cos_sim, 4),
                        "fts_score": round(lex_score, 4),
                        "provider": provider,
                    }
                )

            scored_results.sort(key=lambda x: x["hybrid_score"], reverse=True)
            return scored_results[:top_k]

    def get_index_stats(self) -> Dict:
        if not os.path.exists(self.db_path):
            return {"indexed": False, "chunks": 0}
        with self._connect() as con:
            count = con.execute("SELECT COUNT(*) FROM memory_chunks").fetchone()[0]
            providers = [
                r[0]
                for r in con.execute(
                    "SELECT DISTINCT embedding_provider FROM memory_chunks"
                ).fetchall()
            ]
            files = [
                r[0]
                for r in con.execute(
                    "SELECT DISTINCT source_file FROM memory_chunks"
                ).fetchall()
            ]
        return {
            "indexed": True,
            "db_size_bytes": os.path.getsize(self.db_path),
            "chunks": count,
            "providers": providers,
            "files": files,
        }
