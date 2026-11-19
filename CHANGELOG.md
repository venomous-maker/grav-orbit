# Changelog

Every release of grav-orbit, newest first. Each is a `vX.Y.Z` tag with a GitHub
release carrying its section; the `grav` line in `grav.toml` says which
compiler versions it builds with.

## Unreleased

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

## 0.1.0 (2026-11-19)

The first tagged release. Needs grav 1.7.0 or newer.

An ORM for [Grav](https://github.com/venomous-maker/grav), in the manner of Laravel's Eloquent: models that save and find themselves, a query builder, relations (polymorphic ones too) with eager loading, soft deletes, timestamps, change tracking, model traits by decorator, a schema builder, migrations, factories and seeders, read replicas, and a query log, debugbar, N+1 detection and query cache for seeing what it sends. It sits on [grav-db](https://github.com/venomous-maker/grav-db), so the same code runs on **SQLite**, **MySQL/MariaDB** and **PostgreSQL**. Values always go to the database as `?` arguments, and the names in a query are checked against the model's fields, so a typo is an error before any SQL runs.
