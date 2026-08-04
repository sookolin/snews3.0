"""Known Russian city names for relevance filtering.

Used by the ingestion pipeline to detect when a federal/Russia-wide story also
names a *specific* city that is NOT among the monitored cities. Such an item is
about another place and must be dropped, not shown anywhere.
"""

from __future__ import annotations

import functools

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


_NON_CITY_RAW = 'россия рф сибирь урал кавказ крым поволжье донбасс кубань приморье забайкалье волга дон енисей амур байкал кама обь арктика сша китай индия турция германия франция украина европа азия африка америка'


def _non_city_lemmas():
    from shared.services.matcher import _lemma
    return {_lemma(w) for w in _NON_CITY_RAW.split()}


@functools.lru_cache(maxsize=1)
def _cached_non_city():
    return _non_city_lemmas()


def _geox_lemmas(text):
    from shared.services.matcher import _morph, _TOKEN_RE
    analyzer = _morph()
    if analyzer is None:
        return set()
    found = set()
    for tok in _TOKEN_RE.findall(text.lower()):
        if len(tok) < 4:
            continue
        try:
            parses = analyzer.parse(tok)
        except Exception:
            continue
        for pr in parses:
            if 'Geox' in pr.tag:
                found.add(pr.normal_form)
                break
    return found


def mentions_unmonitored_city(title, text, allowed_tokens, region_lemmas=None):
    from shared.services.matcher import _lemma, _lemmatize_tokens
    blob = (title or '') + ' ' + text[:2000]
    region_lemmas = region_lemmas or set()
    geox = _geox_lemmas(blob)
    if geox:
        non_city = _cached_non_city()
        for lemma in geox:
            if lemma in allowed_tokens:
                continue
            if lemma in non_city:
                continue
            if lemma in region_lemmas:
                continue
            return True
        return False
    tokens = _lemmatize_tokens(blob)
    for city in RU_CITY_NAMES:
        for part in city.split():
            lemma = _lemma(part)
            if len(lemma) < 4:
                continue
            if lemma in tokens and lemma not in allowed_tokens:
                return True
        if len(city) < 4:
            lemma = _lemma(city)
            if lemma in tokens and lemma not in allowed_tokens:
                return True
    return False
