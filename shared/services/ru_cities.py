"""Known Russian city names for relevance filtering.

Used by the ingestion pipeline to detect when a federal/Russia-wide story also
names a *specific* city that is NOT among the monitored cities. Such an item is
about another place and must be dropped, not shown anywhere.
"""

from __future__ import annotations

#: Major Russian cities (lowercase, nominative). The set is intentionally broad
#: so a story naming an unmonitored city (e.g. «Омск», «Казань») is recognised.
_RAW = ""
# CITIES_START
_RAW += " москва санкт-петербург питер новосибирск екатеринбург казань"
_RAW += " нижний новгород челябинск самара омск ростов-на-дону уфа"
_RAW += " красноярск воронеж пермь волгоград краснодар саратов тюмень"
_RAW += " тольятти ижевск барнаул ульяновск иркутск хабаровск ярославль"
_RAW += " владивосток махачкала томск оренбург кемерово новокузнецк рязань"
_RAW += " астрахань пенза липецк тула киров чебоксары калининград курск"
_RAW += " ставрополь улан-удэ тверь магнитогорск сочи брянск иваново"
_RAW += " белгород сургут владимир нижний тагил архангельск калуга смоленск"
_RAW += " волжский череповец саранск якутск вологда курган орёл орел"
_RAW += " владикавказ мурманск тамбов стерлитамак грозный кострома петрозаводск"
_RAW += " нижневартовск новороссийск йошкар-ола нальчик шахты дзержинск братск"
_RAW += " таганрог комсомольск-на-амуре сыктывкар нижнекамск нефтеюганск"
_RAW += " псков бийск энгельс рыбинск балаково северодвинск армавир"
# CITIES_END
RU_CITY_NAMES: frozenset[str] = frozenset(_RAW.split())


def mentions_unmonitored_city(
    title: str | None, text: str, allowed_tokens: set[str]
) -> bool:
    """True if the text names a known RU city that is NOT in ``allowed_tokens``.

    ``allowed_tokens`` is the lemma set of every monitored city's name/keywords.
    Detection is lemma-based (via the matcher's lemmatiser) so inflected forms
    like «в Омске» are recognised. A federal story that also names a specific
    unmonitored city is about another place and must be dropped.
    """
    from shared.services.matcher import _lemma, _lemmatize_tokens

    blob = f"{title or ''} {text[:2000]}"
    tokens = _lemmatize_tokens(blob)
    for city in RU_CITY_NAMES:
        # Single-token cities: compare lemmas. Multi-word ones (rare) are
        # matched by any of their distinctive tokens.
        for part in city.split():
            lemma = _lemma(part)
            if len(lemma) < 4:
                continue  # skip short, ambiguous tokens (e.g. "уфа" handled below)
            if lemma in tokens and lemma not in allowed_tokens:
                return True
        # Short but distinctive names (уфа, тула, орёл…) — exact lemma check.
        if len(city) < 4:
            lemma = _lemma(city)
            if lemma in tokens and lemma not in allowed_tokens:
                return True
    return False
