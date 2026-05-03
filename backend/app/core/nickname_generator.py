import random

from app.models.nickname_word import NicknameWord

_FALLBACK_ADJ = ["勇敢な", "謎の", "伝説の", "小さな", "巨大な"]
_FALLBACK_NOUN = ["戦士", "魔法使い", "盗賊", "僧侶", "賢者"]


def generate(words: list[NicknameWord]) -> str:
    by_part: dict[str, list[str]] = {}
    for w in words:
        by_part.setdefault(w.part, []).append(w.word)

    adjs = by_part.get("adj") or _FALLBACK_ADJ
    nouns = by_part.get("noun") or _FALLBACK_NOUN
    return random.choice(adjs) + random.choice(nouns)
