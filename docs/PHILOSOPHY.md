# Aiambler Philosophy

Aiambler is not a general-purpose application language. It is a token-min
execution language for LLM agents.

The model should think in natural language, choose a small set of primitives,
and emit a compact executable plan. The runtime should do the mechanical work
that must be exact:

- read real files and text;
- filter and parse;
- extract numbers;
- aggregate;
- transform text;
- write logs, console output, and files.

This keeps the LLM away from pretending to calculate from weights. It can reason
about the task, but arithmetic and parsing are delegated to a native executable.

## Why Not Python For Every Task

Python is easy for models because training data is abundant. For small local
agent tasks, it is often expensive anyway:

- many tokens for imports, loops, parsing, and boilerplate;
- process startup overhead;
- optional virtual environment setup;
- dependency ambiguity;
- more surface area for mistakes.

Aiambler aims at the common middle ground: tasks too exact for pure model
reasoning, but too small to justify full Python code.

## Product Boundary

Aiambler should be good at:

- text and log analysis;
- CSV/TSV field extraction;
- simple numeric reductions;
- find/replace and normalization;
- small reports;
- safe local IO;
- short verifiable steps inside agent workflows.

Aiambler should not try to be:

- a full application language;
- a UI framework;
- a replacement for Python libraries;
- a complex object-oriented runtime;
- a hidden shell with unrestricted side effects.

## Design Rules

1. Every compact form must normalize to a clear IR operation.
2. Token-min syntax must be measured, not guessed from character count.
3. Readable aliases are allowed for prompting and debugging.
4. Common tasks deserve built-in one-step primitives.
5. Runtime results must be checkable against Python/AWK baselines.
6. Safety and access mode must be explicit for write/network/system operations.

## Core Contract

```text
LLM: understand the request, choose primitives, explain the result.
Aiambler: execute parsing, math, aggregation, and IO exactly.
```

