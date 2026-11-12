# Orbit against Eloquent and SQLAlchemy

The same work, written idiomatically in each ORM, on the same tables and the
same databases: [`orbit_bench.grav`](orbit_bench.grav),
[`eloquent_bench.php`](eloquent_bench.php) (Laravel's Eloquent, standalone) and
[`sqlalchemy_bench.py`](sqlalchemy_bench.py) (SQLAlchemy 2.0's ORM).

## Summary

| | SQLite | PostgreSQL | MariaDB | client CPU | peak memory |
|---|---:|---:|---:|---:|---:|
| **Orbit** (`--release`) | **2.3 s** | **5.6 s** | **14.9 s** | **2.0–2.6 s** | **41–45 MB** |
| Eloquent 13, PHP 8.5 with JIT | 6.1 s | 13.6 s | 25.6 s | 6.2–9.4 s | 84–87 MB |
| SQLAlchemy 2.0, Python 3.13 | 10.4 s | 20.3 s | 33.0 s | 10.9–13.8 s | 71–74 MB |

In total time Orbit is 2.4–2.6× as fast as Eloquent and 3.6–4.5× as fast as
SQLAlchemy on SQLite and PostgreSQL. On MariaDB, where the server's own time
dominates (compare the CPU column), it is 1.7× and 2.2×. It uses about a third
of Eloquent's CPU and a fifth of SQLAlchemy's, and half of Eloquent's memory
(60% of SQLAlchemy's).

Its biggest leads are where the ORM's own work counts most:
- creating models one by one: 3–15× Eloquent
- finding by id: 2–4× Eloquent
- eager loading: 2.6–2.9× Eloquent

Where the database does most of the work, as with the aggregates, the three
come closer. SQLAlchemy's batched unit of work matches Orbit at saving changes
on MariaDB.

## The work

10,000 users, then these phases, each timed on its own:

| Phase | What it does |
|---|---|
| create | 10,000 `User.create(...)` in one transaction (each an INSERT that returns its id) |
| bulk insert | 10,000 posts in one call (`DB.table("posts").insertMany` / `insert` in chunks of 500 / a Core `insert` with a list) |
| find | 10,000 `User.find(id)` |
| filtered query | 1,000 `where active, age > n, order by age, limit 50` |
| load all | `User.all()` five times |
| change and save | load 2,000 users, change each, save (in a transaction) |
| eager load | 2,000 users with their posts, five times |
| aggregates | 1,000 `count()` and 1,000 `avg("age")` with a condition |

Every program prints a check line (rows found, seen and loaded); all three
print the same one.

## Results

### SQLite 3.53 (file)

Milliseconds, best of 3 (lower is better).

| | Orbit, `--release` | Orbit, `grav build` | Eloquent 13 | SQLAlchemy 2.0 |
|---|---:|---:|---:|---:|
| create 10,000, one by one | **95** | 128 | 1388 | 3004 |
| bulk insert 10,000 rows | 32 | 35 | **30** | 34 |
| find by id ×10,000 | **305** | 349 | 1203 | 2964 |
| filtered query ×1,000 | **347** | 408 | 611 | 744 |
| load all 10,000 ×5 | **316** | 374 | 500 | 456 |
| change and save 2,000 | **31** | 38 | 400 | 78 |
| eager load 2,000 + posts ×5 | **289** | 351 | 846 | 961 |
| count + avg ×1,000 | **812** | 833 | 1017 | 1592 |
| **total** | **2319** | 2591 | 6073 | 10412 |
| client CPU (s) | 2.37 | 2.64 | 6.22 | 10.92 |
| peak memory (MB) | 42 | 41 | 87 | 72 |

### PostgreSQL 17.6 (local socket)

Milliseconds, best of 3 (lower is better).

| | Orbit, `--release` | Orbit, `grav build` | Eloquent 13 | SQLAlchemy 2.0 |
|---|---:|---:|---:|---:|
| create 10,000, one by one | **690** | 702 | 2847 | 6483 |
| bulk insert 10,000 rows | 141 | **89** | 153 | 172 |
| find by id ×10,000 | **794** | 802 | 2715 | 5856 |
| filtered query ×1,000 | **562** | 602 | 1136 | 1206 |
| load all 10,000 ×5 | **377** | 425 | 477 | 534 |
| change and save 2,000 | **156** | 159 | 719 | 268 |
| eager load 2,000 + posts ×5 | **321** | 400 | 842 | 1053 |
| count + avg ×1,000 | **2488** | 2586 | 3073 | 3903 |
| **total** | **5628** | 5868 | 13555 | 20297 |
| client CPU (s) | 1.96 | 2.28 | 7.17 | 13.47 |
| peak memory (MB) | 41 | 41 | 85 | 74 |

### MariaDB 11.8 (local)

Milliseconds, best of 3 (lower is better).

| | Orbit, `--release` | Orbit, `grav build` | Eloquent 13 | SQLAlchemy 2.0 |
|---|---:|---:|---:|---:|
| create 10,000, one by one | **3921** | 5871 | 11987 | 14210 |
| bulk insert 10,000 rows | **560** | 634 | 980 | 729 |
| find by id ×10,000 | **1328** | 1404 | 2797 | 5069 |
| filtered query ×1,000 | **932** | 1023 | 1567 | 1257 |
| load all 10,000 ×5 | **366** | 460 | 669 | 579 |
| change and save 2,000 | 371 | **303** | 927 | 361 |
| eager load 2,000 + posts ×5 | **359** | 468 | 1017 | 1109 |
| count + avg ×1,000 | **5260** | 5774 | 5287 | 5472 |
| **total** | **14923** | 16831 | 25595 | 32992 |
| client CPU (s) | 2.55 | 3.04 | 9.44 | 13.81 |
| peak memory (MB) | 45 | 44 | 84 | 71 |

## How it was run

- An Intel Core i5-8350U (4 cores, 1.7 GHz), Kali Linux; the databases on the
  same machine (PostgreSQL over a Unix socket, MariaDB over its socket, SQLite
  in a file under /tmp). Each program ran three times per database; each phase
  shows its best time; memory is the peak RSS of the process.
- Orbit: Grav's compiler with `grav build` (-O2) and `grav build --release`
  (-O3, without stack-trace bookkeeping); grav-db's drivers on libsqlite3,
  libmariadb and libpq.
- Eloquent: illuminate/database 13.42 standalone (Capsule), PHP 8.5 with
  OPcache and the tracing JIT on; PDO.
- SQLAlchemy: 2.0.48 with its C extensions, Python 3.13; mysqlclient and
  psycopg2 (both C).

## Fairness notes

- Each ORM is written as its users would write it: Eloquent with `$casts`
  for the typed columns, SQLAlchemy with a `Session` per phase (so its
  identity map does not answer from memory).
- SQLAlchemy's create flushes each object (`add` then `flush`), so that each
  has its id at once as Orbit's and Eloquent's `create` do; adding all 10,000
  and flushing once would be faster but is a different operation.
- SQLAlchemy's change-and-save is its unit of work: one flush at commit,
  which batches the UPDATEs. Orbit and Eloquent save each model on its own.
- Orbit and Eloquent set `created_at` and `updated_at`; the SQLAlchemy models
  do too, with column defaults.

## Running it

```sh
# Orbit
grav build --release bench/orbit_bench.grav -o orbit_bench && ./orbit_bench
# Eloquent
cd bench && composer install && php -d opcache.enable_cli=1 -d opcache.jit=tracing eloquent_bench.php
# SQLAlchemy
python3 bench/sqlalchemy_bench.py
```

Each uses SQLite in /tmp by default; set `BENCH_DB` to a
`mysql://user:password@host/db` or `postgresql://user@host/db` URL for the others.
Each program drops and creates the `users` and `posts` tables in that database.
