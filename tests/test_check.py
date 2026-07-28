from pathlib import Path

import pytest

from dddlint.check import check, tokenise
from dddlint.config import Config, Context, SynonymGroup
from dddlint.extract import Definition

pytestmark = pytest.mark.unit


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


def test_drift_flags_visibility_only_difference():
    config = Config()
    defs = [
        Definition("_validate_confidence", "Function", Path("a.py"), 1),
        Definition("validate_confidence", "Function", Path("b.py"), 1),
    ]
    assert any(f.rule == "drift" for f in check(defs, config))
