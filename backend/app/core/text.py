"""Lightweight text analysis.

Used in three places where a full model call would be wasteful or too slow:

* **Reflection scoring fallback** — how much of the expert model did the learner
  actually recall, when embeddings are unavailable.
* **SocraticGuard** — lexical leak detection, which runs on every emitted token
  and must be microseconds, not milliseconds.
* **The offline provider** — so the demo path is deterministic and genuinely
  responsive to what the learner wrote, rather than canned.

Deliberately dependency-free: no NLTK, no spaCy. Concept coverage in a tutoring
context is dominated by content-word overlap, and the marginal accuracy of a
parser is not worth a 40MB model download in a hot path.
"""

from __future__ import annotations

import hashlib
import math
import re

_WORD = re.compile(r"[a-z0-9][a-z0-9'+\-]*")

# The tail of this list ("thing", "basically", "really", "maybe") is not a
# standard stopword set. Those are hedges and fillers that dominate how people
# write when they are unsure — exactly the register of a Prior-Belief answer —
# and counting them as content would inflate every coverage score.
STOPWORDS: frozenset[str] = frozenset(
    """
a about above after again against all am an and any are aren't as at be because been before being
below between both but by can cannot could couldn't did didn't do does doesn't doing don't down
during each few for from further had hadn't has hasn't have haven't having he her here hers herself
him himself his how i if in into is isn't it its itself just let's me more most mustn't my myself
no nor not of off on once only or other ought our ours ourselves out over own same shan't she
should shouldn't so some such than that the their theirs them themselves then there these they this
those through to too under until up very was wasn't we were weren't what when where which while who
whom why with won't would wouldn't you your yours yourself yourselves thing things kind sort really
basically actually maybe like get gets got also well much many lot
""".split()  # noqa: SIM905 - a readable block beats a 1300-character list literal
)


def tokens(text: str) -> list[str]:
    return _WORD.findall(text.lower())


def content_words(text: str) -> list[str]:
    return [t for t in tokens(text) if t not in STOPWORDS and len(t) > 2]


def keyphrases(text: str, *, limit: int = 12) -> list[str]:
    """Salient content words, most frequent first, order-stable."""
    counts: dict[str, int] = {}
    order: dict[str, int] = {}
    for index, word in enumerate(content_words(text)):
        counts[word] = counts.get(word, 0) + 1
        order.setdefault(word, index)
    ranked = sorted(counts, key=lambda w: (-counts[w], order[w]))
    return ranked[:limit]


def coverage(reference: str, candidate: str) -> float:
    """Fraction of the reference's key concepts present in the candidate.

    Asymmetric on purpose: we are asking "did they recall the expert model?",
    not "do these two texts resemble each other". A learner who writes twice as
    much as the reference is not penalised, and one who writes a beautiful
    paragraph about something else scores zero.
    """
    ref = set(keyphrases(reference, limit=20))
    if not ref:
        return 0.0
    cand = set(content_words(candidate))
    if not cand:
        return 0.0

    hits = sum(1 for word in ref if word in cand or _stem_hit(word, cand))
    return round(hits / len(ref), 3)


def missing_concepts(reference: str, candidate: str, *, limit: int = 4) -> list[str]:
    """What the learner left out, phrased as *ideas* rather than tokens.

    Returning bare keywords ("maps", "true", "badness") produces feedback that
    reads like a spellchecker and tells a learner nothing about what they
    misunderstood. Each missing key term is instead resolved back to the clause
    in the expert model that carries it, so the omission is legible as a concept.
    """
    cand = set(content_words(candidate))
    absent = [
        word
        for word in keyphrases(reference, limit=20)
        if word not in cand and not _stem_hit(word, cand)
    ]
    if not absent:
        return []

    source = sentences(reference)
    found: list[str] = []
    for word in absent:
        clause = next((s for s in source if word in s.lower()), None)
        if clause is None:
            continue
        phrase = truncate(clause, 90)
        if phrase not in found:
            found.append(phrase)
        if len(found) >= limit:
            break
    return found


def _stem_hit(word: str, candidate: set[str]) -> bool:
    """Crude suffix-tolerant match: 'gradient'/'gradients', 'iterate'/'iterating'."""
    root = word.rstrip("s")
    return any(other.startswith(root[: max(4, len(root) - 2)]) for other in candidate)


def jaccard(a: str, b: str) -> float:
    sa, sb = set(content_words(a)), set(content_words(b))
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def hashed_embedding(text: str, dim: int) -> list[float]:
    """Deterministic bag-of-words embedding for the offline path.

    Not a semantic model — it is a hashed lexical vector. That is enough for the
    offline demo to behave *directionally* like the real thing (similar texts
    score similar), while being reproducible in tests and free.
    """
    vector = [0.0] * dim
    for word in content_words(text) or ["empty"]:
        digest = hashlib.blake2b(word.encode("utf-8"), digest_size=8).digest()
        index = int.from_bytes(digest[:4], "big") % dim
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(v * v for v in vector))
    return [v / norm for v in vector] if norm else vector


def sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def truncate(text: str, limit: int) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


__all__ = [
    "STOPWORDS",
    "content_words",
    "coverage",
    "hashed_embedding",
    "jaccard",
    "keyphrases",
    "missing_concepts",
    "sentences",
    "tokens",
    "truncate",
]
