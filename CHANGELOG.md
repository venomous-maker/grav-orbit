# Changelog

Every release of grav-orbit, newest first. Each is a `vX.Y.Z` tag with a GitHub
release carrying its section; the `grav` line in `grav.toml` says which
compiler versions it builds with.

## Unreleased

### Fixes

- Database connections that the server dropped while idle (MySQL's `wait_timeout`, a restart, a proxy's idle limit) reconnect on their next use instead of failing with "server has gone away" (grav-db 0.2.1). Uses the new releases of grav-db.

## 0.3.0 (2026-11-25)

Needs grav 1.12.0 or newer.

- `DB.afterCommit(fn)`: work run once the transaction commits, dropped when it
  (or its savepoint) rolls back, run at once outside a transaction.
- Tidied with `grav lint --fix`; three deliberately empty catches say why.

## 0.2.0 (2026-11-20)

### Requirements

- Needs grav 1.9.0 or later, and uses the 0.2.0 releases of the packages it
  depends on.

### Queries

- `iterate(size)` on a query or a model class: its rows as a `for` loop, read
  `size` at a time in id order; a loop that stops early reads no further pages.

## 0.1.1 (2026-11-19)

### Performance

- Loading rows is about 25% cheaper: a field's kind is worked out once instead
  of compared as text on every row, and the dirty-check snapshot no longer reads
  strings and whole numbers back through reflection.
- Model hooks (`saving`, `retrieved`, ...) are dispatched by the `ModelHook`
  enum instead of by name; `TableMap.fire(string, ...)` still works.
- Building a query is about 75% cheaper: behaviors that add no conditions
  (`Behavior.scopes()` false: Timestamps, SoftDeletes, Uuids) no longer cost a
  scratch builder per query, the alias map is made only when needed, and a
  builder looks its quoting connection up once.
- Uses grav-db v0.1.1 (its faster `quote()`).

## 0.1.0 (2026-11-19)

The first tagged release. Needs grav 1.7.0 or newer.

An ORM for [Grav](https://github.com/venomous-maker/grav), in the manner of Laravel's Eloquent: models that save and find themselves, a query builder, relations (polymorphic ones too) with eager loading, soft deletes, timestamps, change tracking, model traits by decorator, a schema builder, migrations, factories and seeders, read replicas, and a query log, debugbar, N+1 detection and query cache for seeing what it sends. It sits on [grav-db](https://github.com/venomous-maker/grav-db), so the same code runs on **SQLite**, **MySQL/MariaDB** and **PostgreSQL**. Values always go to the database as `?` arguments, and the names in a query are checked against the model's fields, so a typo is an error before any SQL runs.
