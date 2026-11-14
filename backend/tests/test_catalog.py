"""Invariantes do catálogo de indicadores: mantêm honesta a agregação e a procedência (regras 1, 6 e 7)."""

from collections import Counter

from app.indicators import (
    _INDICATORS,
    AGG_POP_MEAN,
    AGG_SUM,
    CATEGORIES,
    INDICATORS,
    WB_INDICATORS,
)

# Unidades que são razões, índices ou percentuais de algo que não é a população: somá-las
# (ou tirar média ponderada pela população) entre países daria um número enganoso.
NOT_ADDITIVE_HINTS = (
    "%", "índice", "escore", "0 a", "= 100", "moeda local",
    "por 100", "por 1.000", "por milhão", "por pessoa", "por hab", "por hectare", "mm por", "m³", "MJ por",
)


def test_slugs_and_world_bank_codes_are_unique():
    slugs = Counter(i.slug for i in _INDICATORS)
    codes = Counter(i.wb_code for i in _INDICATORS if i.wb_code)
    assert [s for s, n in slugs.items() if n > 1] == []
    assert [c for c, n in codes.items() if n > 1] == []
    assert len(INDICATORS) == len(_INDICATORS)
    assert WB_INDICATORS == {i.slug: i.wb_code for i in _INDICATORS if i.wb_code}


def test_every_indicator_has_a_known_category_and_text():
    categories = {c.id for c in CATEGORIES}
    for item in _INDICATORS:
        assert item.category in categories, item.slug
        assert item.name.strip() and item.unit.strip() and item.description.strip(), item.slug
        assert item.source.strip() and item.source_url.startswith("https://"), item.slug


def test_world_bank_indicators_cite_their_code_and_have_country_data():
    for item in _INDICATORS:
        if not item.wb_code:
            continue
        assert item.per_country, item.slug
        assert item.wb_code in item.description, item.slug
        assert item.source_url.endswith(item.wb_code), item.slug
        assert item.source.startswith("Banco Mundial"), item.slug


def test_sums_are_only_for_absolute_quantities():
    for item in _INDICATORS:
        if item.agg == AGG_SUM:
            assert not any(hint in item.unit for hint in NOT_ADDITIVE_HINTS), f"{item.slug} ({item.unit}) não é aditivo"


def test_population_mean_is_never_used_for_shares_of_gdp_or_indexes():
    for item in _INDICATORS:
        if item.agg == AGG_POP_MEAN:
            assert "do PIB" not in item.unit and "índice" not in item.unit.lower(), item.slug


def test_catalog_grew_beyond_the_first_release():
    # 75 indicadores no primeiro lançamento; a ampliação com o arquivo em massa do Banco Mundial os supera.
    assert len(INDICATORS) > 200
    per_category = Counter(i.category for i in _INDICATORS)
    assert all(per_category[c] >= 10 for c in per_category)
