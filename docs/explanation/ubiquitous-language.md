---
icon: lucide/lightbulb
---

# Ubiquitous language

## The problem

In domain-driven design, a **ubiquitous language** is the vocabulary shared by
everyone working *within a single bounded context* — in conversation, in
documentation, and in the code. Inside that boundary the term is precise and
non-negotiable: when the domain expert says "order", the code says `order`. Not
`purchase`, not `transaction`, not `Order` in one module and `PurchaseDto` in
another.

The language is ubiquitous *within* its context, not across the whole system. A
real system has several bounded contexts, each with its own language, and the
same word can legitimately mean different things in each — a "shipment" in
fulfilment is not a "shipment" in billing. Forcing one vocabulary over every
context is the mistake the boundary exists to prevent; translation belongs at
the boundary between contexts, not inside them.

Language drifts within a context anyway. A new engineer calls it a `client`; the
original code calls it a `customer`. A refactor introduces an `OrderManager`
next to the existing `OrderService`. Each choice is locally reasonable, but the
context now speaks three dialects and every reader pays a translation tax.

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

Rules live at three scopes, so one config can hold several languages at once:
global rules everyone agrees on, `domains` for a broad subject area, and
`contexts` for a bounded context's own vocabulary — path-scoped and applied
last, so a context can override a term the surrounding domain made canonical.
See [Scope rules to domains and contexts](../how-to/domains-contexts.md).

## The language evolves — findings are a prompt, not a verdict

A ubiquitous language is a model of the domain, and the domain keeps moving.
Terms are refined, split, or retired as the team's understanding improves, so a
vocabulary that never changes is not stable — it is stale.

That makes a finding a question with two valid answers. Either the name is wrong
and the code should be renamed, or the name is right and `dddlint.yaml` is
behind. Someone straining the vocabulary — reaching for a word the config
forbids, or reusing a canonical term for a concept it does not quite fit — is
usually not being sloppy. They are the first person to hit a gap in the model,
and repeated strain on the same term is the strongest signal you get that the
language needs a new word, a split into two, or a new bounded context to hold
the second meaning.

So resolve findings deliberately. Renaming a name to silence the linter when the
domain has genuinely moved on encodes the old model deeper. Because the config
lives in version control next to the code, updating it is an ordinary reviewable
commit — the same diff that changes the vocabulary records who changed it and
why.

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
red build: use the agreed word, then continue.

An agent should not edit the vocabulary to make its own code pass — that is the
one resolution reserved for a human who understands why the domain moved. When
an agent keeps colliding with the same term, treat the collision as a report to
read, not a rule to relax.

## Further reading

- [How checking works](how-checking-works.md) — the mechanics behind the rules.
- [Rules reference](../reference/rules.md) — each finding, precisely.
