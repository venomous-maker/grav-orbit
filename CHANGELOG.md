# Changelog

Every release of grav-orbit, newest first. Each is a `vX.Y.Z` tag with a GitHub
release carrying its section; the `grav` line in `grav.toml` says which
compiler versions it builds with.

## Unreleased

## 0.1.0 (2026-11-19)

The first tagged release. Needs grav 1.7.0 or newer.

An ORM for [Grav](https://github.com/venomous-maker/grav), in the manner of Laravel's Eloquent: models that save and find themselves, a query builder, relations (polymorphic ones too) with eager loading, soft deletes, timestamps, change tracking, model traits by decorator, a schema builder, migrations, factories and seeders, read replicas, and a query log, debugbar, N+1 detection and query cache for seeing what it sends. It sits on [grav-db](https://github.com/venomous-maker/grav-db), so the same code runs on **SQLite**, **MySQL/MariaDB** and **PostgreSQL**. Values always go to the database as `?` arguments, and the names in a query are checked against the model's fields, so a typo is an error before any SQL runs.
