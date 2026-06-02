---
tags: [decision, demo]
status: active
date: 2026-01-01
repo: demo
---

## TL;DR

Use Postgres for the primary store. pgvector + JSON tipped it. Rejected: Mongo (weak joins).

## Why

We need relational integrity and vector search in one engine.

## How

Postgres 16 + pgvector. Drizzle migrations.

## Outcome

Single store for relational + vector workloads.
