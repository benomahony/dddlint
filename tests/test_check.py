from pathlib import Path

from dddlint.check import check, tokenise
from dddlint.config import Config, Context, SynonymGroup
from dddlint.extract import Definition


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


def test_drift_flags_one_concept_many_spellings():
    config = Config()
    defs = [
        Definition("getUser", "Function", Path("a.py"), 1),
        Definition("get_user", "Function", Path("b.go"), 1),
    ]
    assert any(f.rule == "drift" for f in check(defs, config))
