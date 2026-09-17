"""Retrieval over documents and reportable comments.

With a key: OpenAI embeddings + cosine similarity in numpy, cached on disk.
Without a key: keyword overlap. Either way, comments from team-waves under the reporting
threshold are never indexed, because they are read from v_comments_reportable."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field

import numpy as np

from app import config, llm
from app.db import DB

STOP = set("the a an and or of to in on for is are was were be been with at by from that this it as we our us they them their what why how when where who which do does did not no yes".split())


@dataclass
class Chunk:
    chunk_id: str
    kind: str          # "doc" or "comment"
    title: str
    text: str
    meta: dict = field(default_factory=dict)


def _tokens(s: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", s.lower()) if len(t) > 2 and t not in STOP}


def load_chunks(db: DB) -> list[Chunk]:
    chunks: list[Chunk] = []
    for path in sorted(config.DOCS_DIR.glob("*.md")):
        text = path.read_text()
        title = text.splitlines()[0].lstrip("# ").strip()
        sections = re.split(r"\n(?=## )", text)
        for j, sec in enumerate(sections):
            body = sec.strip()
            if len(body) < 40:
                continue
            sec_title = body.splitlines()[0].lstrip("# ").strip()
            chunks.append(Chunk(chunk_id=f"doc:{path.stem}:{j}", kind="doc", title=f"{title} / {sec_title}",
                                text=body, meta={"doc": path.name, "section": sec_title}))
    rows = db.run_sql("SELECT comment_id, team_id, team_name, site_name, shift, wave_id, text FROM v_comments_reportable").rows
    for r in rows.itertuples():
        chunks.append(Chunk(chunk_id=f"comment:{int(r.comment_id)}", kind="comment",
                            title=f"Comment, {r.site_name} {r.team_name}, wave {int(r.wave_id)}",
                            text=str(r.text),
                            meta={"team_id": int(r.team_id), "team_name": r.team_name, "site_name": r.site_name,
                                  "shift": r.shift, "wave_id": int(r.wave_id)}))
    return chunks


class Retriever:
    def __init__(self, db: DB):
        self.chunks = load_chunks(db)
        self.mode = "keyword"
        self.vectors: np.ndarray | None = None
        if config.has_key():
            try:
                self.vectors = self._embed_all()
                self.mode = "embeddings"
            except llm.LLMUnavailable as e:
                self.mode = f"keyword (embeddings unavailable: {e})"

    def _embed_all(self) -> np.ndarray:
        config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_path = config.CACHE_DIR / f"embeddings_{config.EMBED_MODEL}.json"
        cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
        keys = [hashlib.sha1(c.text.encode()).hexdigest() for c in self.chunks]
        todo = [(k, c.text) for k, c in zip(keys, self.chunks) if k not in cache]
        if todo:
            vecs = llm.embed([t for _, t in todo])
            for (k, _), v in zip(todo, vecs):
                cache[k] = v
            cache_path.write_text(json.dumps(cache))
        m = np.array([cache[k] for k in keys], dtype=float)
        return m / np.linalg.norm(m, axis=1, keepdims=True)

    def search(self, query: str, k: int = 4, kind: str | None = None, filters: dict | None = None) -> list[tuple[Chunk, float]]:
        cands = [(i, c) for i, c in enumerate(self.chunks)
                 if (kind is None or c.kind == kind) and self._match(c, filters or {})]
        if not cands:
            return []
        if self.vectors is not None:
            try:
                q = np.array(llm.embed([query])[0], dtype=float)
                q = q / np.linalg.norm(q)
                scores = [(c, float(self.vectors[i] @ q)) for i, c in cands]
            except llm.LLMUnavailable:
                scores = self._keyword_scores(query, cands)
        else:
            scores = self._keyword_scores(query, cands)
        scores.sort(key=lambda x: -x[1])
        return [s for s in scores[:k] if s[1] > 0]

    @staticmethod
    def _match(c: Chunk, filters: dict) -> bool:
        for key, val in filters.items():
            if val is None:
                continue
            if c.meta.get(key) != val:
                return False
        return True

    @staticmethod
    def _keyword_scores(query: str, cands):
        qt = _tokens(query)
        out = []
        for _, c in cands:
            ct = _tokens(c.text + " " + c.title)
            overlap = len(qt & ct)
            out.append((c, overlap / (len(qt) + 1e-9)))
        return out
