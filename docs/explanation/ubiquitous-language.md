---
icon: lucide/lightbulb
---

# Ubiquitous language

## The problem

In domain-driven design, a **ubiquitous language** is a single, shared
vocabulary used by everyone on a project — in conversation, in documentation,
and in the code. When the domain expert says "order", the code says `order`.
Not `purchase`, not `transaction`, not `Order` in one module and `PurchaseDto`
in another.

Language drifts anyway. A new engineer calls it a `client`; the original code
calls it a `customer`. A refactor introduces an `OrderManager` next to the
existing `OrderService`. Each choice is locally reasonable, but the codebase now
speaks three dialects and every reader pays a translation tax.

Linters catch style. Type checkers catch types. Neither catches a codebase
slowly forgetting its own words.

## What dddlint enforces

dddlint makes the ubiquitous language an executable artifact. You write the
vocabulary down in `dddlint.yaml`, and it holds the code to it:

- **Forbidden terms** — words the domain has decided are meaningless noise
  (`util`, `helper`, `manager`) and should never name a concept.
- **Canonical terms and aliases** — when several words mean the same thing, one
  is canonical and the rest are aliases that should be renamed.
- **Drift** — even without a rule, the same concept spelled several ways is
  worth surfacing.

## Why names, not comments or docstrings

Names are the part of the code every reader sees and cannot skip. A stale
comment misleads; a misnamed class misleads *and* propagates — every call site
repeats the wrong word. Enforcing the vocabulary at the level of definition
names is the highest-leverage place to keep a codebase honest.

## Why polyglot matters

A bounded context rarely lives in one language. The API is TypeScript, the
service is Go, the data job is Python, the contract is Protobuf. If the language
linter only understood one of them, drift would just move to the languages it
could not see. dddlint checks names across every language tree-sitter
recognises, so the vocabulary is enforced end to end.

## Why it targets coding agents too

An autonomous coding agent generates plausible names at speed. "Plausible" is
exactly the failure mode a ubiquitous language guards against — the agent has no
memory of the term the team agreed on last quarter. A non-zero exit code on a
naming violation gives the agent's loop the same feedback a human gets from a
red build: fix the word, then continue.

## Further reading

- [How checking works](how-checking-works.md) — the mechanics behind the rules.
- [Rules reference](../reference/rules.md) — each finding, precisely.
