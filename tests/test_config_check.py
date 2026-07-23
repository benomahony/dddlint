from pathlib import Path

from dddlint.config import Config, Context, SynonymGroup
from dddlint.config_check import check_config

CONFIG_PATH = Path("dddlint.yaml")


def test_domain_rules_apply_to_files():
    from dddlint.check import check
    from dddlint.extract import Definition

    config = Config(domains=[Context(name="commerce", include=["**/*.py"], forbidden=["manager"])])
    defs = [Definition("OrderManager", "Class", Path("src/order.py"), 0)]
    assert any(f.rule == "forbidden" for f in check(defs, config))


def test_context_overrides_domain_alias():
    from dddlint.check import check
    from dddlint.extract import Definition

    config = Config(
        domains=[Context(name="d", include=["**/*.py"], synonyms=[SynonymGroup(canonical="customer", aliases=["client"])])],
        contexts=[Context(name="c", include=["**/*.py"], synonyms=[SynonymGroup(canonical="account", aliases=["client"])])],
    )
    defs = [Definition("ClientService", "Class", Path("src/x.py"), 0)]
    findings = check(defs, config)
    messages = [f.message for f in findings if f.rule == "alias"]
    assert any("account" in m for m in messages)
    assert not any("customer" in m for m in messages)


def test_forbidden_canonical_clash():
    config = Config(
        forbidden=["client"],
        synonyms=[SynonymGroup(canonical="client", aliases=["customer"])],
    )
    findings = check_config(config, CONFIG_PATH)
    assert any(f.rule == "config:forbidden-canonical-clash" for f in findings)


def test_alias_conflict_across_scopes():
    config = Config(
        synonyms=[SynonymGroup(canonical="customer", aliases=["client"])],
        contexts=[Context(name="legacy", include=["**/legacy/**"], synonyms=[SynonymGroup(canonical="account", aliases=["client"])])],
    )
    findings = check_config(config, CONFIG_PATH)
    assert any(f.rule == "config:alias-conflict" and f.name == "client" for f in findings)


def test_duplicate_domain_context_names():
    config = Config(
        domains=[Context(name="billing", include=["**/billing/**"])],
        contexts=[Context(name="billings", include=["**/billings/**"])],
    )
    findings = check_config(config, CONFIG_PATH)
    assert any(f.rule == "config:duplicate-name" for f in findings)


def test_no_false_positives_on_clean_config():
    config = Config(
        synonyms=[SynonymGroup(canonical="customer", aliases=["client"])],
        domains=[Context(name="commerce", include=["**/commerce/**"])],
        contexts=[Context(name="billing", include=["**/billing/**"])],
    )
    assert check_config(config, CONFIG_PATH) == []
