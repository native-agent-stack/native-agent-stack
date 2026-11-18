# ADR-0003: Multi-Model Peer Bus & Isolated Worktree Convergence

- **Status:** Accepted
- **Date:** 2026-11-18
- **Evidence Grade:** E3

## Context and Problem Statement
Concurrent autonomous agents editing shared repositories collide on working trees unless synchronized by transactional leases and isolated worktrees.

## Decision Outcome
All harnesses coordinate via the shared SQLite WAL peer bus (`sota-bus`), `aannoo/hcom` terminal wakeups, and isolated `git worktree` branches merged via `--ff-only` after passing deterministic gates.
