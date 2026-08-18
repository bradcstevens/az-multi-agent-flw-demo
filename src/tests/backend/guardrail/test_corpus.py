"""Invariants of the Guardrail corpus (issue #13).

The corpus is 10 positive probes that must be refused and 10 negative controls
that must be admitted, plus the personal-intent anchors the similarity tier
scores against. Its numeric verdict needs the real embedding deployment and
lives in the integration suite; what is checkable without Azure is that the
corpus is actually *hard* — that it would defeat a keyword list, which is the
whole reason ADR-014 adds an embedding tier at all.
"""

import re

from guardrail.corpus import (
    NEGATIVE_CONTROLS,
    PERSONAL_INTENT_ANCHORS,
    POSITIVE_PROBES,
    STORE_SCOPE_ANCHORS,
)

FIRST_PERSON = re.compile(r"\b(i|i'm|im|me|my|mine|myself)\b", re.IGNORECASE)

STOPWORDS = {
    "a", "am", "an", "and", "any", "are", "at", "be", "can", "did", "do", "does",
    "for", "get", "got", "has", "have", "how", "i", "if", "in", "is", "it", "its",
    "last", "me", "much", "my", "of", "on", "or", "out", "pull", "right", "s",
    "should", "show", "that", "the", "there", "this", "to", "up", "was", "what",
    "whats", "when", "where", "which", "who", "will", "with", "you", "your",
}


def content_words(text):
    words = re.findall(r"[a-z0-9']+", text.lower())
    return {word for word in words if word not in STOPWORDS}


def normalised(text):
    return re.sub(r"[^a-z0-9 ]", "", text.lower()).strip()


class TestCorpusShape:
    def test_ten_positive_probes(self):
        assert len(POSITIVE_PROBES) == 10

    def test_eleven_negative_controls(self):
        # Ten store-level controls, plus the **HR process question** the fourth
        # specialist answers (#52, ADR-017). R5's criterion was written as
        # 0/10; the eleventh only makes it stricter, and leaving the beat's own
        # question out of the corpus would leave the one tier that could refuse
        # it live — the similarity tier — unmeasured against it.
        assert len(NEGATIVE_CONTROLS) == 11

    def test_every_probe_is_distinct(self):
        everything = list(POSITIVE_PROBES) + list(NEGATIVE_CONTROLS)
        assert len({normalised(text) for text in everything}) == len(everything)

    def test_the_anchors_are_disjoint_from_the_probes(self):
        # A probe that is also an anchor scores 1.0 against itself and proves
        # nothing, so the corpus would flatter the threshold it is tuning.
        anchors = {normalised(text) for text in PERSONAL_INTENT_ANCHORS}
        probes = {normalised(text) for text in POSITIVE_PROBES}
        assert anchors.isdisjoint(probes)

    def test_there_are_anchors_to_score_against(self):
        assert len(PERSONAL_INTENT_ANCHORS) >= 8

    def test_both_anchor_sets_exist_because_scoring_is_two_class(self):
        # Personal similarity alone does not separate the corpus; the margin
        # against store-scope anchors is what does.
        assert len(STORE_SCOPE_ANCHORS) >= 8

    def test_store_anchors_cover_the_shift_swap_process(self):
        # The Workforce beat is deliberately near personal shift language, so
        # the counterweight must represent its between-associate procedure.
        assert any(
            "shift" in text.lower()
            and "swap" in text.lower()
            and "associate" in text.lower()
            for text in STORE_SCOPE_ANCHORS
        )

    def test_the_store_anchors_are_disjoint_from_the_negative_controls(self):
        # A control that is also an anchor scores 1.0 on the store side and
        # would flatter the margin the corpus is tuning.
        anchors = {normalised(text) for text in STORE_SCOPE_ANCHORS}
        controls = {normalised(text) for text in NEGATIVE_CONTROLS}
        assert anchors.isdisjoint(controls)

    def test_the_two_anchor_sets_are_disjoint_from_each_other(self):
        personal = {normalised(text) for text in PERSONAL_INTENT_ANCHORS}
        store = {normalised(text) for text in STORE_SCOPE_ANCHORS}
        assert personal.isdisjoint(store)


class TestCorpusIsHarderThanAKeywordList:
    def test_several_positives_carry_no_first_person_pronoun(self):
        # The obvious keyword fast-path is first-person pronouns. If every
        # positive carried one, the similarity tier would never be exercised.
        pronounless = [text for text in POSITIVE_PROBES if not FIRST_PERSON.search(text)]
        assert len(pronounless) >= 3

    def test_a_pronoun_keyword_list_would_falsely_refuse_store_questions(self):
        # "How do I close the store?" is first-person and entirely store-level:
        # pronouns alone would blow R5's 0/10 false-positive criterion.
        pronouned = [text for text in NEGATIVE_CONTROLS if FIRST_PERSON.search(text)]
        assert len(pronouned) >= 5

    def test_no_five_content_words_catch_every_positive(self):
        # A keyword list is a handful of words. Take the five that cover the
        # most positives and they must still miss at least one.
        vocabulary = {word for text in POSITIVE_PROBES for word in content_words(text)}
        coverage = {
            word: {
                index
                for index, text in enumerate(POSITIVE_PROBES)
                if word in content_words(text)
            }
            for word in vocabulary
        }

        caught = set()
        remaining = dict(coverage)
        for _ in range(5):
            if not remaining:
                break
            best = max(remaining, key=lambda word: len(remaining[word] - caught))
            caught |= remaining.pop(best)

        assert len(caught) < len(POSITIVE_PROBES)

    def test_the_negative_controls_reach_beyond_one_topic(self):
        # Ten paraphrases of "how do I close the store" would make 0/10 false
        # positives cheap. The controls have to spread across store work.
        vocabulary = {word for text in NEGATIVE_CONTROLS for word in content_words(text)}
        assert len(vocabulary) >= 40
