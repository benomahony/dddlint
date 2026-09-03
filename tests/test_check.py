from pathlib import Path

import pytest

from dddlint.check import check, is_test_definition, tokenise
from dddlint.config import Config, Context, SynonymGroup
from dddlint.extract import Definition

pytestmark = pytest.mark.unit


TWO_DOMAINS = Config(
    domains=[
        Context(name="billing", include=["**/billing/**"]),
        Context(name="shipping", include=["**/shipping/**"]),
    ]
)


def test_is_test_definition_spots_names_and_paths():
    assert is_test_definition(Definition("test_charge", "Function", Path("a.py"), 1))
    assert is_test_definition(Definition("InvoiceTest", "Class", Path("a.py"), 1))
    assert is_test_definition(Definition("charge", "Function", Path("tests/a.py"), 1))
    assert is_test_definition(Definition("charge", "Function", Path("src/foo_test.go"), 1))
    assert not is_test_definition(Definition("charge", "Function", Path("src/billing/a.py"), 1))


def test_test_domain_drift_flags_a_test_in_the_wrong_domain():
    defs = [
        Definition("Invoice", "Class", Path("src/billing/a.py"), 1),
        Definition("TestInvoice", "Class", Path("src/shipping/test_a.py"), 3),
    ]
    findings = [f for f in check(defs, TWO_DOMAINS) if f.rule == "test-domain-drift"]
    assert len(findings) == 1
    assert "billing" in findings[0].message and "shipping" in findings[0].message
    assert findings[0].name == "TestInvoice"


def test_test_domain_drift_stays_quiet_when_the_test_sits_with_its_subject():
    defs = [
        Definition("Invoice", "Class", Path("src/billing/a.py"), 1),
        Definition("TestInvoice", "Class", Path("src/billing/test_a.py"), 3),
    ]
    assert not any(f.rule == "test-domain-drift" for f in check(defs, TWO_DOMAINS))


def test_test_domain_drift_ignores_unassigned_tests():
    defs = [
        Definition("Invoice", "Class", Path("src/billing/a.py"), 1),
        Definition("TestInvoice", "Class", Path("tests/test_a.py"), 3),
    ]
    assert not any(f.rule == "test-domain-drift" for f in check(defs, TWO_DOMAINS))


def test_test_domain_drift_ignores_an_ambiguous_subject():
    defs = [
        Definition("Invoice", "Class", Path("src/billing/a.py"), 1),
        Definition("Invoice", "Class", Path("src/shipping/b.py"), 1),
        Definition("TestInvoice", "Class", Path("src/shipping/test_a.py"), 3),
    ]
    assert not any(f.rule == "test-domain-drift" for f in check(defs, TWO_DOMAINS))


def test_tokenise_splits_every_case():
    assert tokenise("getUserById") == ("get", "user", "by", "id")
    assert tokenise("get_user_by_id") == ("get", "user", "by", "id")
    assert tokenise("HTTPServer") == ("http", "server")
    assert tokenise("kebab-name") == ("kebab", "name")


def test_forbidden_term():
    config = Config(forbidden=["manager"])
    defs = [Definition("OrderManager", "Class", Path("a.py"), 1)]
    rules = {f.rule for f in check(defs, config)}
    assert "forbidden" in rules


def test_alias_redirects_to_canonical():
    config = Config(synonyms=[SynonymGroup(canonical="customer", aliases=["client"])])
    defs = [Definition("ClientRepository", "Class", Path("a.py"), 1)]
    findings = check(defs, config)
    assert any(f.rule == "alias" and "customer" in f.message for f in findings)


def test_context_scopes_rules():
    config = Config(
        contexts=[Context(name="billing", include=["**/billing/**"], forbidden=["bill"])]
    )
    inside = [Definition("BillService", "Class", Path("src/billing/x.py"), 1)]
    outside = [Definition("BillService", "Class", Path("src/core/x.py"), 1)]
    assert any(f.rule == "forbidden" for f in check(inside, config))
    assert not any(f.rule == "forbidden" for f in check(outside, config))


def test_alias_fix_preserves_casing():
    config = Config(synonyms=[SynonymGroup(canonical="customer", aliases=["client"])])
    upper = check([Definition("CLIENT_REPO", "Class", Path("a.py"), 1)], config)
    lower = check([Definition("client_repo", "Function", Path("a.py"), 1)], config)
    cap = check([Definition("ClientRepo", "Class", Path("a.py"), 1)], config)
    assert any(f.fix == "CUSTOMER_REPO" for f in upper if f.rule == "alias")
    assert any(f.fix == "customer_repo" for f in lower if f.rule == "alias")
    assert any(f.fix == "CustomerRepo" for f in cap if f.rule == "alias")


def test_drift_flags_one_concept_many_spellings():
    config = Config()
    defs = [
        Definition("getUser", "Function", Path("a.py"), 1),
        Definition("get_user", "Function", Path("b.go"), 1),
    ]
    assert any(f.rule == "drift" for f in check(defs, config))


def test_drift_ignores_dunder_names():
    config = Config()
    defs = [
        Definition("__init__", "Function", Path("a.py"), 1),
        Definition("init", "Function", Path("cli.py"), 1),
    ]
    assert not any(f.rule == "drift" for f in check(defs, config))


def test_drift_ignores_case_only_difference_across_kinds():
    config = Config()
    defs = [
        Definition("Entity", "Class", Path("models.py"), 1),
        Definition("entity", "Function", Path("fluent.py"), 1),
    ]
    assert not any(f.rule == "drift" for f in check(defs, config))


def test_drift_flags_case_only_difference_within_one_kind():
    config = Config()
    defs = [
        Definition("Entity", "Class", Path("a.py"), 1),
        Definition("entity", "Class", Path("b.py"), 1),
    ]
    assert any(f.rule == "drift" for f in check(defs, config))


def test_drift_ignores_opposite_directions_around_a_marker():
    defs = [
        Definition("convert_us_to_uk", "Function", Path("a.py"), 1),
        Definition("convert_uk_to_us", "Function", Path("b.py"), 1),
    ]
    assert not any(f.rule == "drift" for f in check(defs, Config()))


def test_drift_flags_reordered_tokens_with_no_direction_between_them():
    defs = [
        Definition("confidence_negative", "Function", Path("a.py"), 1),
        Definition("negative_confidence", "Function", Path("b.py"), 1),
    ]
    assert any(f.rule == "drift" for f in check(defs, Config()))


def test_drift_flags_one_spelling_of_a_direction_repeated():
    defs = [
        Definition("copy_src_to_dst", "Function", Path("a.py"), 1),
        Definition("copySrcToDst", "Function", Path("b.py"), 1),
    ]
    assert any(f.rule == "drift" for f in check(defs, Config()))


def test_directional_markers_are_configurable():
    defs = [
        Definition("convert_us_to_uk", "Function", Path("a.py"), 1),
        Definition("convert_uk_to_us", "Function", Path("b.py"), 1),
    ]
    assert any(f.rule == "drift" for f in check(defs, Config(directional=[])))


def test_forbidden_term_in_a_module_name_reports_its_own_rule():
    defs = [Definition("file_utils", "Module", Path("file_utils.py"), 0)]
    assert [f.rule for f in check(defs, Config(forbidden=["utils"]))] == ["forbidden:module"]


def test_alias_in_a_package_name_offers_no_rename_of_the_source():
    config = Config(synonyms=[SynonymGroup(canonical="customer", aliases=["client"])])
    defs = [Definition("client", "Package", Path("client/__init__.py"), 0)]
    assert [(f.rule, f.fix) for f in check(defs, config)] == [("alias:module", None)]


def test_a_module_neither_duplicates_nor_drifts_against_what_it_holds():
    defs = [
        Definition("file_utils", "Module", Path("file_utils.py"), 0),
        Definition("file_utils", "Function", Path("file_utils.py"), 3),
    ]
    assert not any(f.rule in {"duplicate", "drift"} for f in check(defs, Config()))


def test_duplicate_flags_one_name_on_two_kinds():
    defs = [
        Definition("balance", "Method", Path("a.py"), 3),
        Definition("balance", "Variable", Path("b.py"), 9),
    ]
    findings = [f for f in check(defs, Config()) if f.rule == "duplicate"]
    assert len(findings) == 2
    assert "Variable at b.py:10" in findings[0].message
    assert "Method at a.py:4" in findings[1].message


def test_duplicate_is_opt_out():
    defs = [
        Definition("balance", "Method", Path("a.py"), 3),
        Definition("balance", "Variable", Path("b.py"), 9),
    ]
    assert not any(f.rule == "duplicate" for f in check(defs, Config(name_uniqueness=False)))


def test_duplicate_allows_a_name_owned_by_two_contexts():
    config = Config(
        contexts=[
            Context(name="billing", include=["billing/*"]),
            Context(name="shipping", include=["shipping/*"]),
        ]
    )
    defs = [
        Definition("Invoice", "Class", Path("billing/a.py"), 1),
        Definition("Invoice", "Class", Path("shipping/b.py"), 1),
    ]
    assert not any(f.rule == "duplicate" for f in check(defs, config))


def test_duplicate_ignores_dunder_names():
    defs = [
        Definition("__init__", "Function", Path("a.py"), 1),
        Definition("__init__", "Function", Path("b.py"), 1),
    ]
    assert not any(f.rule == "duplicate" for f in check(defs, Config()))


def test_drift_flags_visibility_only_difference():
    config = Config()
    defs = [
        Definition("_validate_confidence", "Function", Path("a.py"), 1),
        Definition("validate_confidence", "Function", Path("b.py"), 1),
    ]
    assert any(f.rule == "drift" for f in check(defs, config))


def test_exempt_names_produce_no_findings():
    config = Config(exempt=["pytestmark"])
    defs = [
        Definition("pytestmark", "Constant", Path("tests/a.py"), 1),
        Definition("pytestmark", "Constant", Path("tests/b.py"), 1),
    ]
    assert check(defs, config) == []
    # a name not on the list still reports as usual
    assert any(f.rule == "duplicate" for f in check(defs, Config()))
