<p align="center">
  <img src="docs/orbit-logo.svg" width="128" height="128" alt="Orbit logo">
</p>

<h1 align="center">Orbit</h1>

An ORM for [Grav](https://github.com/venomous-maker/grav), in the manner of
Laravel's Eloquent: models that save and find themselves, a query builder,
relations (polymorphic ones too) with eager loading, soft deletes, timestamps,
change tracking, model traits by decorator, a schema builder, migrations,
factories and seeders, read replicas, and a query log, debugbar, N+1 detection
and query cache for seeing what it sends. It sits on
[grav-db](https://github.com/venomous-maker/grav-db), so the same code runs on
**SQLite**, **MySQL/MariaDB** and **PostgreSQL**. Values always go to the
database as `?` arguments, and the names in a query are checked against the
model's fields, so a typo is an error before any SQL runs.

```grav
import "std"
import "grav-orbit"

class User extends Model {
    public id: long = 0
    public name: string = ""
    public email: string = ""
    public createdAt: DateTime? = null      // filled in on save
    public updatedAt: DateTime? = null
    fn posts() -> HasMany<Post> { return self.hasMany() }
}

class Post extends Model {
    public id: long = 0
    public userId: long = 0                 // the column user_id
    public title: string = ""
    public published: bool = false
    fn author() -> BelongsTo<User> { return self.belongsTo() }
}

fn main() {
    DB.connect(Sqlite.open("app.db"))
    User.createTable()
    Post.createTable()

    let ada = User.create(fields("name", "Ada", "email", "ada@example.com"))
    ada.posts().create(fields("title", "Hello", "published", true))

    let writers = User.whereHas("posts", fn(q: Builder) { q.where("published", true) })
                      .with("posts")
                      .orderBy("name")
                      .get()
    for (u in writers) {
        print(u.name + ": ${u.posts().get().size()} posts")
    }
}
```

## Performance

On the same work, Orbit runs 2.4–2.6× as fast as Laravel's Eloquent (PHP 8.5
with JIT) and 3.6–4.5× as fast as SQLAlchemy 2.0, using about half their memory:

| Total time | SQLite | PostgreSQL | MariaDB |
|---|---:|---:|---:|
| **Orbit** | **2.3 s** | **5.6 s** | **14.9 s** |
| Eloquent 13 | 6.1 s | 13.6 s | 25.6 s |
| SQLAlchemy 2.0 | 10.4 s | 20.3 s | 33.0 s |

The ratios are for SQLite and PostgreSQL. On MariaDB the server's own time
dominates, and Orbit is 1.7× and 2.2× as fast.
[bench/](bench/README.md) has the programs, each phase's times and how they
were run.

## Install

From GitHub:

```bash
grav add github.com/venomous-maker/grav-orbit          # the newest tag, or the default branch
```

(`grav add github.com/venomous-maker/grav-orbit@<tag>` takes a given tag.)
From a checkout on your machine (used as it is, so edits show at once):

```bash
grav add ../grav-orbit
```

Then `import "grav-orbit"` brings in Orbit and grav-db (`Sqlite`, `MySql`,
`Postgres`, `Connection`, `Row`, ...). Orbit depends on grav-db through its
`grav.toml`, so `grav install` fetches it.

Orbit needs a Grav compiler from November 2026 or later: it uses field
initializers, named decorator arguments (`@Column("email", length: 190)`),
`Decimal`, microsecond `DateTime`s, and reflection that creates objects and
calls methods (`ClassInfo.create`, `MethodInfo.invoke`). The database client
libraries are grav-db's: `libsqlite3` for SQLite, `libmariadb` or
`libmysqlclient` for MySQL, `libpq` for PostgreSQL, each loaded when the first
connection is made.

## Connecting

Orbit works on grav-db connections that you open and hand to `DB`:

```grav
DB.connect(Sqlite.open("app.db"))                                           // the default connection
DB.connect(MySql.open("mysql://app:secret@localhost/shop"))                 // (or a server)
DB.connect(Postgres.open("postgresql://app:secret@localhost/reports"), "reports")   // a named one
```

Models use the default connection unless their class says otherwise:

```grav
@Connection("reports")
class DailyTotal extends Model {
    public id: long = 0
    public day: DateTime? = null
    public total: Decimal = Decimal.of(0)
}
```

`DB.connection(name = "default")` gives a connection back (a `StateError` when
there is none), `DB.hasConnection(name)` says whether one is set, and
`DB.disconnect(name)` forgets it (closing it is yours). A query can also run on
a connection of its own: `User.query().on(otherDb).count()`. As in grav-db, a
connection is for one thread at a time.

## Models

A model is a class that extends `Model`. Its fields are its columns:

```grav
class User extends Model {
    public id: long = 0
    public name: string = ""
    public nickName: string? = null         // column nick_name; NULL allowed (the `?`)
    public age: int? = null
    public active: bool = true
    public balance: Decimal = Decimal.of(0)
    public avatar: Bytes? = null
    public settings: JsonValue? = null
    public createdAt: DateTime? = null
    public updatedAt: DateTime? = null
}
```

**What is a column.** Fields holding numbers, bools, strings, enums (stored as
their number), `DateTime`, `Decimal`, `Bytes`, `JsonValue` or `any`, and the
`T?` forms of these, are columns. Fields holding other objects (lists, maps,
models) are not.

**The conventions.**

- The table is the class name, snake_case and plural: `User` is `users`,
  `OrderItem` is `order_items`, `Category` is `categories`, `Box` is `boxes`.
- A column is its field's name in snake_case: `nickName` is `nick_name`,
  `createdAt` is `created_at`.
- The id is the field called `id`. An `int` or `long` id is numbered by the
  database, and filled in on the object when it is inserted.
- A `T?` field is a nullable column; any other field is `NOT NULL`.

Anywhere Orbit takes a name (in `where`, `orderBy`, `fields(...)`, a relation's
keys), it takes the field name or the column name: `"nickName"` and
`"nick_name"` are the same.

**Field initializers** are the defaults of a new object: `User.make(...)`,
`User.create(...)`, `new User()` and a factory all start from them, so `active`
above is `true` and `balance` is `0` until something sets them.

**Decorators** change the mapping. On a class:

| Decorator | Does |
|-----------|------|
| `@Table("people")` | the table's name |
| `@Connection("reports")` | the named connection the class uses |
| `@MorphName("post")` | its name in polymorphic relations' type columns (the class name otherwise) |
| `@NoTimestamps` | `createdAt` and `updatedAt` are not filled in |
| `@SoftDeletes`, `@SoftDeletes("removedAt")` | soft deletes (see [Soft deletes](#soft-deletes)) |
| `@Timestamps("created", "updated")` | other names for the timestamp fields |
| `@Uuids`, `@Uuids("field")` | a new row gets a random UUID (see [Behaviors](#behaviors-model-traits)) |
| `@Appends("initials", ...)` | these properties' getters go into `toMap` and `toJson` (see [Accessors](#accessors-mutators-and-casts)) |

On a field:

| Decorator | Does |
|-----------|------|
| `@Id` | this field is the id (instead of the one called `id`) |
| `@Id(auto: false)` | an integer id the database does not number (you set it) |
| `@Column("email_address")` | the column's name |
| `@Column(..., length: 255)` | `VARCHAR(255)` for a string |
| `@Column(..., precision: 10, scale: 2)` | `DECIMAL(10, 2)` for a `Decimal` |
| `@Column(..., unique: true)` | a `UNIQUE` column |
| `@Column(..., nullable: true)` | NULL allowed, though the field is not `T?` |
| `@Column(..., type: "CHAR(2)")` | the SQL type, as written |
| `@Ignore` | not a column |
| `@Hidden` | left out of `toMap()` and `toJson()` |
| `@Guarded` | not set by mass assignment (`create`, `make`, `fill`, `update`) |
| `@Cast("money")` | a field of any type, stored through a registered `Cast` (built in: `json`, `csv`) |
| `@NotNull` | `NOT NULL`, though the field is `T?` |
| `@Unique` | a `UNIQUE` column |

`@Column` takes the column name first (optional), then any of its named
arguments:

```grav
@Table("accounts")
class Account extends Model {
    @Id public number: long = 0
    @Column("email_address", length: 190, unique: true)
    public email: string = ""
    @Column(precision: 12, scale: 2)
    public balance: Decimal = Decimal.of(0)
    @Column(type: "CHAR(2)")
    public country: string = "KE"
    @Hidden public passwordHash: string = ""
    @Guarded public role: string = "member"
    @Ignore public cache: string = ""
}
```

A string id (a UUID, a code) is not numbered: set it yourself, or let `@Uuids("id")`
fill it in:

```grav
@Uuids("id")
class ApiKey extends Model {
    public id: string = ""
    public label: string = ""
}
```

The length, precision, scale, uniqueness, nullability and SQL type are what
`Model.createTable()` uses to make the table; a table you make with the
[schema builder](#the-schema-builder) has the columns you give it.

## Creating, reading, updating, deleting

`fields(...)` makes the maps Orbit takes: names and values in pairs.

```grav
// Creating
let ada = User.create(fields("name", "Ada", "age", 36))      // INSERT; ada.id is filled in
let bob = User.make(fields("name", "Bob"))                    // a new User, not saved
bob.save()                                                    // INSERT
let cy = new User()
cy.name = "Cy"
cy.save()

// Reading
let u = User.find(1)                          // a User, or null
let v = User.findOrFail(1)                    // NotFound when there is none
let some = User.findMany([1, 2, 3])           // those that exist
let all = User.all()
let first = User.first()

// Updating
ada.name = "Ada L."
ada.save()                                    // UPDATE of the changed columns only
ada.update(fields("age", 37))                 // set and save
ada.fill(fields("age", 38, "active", false))  // set, not saved
ada.save()
ada.increment("age")                          // in the object and its row
ada.decrement("age", 2)                       // decrement takes a step too
ada.touch()                                   // saves it with updatedAt set to now

// Deleting
ada.delete()                                  // true when there was a row
User.destroy([4, 5, 6])                       // by id; how many
```

**Find or make.**

```grav
// The first user with this email, or a new one with both maps' fields, saved.
let eve = User.firstOrCreate(fields("email", "eve@example.com"), fields("name", "Eve"))
// The same, not saved.
let fay = User.firstOrNew(fields("email", "fay@example.com"), fields("name", "Fay"))
// The first match with the second map set and saved, or a new one.
let gus = User.updateOrCreate(fields("email", "gus@example.com"), fields("age", 30))
// The user with id 7, or a new (unsaved) one.
let maybe = User.findOrNew(7)
```

**Reloading and copying.** `u.refresh()` reads the row again (a `NotFound`
when it is gone). `u.replicate()` is a copy without the id, not saved; it is a
`Model`, so cast it: `let copy = u.replicate() as User`. `u.isNew()` says
whether it is saved yet, and `u.isSame(other)` whether two objects are the same
row.

**Many at once.** `User.saveAll(users)` saves a list in one transaction.
`User.truncate()` deletes every row, and `User.tableName()` is the table's name.

**Mass assignment.** `create`, `make`, `fill`, `update`, `firstOrCreate`,
`firstOrNew` and `updateOrCreate` set any field
except the `@Guarded` ones and a numbered id, which they leave as they are, so
a map built from a form cannot set them. Set them directly instead
(`u.role = "admin"`). A name that is no field of the class is a `ValueError`.

```grav
let u = User.make(fields("name", "Dee", "role", "admin"))
print(u.role)        // "member": role is @Guarded
```

## The query builder

`User.where(...)`, `User.query()` and the other static methods start a
`Query<User>`; each clause adds to it and returns it, and `get()`, `first()`,
`count()` and the like run it.

```grav
let adults = User.where("age", ">=", 18)
                 .where("active", true)
                 .orderBy("name")
                 .limit(20)
                 .get()                            // Array<User>
```

### Conditions

```grav
User.where("name", "Ada")                          // name = ? (IS NULL for null)
User.where("age", ">", 30)                         // =, !=, <>, <, <=, >, >=, like, not like, ilike
User.where("age", ">", 30).orWhere("role", "admin")
User.query().whereNot("role", "admin")             // != (IS NOT NULL for null)

// Groups in parentheses, through a function
User.where("active", true)
    .where(fn(q: Builder) { q.where("age", ">", 30).orWhereNull("age") })
User.query().whereNot(fn(q: Builder) { q.where("role", "guest").orWhere("age", "<", 13) })
// (and orWhere(fn), orWhereNot(fn) for an OR group)

User.whereIn("name", ["Ada", "Bob"])               // whereNotIn, orWhereIn, orWhereNotIn
User.whereNull("age")                              // whereNotNull, orWhereNull, orWhereNotNull
User.whereBetween("age", 18, 65)                   // whereNotBetween, orWhereBetween, orWhereNotBetween
User.whereColumn("updatedAt", ">", "createdAt")    // two columns; orWhereColumn
User.whereLike("email", "%@example.com")           // whereNotLike, orWhereLike
User.where("name", "ilike", "ada%")                // case-insensitive (LOWER(...) LIKE LOWER(?) outside PostgreSQL)
User.query().whereDate("createdAt", ">=", "2026-01-01")   // the date part (a DateTime works too)
User.query().whereYear("createdAt", "=", 2026)
User.query().whereKey(7)                           // by id; whereKey([1, 2, 3])
User.whereRaw("LOWER(name) = ?", ["ada"])          // SQL, with ? arguments; orWhereRaw
Post.whereBelongsTo(ada)                           // posts.user_id = ada.id (the relation named after the class: user)
Post.whereBelongsTo(ada, "author")                 // through another belongsTo; a list of owners works too
```

An empty `whereIn` list matches no rows, and an empty `whereNotIn` list matches
every row.

**JSON columns.** A name `column->key->key` reads a path inside a JSON column
(a `JsonValue` field, or a `@Cast("json")` one), as text; numbers compare as
numbers and bools as bools, on every database:

```grav
Setting.where("data->lang", "en")
Setting.where("data->nested->x", "y")
Setting.where("data->qty", ">", 2)
Setting.where("data->dark", true)
```

Each key is a plain identifier (letters, digits, `_`). It is SQLite's
`json_extract`, MySQL's `JSON_EXTRACT` and PostgreSQL's `#>>`.

**Full-text search.** `whereFullText(["title", "body"], "grav tips")` (and
`orWhereFullText`) is MySQL's `MATCH ... AGAINST` (it needs a full-text index:
`t.fullText(["title", "body"])` in the schema), PostgreSQL's
`to_tsvector(...) @@ plainto_tsquery(...)` (English; `t.fullText` makes the
matching GIN index), and on SQLite every word in one of the columns
(`LIKE`, no index).

**Subqueries.** A query can stand where a value does, or as a list for
`whereIn`, or as a test for `whereExists`. Name the outer table's columns as
`table.column` to tie them together:

```grav
// users with a published post
User.whereIn("id", Post.query().select(["userId"]).where("published", true))
// users with a profile
User.whereExists(DB.table("profiles").whereColumn("profiles.user_id", "=", "users.id"))   // whereNotExists, orWhereExists
// posts above the average
Post.where("views", ">", DB.table("posts").selectRaw("AVG(views)"))
// a column from a subquery, read with extra("top_post")
User.query().selectSub(Post.query().select(["title"])
    .whereColumn("posts.user_id", "=", "users.id").orderBy("views", "desc").limit(1), "top_post")
```

**Unions.** `union(other)` adds another query's rows (the same columns),
without duplicates; `unionAll(other)` keeps them. The first query's order,
limit and offset apply to all the rows:

```grav
User.where("name", "Ada").union(User.where("role", "admin")).orderBy("name").get()
```

**Local scopes.** A method marked `@Scope` takes the query first (and any
arguments after); `scope(name, args)` applies it, from the class or from a
query:

```grav
class User extends Model {
    ...
    @Scope fn adults(q: Builder) { q.where("age", ">=", 18) }
    @Scope fn named(q: Builder, prefix: string) { q.whereLike("name", prefix + "%") }
}

User.scope("adults").count()
User.query().scope("adults").scope("named", ["B"]).get()
```

A name that is no `@Scope` method of the class is a `ValueError`.

**Optional parts.** `when(condition, f)` applies `f` when the condition holds,
`unless(condition, f)` when it does not, and `tap(f)` always (a reusable piece
of a query, kept in a function):

```grav
fn active(q: Builder) { q.where("active", true).whereNotNull("email") }

fn search(term: string, minAge: int) -> Array<User> {
    return User.query()
        .tap(active)
        .when(term != "", fn(q: Builder) { q.whereLike("name", "%" + term + "%") })
        .unless(minAge == 0, fn(q: Builder) { q.where("age", ">=", minAge) })
        .get()
}
```

### Order and paging

```grav
User.orderBy("name")                       // orderBy(name, "desc"), orderByDesc(name)
User.query().orderByRaw("LENGTH(name) DESC")
User.latest()                              // createdAt, newest first; latest("updatedAt")
User.oldest()
User.query().inRandomOrder()
User.orderBy("name").reorder()             // drops the order so far
User.limit(10)                             // take(10) is the same
User.query().offset(20).limit(10)          // skip(20) is the same
User.query().forPage(3, 25)                // rows 51 to 75
User.query().sharedLock()                  // FOR SHARE (MySQL: LOCK IN SHARE MODE); lockForUpdate: FOR UPDATE
```

**Pages.** `paginate(page = 1, perPage = 15)` runs a count and the page, and
gives a `Page<T>`: its `items`, `total`, `page` and `perPage`, with
`lastPage()`, `hasMorePages()` and `isEmpty()`.

```grav
let page = User.query().orderBy("name").paginate(2, 20)
print("page ${page.page} of ${page.lastPage()}, ${page.total} users")
for (u in page.items) { print(u.name) }
```

**Pages without a total.** `simplePaginate(page, perPage)` skips the count: it
reads one row more than the page to know whether another follows, and gives a
`SimplePage<T>` (`items`, `page`, `perPage`, `hasMorePages()`).
`cursorPaginate(perPage, cursor = "")` pages by id without an OFFSET (so deep
pages stay fast, and rows added meanwhile are not skipped or repeated): pass
the previous page's `nextCursor` for the next one (`""` after the last):

```grav
let first = User.cursorPaginate(50)
let second = User.cursorPaginate(50, first.nextCursor)     // second.hasMorePages()
```

**A big table, a part at a time.** `chunk(size, f)` reads `size` rows at a
time in id order and hands each part to `f`; `chunkById(size, f)` pages by id
(`id > last`) instead of by offset, so rows changed meanwhile are not skipped
or repeated; `each(f)` hands over one object at a time.

```grav
User.where("active", false).chunkById(500, fn(part: Array<User>) {
    for (u in part) { u.delete() }
})
User.query().each(fn(u: User) { print(u.email) })
User.lazy(fn(u: User) { print(u.email) }, 1000)        // chunkById underneath: one object at a time
User.where("active", true).cursor(fn(u: User) { print(u.email) })

for (u in User.where("active", true).iterate(500)) {   // a loop: 500 rows a query, in id order
    if (u.email == "") { break }                       // stops reading further pages
}
```

`iterate(size)` (on a query or a model class) is `lazy` as a `for` loop: it
reads `size` rows at a time by id, and a loop that ends early reads no more.

`cursor(f)` runs one query and makes each object as its row arrives (MySQL
streams it); it applies no `with()`, and `f` should not query the same
connection meanwhile (MySQL does not allow it while a result is streaming).

### Columns, joins, groups

```grav
User.select(["id", "name"])                              // only these columns
User.query().select(["id", "name"]).selectRaw("LENGTH(name) AS name_length")
Post.query().select(["userId"]).distinct()

DB.table("posts")
    .join("users", "users.id", "=", "posts.user_id")     // leftJoin, rightJoin
    .where("users.name", "Bob")
    .pluck("title")

DB.table("posts")
    .selectRaw("user_id, COUNT(*) AS n")
    .groupBy("user_id")
    .having("n", ">", 1)                                 // a selected alias, or a field
    .get()
Post.query().groupBy("userId").havingRaw("COUNT(*) > ?", [1])
```

With joins, write a column as `table.column`. A column a query selects beyond
the model's fields (from `selectRaw`, `withCount`, a pivot) is kept on each
object: read it with `u.extra("name_length")`. A `having` on a `selectRaw`
alias works on PostgreSQL too: Orbit puts the expression back.

### Answers

| Call | Gives |
|------|-------|
| `get()`, `all()` | every match, as `Array<T>` |
| `first()` | the first match, or null |
| `firstOrFail()` | the first match; `NotFound` when there is none |
| `sole()` | the one match: `NotFound` for none, `StateError` for more than one |
| `firstWhere(name, value)`, `firstWhere(name, op, value)` | the first match of one more condition |
| `firstOr(f)` | the first match, or what `f` gives |
| `find(id)`, `findMany(ids)`, `findOrFail(id)`, `findOrNew(id)` | by id |
| `count()` | how many (a `long`) |
| `exists()`, `doesntExist()` | whether there are any |
| `sum(name)` | the total, as a `Decimal` (0 for no rows) |
| `avg(name)` | the mean, as a `float` (0 for no rows) |
| `min(name)`, `max(name)` | the smallest and largest value (null for no rows) |
| `pluck(name)` | one column of every match, as `Array<any>` |
| `value(name)` | one column of the first match, or null |
| `rows()` | the rows as they come (a grav-db `ResultSet`) |

```grav
let total = Order.where("paid", true).sum("amount")       // a Decimal
let names = User.orderBy("name").pluck("name")
let email = User.where("name", "Ada").value("email")
let fallback = User.query().where("name", "Nobody").firstOr(fn() -> User => User.make(fields("name", "guest")))
```

### Writing through a query

```grav
Post.where("published", false).update(fields("views", 0))     // how many rows; updatedAt is set too
Post.where("views", 0).delete()                               // (marks them, for @SoftDeletes)
Post.where("title", "Hello").increment("views")               // decrement, and a step: increment("views", 5)
```

**Upserts.** `upsert(rows, uniqueBy, update)` inserts each row or, where one
with the same `uniqueBy` columns exists, updates its `update` columns.
`insertOrIgnore(rows)` inserts the rows a unique key does not already have.
Both are batched, and fill in `createdAt` and `updatedAt` when the model has
them.

```grav
let rows = new Array<HashMap<string, any>>()
rows.push(fields("email", "ada@example.com", "name", "Ada", "age", 37))
rows.push(fields("email", "zed@example.com", "name", "Zed", "age", 22))
User.upsert(rows, ["email"], ["name", "age"])
User.insertOrIgnore(rows)
```

On SQLite and PostgreSQL, `uniqueBy` must be the columns of a unique index or
the primary key (it is the `ON CONFLICT` target); MySQL uses its `ON DUPLICATE
KEY UPDATE`, which goes by any unique key.

### Looking at the SQL, and locking

```grav
let q = User.where("age", ">", 18).orderBy("name")
print(q.toSql())          // SELECT "users".* FROM "users" WHERE "users"."age" > ? ORDER BY "users"."name" ASC
print("${q.getBindings()}")

DB.transaction(fn() {
    let acct = Account.query().whereKey(7).lockForUpdate().first()   // FOR UPDATE (MySQL, PostgreSQL)
    acct.balance = acct.balance + Decimal.parse("10.00")
    acct.save()
})
```

`lockForUpdate` does nothing on SQLite, whose transactions lock the whole
database.

To see every statement a program sends, with its time, use
[the query log](#watching-the-queries).

### What the static methods offer

`User.where(...)` and its kin are shortcuts for `User.query().where(...)`.
They cover the common starts: `query`, `where` (all three forms), `whereIn`,
`whereNotIn`, `whereNull`, `whereNotNull`, `whereBetween`, `whereLike`,
`whereColumn`, `whereRaw`, `has`, `doesntHave`, `whereHas`,
`whereDoesntHave`, `whereRelation`, `whereHasMorph`, `whereBelongsTo`,
`whereExists`, `whereFullText`, `scope`, `with` (with a constraint too),
`withWhereHas`, `withCount`, `withSum`, `withExists`, `withoutScope`,
`withTrashed`, `onlyTrashed`, `select`, `orderBy`, `latest`, `oldest` and
`limit`; and the answers `all`, `first`, `firstWhere(name, value)`, `find`,
`findOrFail`, `findMany`, `findOrNew`, `count`, `sum`, `avg`, `min`, `max`,
`pluck`, `paginate`, `simplePaginate`, `cursorPaginate`, `chunk`, `chunkById`,
`cursor`, `lazy`, `upsert` and `insertOrIgnore`. Anything else starts with `User.query()`:
`User.query().whereDate(...)`, `User.query().when(...)`.

## Watching the queries

Every statement Orbit sends (a model's save, a query, a relation's load, raw
`DB.select`) goes through one place that can log it, time it, answer it from a
cache and count it. With none of that switched on, it costs nothing.

### The query log and listeners

```grav
DB.enableQueryLog()
User.with("posts").where("active", true).get()
for (q in DB.getQueryLog()) {
    print(q.toString())    // SELECT "users".* FROM "users" WHERE "users"."active" = ? [true] (0.21 ms)
}
DB.flushQueryLog()
DB.disableQueryLog()

DB.listen(fn(q: QueryEvent) {                      // every statement, logged or not
    if (q.ms > 100.0) { Log.warn("slow query: " + q.toString()) }
})
```

A `QueryEvent` has the `sql`, its `bindings`, the `connection` name, `ms`,
`rows` (read, or changed), whether it was a `read`, went to a `replica`, came
from the `cached` results, its `batch` size (`insertMany`, `upsert`), and the
`error` when it failed (a failed statement is logged too, and still throws).
The log keeps the newest `Sql.logLimit` events (10000), so a long-running
program can leave it on.

### The debugbar

`Debugbar` reads the log and points at what deserves a look: the same query
shape run again and again with only its arguments changing (the mark of an
N+1), exact duplicates, relations lazy-loaded one object at a time, failures,
and the slowest statements.

```grav
Debugbar.enable()
for (u in User.all()) { print(u.posts().count()) }       // one COUNT per user
print(Debugbar.report())
// orbit: 51 statements in 4.20 ms (51 reads, 0 writes)
//   N+1: User.posts() lazy-loaded 50× on objects read together — with("posts")
//   repeated 50× (3.90 ms): SELECT COUNT(*) FROM "posts" WHERE ...
//   slowest: ...

Debugbar.reset()                                          // a new request
print(Debugbar.measure(fn() { User.with("posts").get() }))  // run something and report on it alone
let st = Debugbar.stats()                                 // the figures (DebugStats)
let json = Debugbar.toJson()                              // every statement too, for a panel of your own
page = page + Debugbar.html()                             // a panel fixed to the bottom of a page
```

`Debugbar.repeatThreshold` (3) is how many runs make a shape "repeated". The
HTML panel shows the SQL and its arguments: keep it off production pages.

### N+1 detection

A relation read with `get()` (or `count()`) on an object that its query read
together with others, without `with(...)`, runs one more query for each of
them: an N+1. Orbit can stop it, warn about it, or count it:

```grav
Orbit.preventLazyLoading()            // throws LazyLoadingViolation (model, relation)
Orbit.warnOnLazyLoading()             // or: one line on stderr per Class.relation
Orbit.handleLazyLoadingViolationsUsing(fn(m: Model, relation: string) {
    Log.warn("N+1: " + ClassInfo.of(m).simpleName() + "." + relation)
})
Orbit.detectLazyLoading()             // or only count them: Orbit.lazyLoads(), the debugbar
```

Objects read alone (`find`, `first`) still lazy-load freely: that is one query,
not N. Relations loaded by `with` (or `load`) are never lazy.

### Remembered results (the query cache)

`remember(seconds)` keeps a query's results in the query cache: the first run
reads the database, identical runs after it (the same SQL with the same
arguments) the cache, until the time is up or Orbit writes to a table the query
reads — a model's save or delete, a query's update, delete or insert, or a
pivot change on that table drops the results that read it. Relations its
`with` loads are remembered as long.

```grav
Orbit.cacheQueries()                                          // in memory, up to 1000 results
let popular = Post.where("views", ">", 1000).with("author").remember(60).get()
let n = User.where("active", true).remember(300).count()      // counts, pluck, exists too
Post.where("id", 7).update(fields("views", 0))               // posts' remembered results go
Orbit.flushQueryCache()                                       // or all of them, by hand
Orbit.forgetCachedTable("users")                              // or those that read one table
```

The cache is per process; a write made elsewhere (another process, a
database trigger) is seen once the time is up. Raw writes (`DB.statement`,
`DB.update`, ...) drop every remembered result of their connection, since Orbit
cannot tell which tables they change. Nothing is cached, or read from the
cache, inside a transaction; what a transaction writes is invalidated again
when it ends. `Orbit.useQueryCache(store)` takes a `QueryCache` of your own;
`MemoryQueryCache` counts its `hits` and `misses`.

## Relations

A relation is a method of the model that returns one. The type argument comes
from the method's return type:

```grav
class User extends Model {
    public id: long = 0
    public name: string = ""
    fn posts() -> HasMany<Post> { return self.hasMany() }             // posts.user_id
    fn profile() -> HasOne<Profile> { return self.hasOne() }          // profiles.user_id
    fn roles() -> BelongsToMany<Role> { return self.belongsToMany() } // the pivot role_user
}

class Post extends Model {
    public id: long = 0
    public userId: long = 0
    public title: string = ""
    fn author() -> BelongsTo<User> { return self.belongsTo() }        // posts.user_id -> users.id
}
```

The keys follow Eloquent's names. A foreign key is the owner's class name,
snake_case, with `_id` (`user_id`), found among the related class's fields by
field or column name. Each can be given:

| Method | Arguments (all optional) |
|--------|--------------------------|
| `hasMany<T>`, `hasOne<T>` | `foreignKey` (on T), `localKey` (on this class; its id) |
| `belongsTo<T>` | `foreignKey` (on this class; T's name + `_id`), `ownerKey` (on T; its id) |
| `belongsToMany<T>` | `table` (both names, singular, in alphabetical order: `role_user`), `foreignPivotKey` (`user_id`), `relatedPivotKey` (`role_id`) |
| `hasManyThrough<T, U>`, `hasOneThrough<T, U>` | `firstKey` (on U), `secondKey` (on T), `localKey`, `secondLocalKey` |
| `morphMany<T>`, `morphOne<T>`, `morphTo` | `name` (the columns `<name>_id` and `<name>_type`) |
| `morphToMany<T>`, `morphedByMany<T>` | `name`, `table` (`<name>` plural: `taggables`) |

```grav
fn writer() -> BelongsTo<User> { return self.belongsTo("author_id") }
fn articles() -> HasMany<Post> { return self.hasMany("author_id") }
```

### Using a relation

A relation's `get()` runs it (or gives what `with()` loaded); `query()`, and
the shortcuts `where`, `whereIn`, `orderBy`, `latest`, `limit` and `with` on the
many-sided relations, give a `Query<T>` to narrow further.

```grav
let posts = user.posts().get()                              // Array<Post>
let recent = user.posts().where("published", true).latest().limit(5).get()
let n = user.posts().count()
let titles = user.posts().pluck("title")
let has = user.posts().exists()
let profile = user.profile().get()                          // a Profile, or null
let author = post.author().get()                            // a User, or null

user.posts().create(fields("title", "Hi"))                  // user_id set, saved
user.posts().save(somePost)                                 // and saveMany(list)
user.profile().create(fields("bio", "First programmer"))

post.author().associate(bob)                                // sets user_id (save to keep it)
post.save()
post.author().dissociate()
```

**One of many.** A `hasOne` can pick one row out of many: the one with the
largest (or smallest) value of a column, the id by default. It loads, counts
and filters like any `hasOne`:

```grav
fn latestPost() -> HasOne<Post> { return self.hasOne::<Post>().latestOfMany() }            // the largest id
fn firstPost() -> HasOne<Post> { return self.hasOne::<Post>().oldestOfMany("createdAt") }
fn mostViewed() -> HasOne<Post> { return self.hasOne::<Post>().ofMany("views", "max") }

User.with("latestPost").get()
User.whereHas("latestPost", fn(q: Builder) { q.where("published", true) })
```

**Defaults.** `withDefault()` on a `hasOne` or `belongsTo` makes `get()` give a
new, unsaved object instead of null, with the fields given:

```grav
fn author() -> BelongsTo<User> { return self.belongsTo::<User>("user_id").withDefault(fields("name", "Guest")) }
post.author().get().name           // "Guest" when the post has no author
```

### Many-to-many

```grav
class User extends Model {
    ...
    fn roles() -> BelongsToMany<Role> { return self.belongsToMany() }
    // Pivot columns read with each role, a pivot condition, pivot timestamps.
    fn rankedRoles() -> BelongsToMany<Role> {
        return self.belongsToMany::<Role>().withPivot(["level"]).withTimestamps()
    }
    fn seniorRoles() -> BelongsToMany<Role> {
        return self.belongsToMany::<Role>().withPivot(["level"]).wherePivot("level", ">=", 3)
    }
}
class Role extends Model {
    public id: long = 0
    public name: string = ""
    fn users() -> BelongsToMany<User> { return self.belongsToMany() }
}
```

(When the relation is chained further, give the type argument with `::<Role>`.)

```grav
user.roles().attach(admin.id)                           // a key, or the object: attach(admin)
user.rankedRoles().attach(admin, fields("level", 5))    // with pivot columns
user.roles().attachMany([1, 2, 3])
user.roles().detach(editor)                             // how many links went; detachMany(ids), detachAll()
user.roles().sync([1, 2])                               // exactly these: missing ones attached, others detached
user.roles().syncWithoutDetaching([3])                  // attach those missing, detach nothing
user.roles().toggle([1, 4])                             // attach what is not linked, detach what is
user.rankedRoles().updateExistingPivot(editor.id, fields("level", 1))
let ids = user.roles().linkedKeys()                     // the linked keys, from the pivot

for (r in user.rankedRoles().orderBy("name").get()) {
    print(r.name + " at level ${r.pivot("level")}, since ${r.pivot("created_at")}")
}
```

`withTimestamps()` fills the pivot's `created_at` and `updated_at` on
`attach` (and `updated_at` on `updateExistingPivot`), and reads them back.
`wherePivot(column, value)` and `wherePivot(column, op, value)` limit the links
a relation sees, in queries, `whereHas` and `with` alike.

### Through another model

```grav
class Country extends Model {
    public id: long = 0
    public name: string = ""
    // countries -> citizens.country_id -> notes.citizen_id
    fn notes() -> HasManyThrough<Note, Citizen> { return self.hasManyThrough() }
    fn firstNote() -> HasOneThrough<Note, Citizen> { return self.hasOneThrough() }
}
class Citizen extends Model { public id: long = 0; public countryId: long = 0; public name: string = "" }
class Note extends Model { public id: long = 0; public citizenId: long = 0; public text: string = "" }

let notes = kenya.notes().get()
let n = kenya.notes().count()
let one = kenya.firstNote().get()        // a Note, or null
```

`HasManyThrough` also has `first()`, `pluck` and the query shortcuts.

### Polymorphic relations

A polymorphic relation `x` uses two columns, `x_id` and `x_type`; the type
holds the class's morph name (its name, `Post`, or its `@MorphName`).

```grav
class Comment extends Model {
    public id: long = 0
    public body: string = ""
    public commentableId: long = 0
    public commentableType: string = ""
    fn commentable() -> MorphTo { return self.morphTo("commentable") }
}
class Post extends Model {
    ...
    fn comments() -> MorphMany<Comment> { return self.morphMany("commentable") }
    fn cover() -> MorphOne<Image> { return self.morphOne("imageable") }
    fn tags() -> BelongsToMany<Tag> { return self.morphToMany("taggable") }   // taggables(tag_id, taggable_id, taggable_type)
}
class Video extends Model {
    ...
    fn comments() -> MorphMany<Comment> { return self.morphMany("commentable") }
}
class Tag extends Model {
    public id: long = 0
    public name: string = ""
    fn posts() -> BelongsToMany<Post> { return self.morphedByMany("taggable") }
}

post.comments().create(fields("body", "Nice post"))     // commentable_id and commentable_type set
video.comments().count()
let target = comment.commentable().get()                // a Model: a Post or a Video
if (target is Video) { print((target as Video).title) }
comment.commentable().associate(video)                  // save the comment to keep it
post.tags().attachMany([grav.id, news.id])
let tagged = grav.posts().get()
```

`MorphMany` and `MorphOne` have `query`, `get`, `save` and `create` (and
`MorphMany` `count` and `pluck`); a morph-to-many relation is a
`BelongsToMany`, with all of its pivot methods.

**The morph map.** `morphTo` finds the class from the type column's value,
among the classes Orbit has mapped so far. A class is mapped the first time it
is used, so before reading a `morphTo` whose classes may not have been used
yet, register them, or give a type value its class by hand:

```grav
Orbit.register([reflect(Post), reflect(Video)])
Orbit.morphMap("post", reflect(Post))        // "post" in commentable_type means Post
```

## Querying relations

**Eager loading.** `with` loads a relation for every result in one query (one
query a level for a nested path), so `get()` on it afterwards runs nothing:

```grav
let users = User.with("posts").with("profile").get()
let deep = User.with("posts.comments").get()             // posts, and their comments
let both = User.with(["posts", "roles"]).get()
let comments = Comment.with("commentable").get()          // morphTo too: one query per type

// Only some of them: a constraint on the loaded relation (the last part of a path)
let users = User.with("posts", fn(q: Builder) { q.where("published", true).latest() }).get()
let nice = User.with("posts.comments", fn(q: Builder) { q.whereLike("body", "Nice%") }).get()
// The users that have such posts, with just those loaded
let busy = User.withWhereHas("posts", fn(q: Builder) { q.where("views", ">", 100) }).get()
```

**By what they have.**

```grav
User.has("posts")                                         // at least one post
User.has("posts", ">=", 3)                                // a count; orHas
User.has("posts.comments")                                // through both
User.doesntHave("posts")
User.whereHas("posts", fn(q: Builder) { q.where("published", true) })
User.query().whereHas("posts", fn(q: Builder) { q.where("views", ">", 100) }, ">=", 2)
User.query().where("active", true).orWhereHas("roles", fn(q: Builder) { q.where("name", "admin") })
User.whereDoesntHave("posts", fn(q: Builder) { q.where("published", true) })   // orWhereDoesntHave
User.whereRelation("posts", "views", ">", 7)              // whereHas with one condition; orWhereRelation
```

A `morphTo` points into several tables, so name the types to look in
(their morph names):

```grav
Comment.whereHasMorph("commentable", ["Post", "Video"], fn(q: Builder) { q.whereLike("title", "Grav%") })
Comment.query().hasMorph("commentable", ["Video"])        // orWhereHasMorph, whereDoesntHaveMorph
```

**Counts and other aggregates** of a relation come with each row:

```grav
for (u in User.withCount("posts").get()) { print("${u.name}: ${u.countOf("posts")}") }
User.query().withCount("posts", fn(q: Builder) { q.where("published", true) })

let users = User.withSum("posts", "views").withExists("profile").get()
let views = users[0].extra("posts_sum_views")             // also withAvg, withMin, withMax
let hasProfile = users[0].extra("profile_exists")         // 1 or 0 (true or false on PostgreSQL)
```

The added columns are `<relation>_count`, `<relation>_sum_<field>` (and
`_avg_`, `_min_`, `_max_`) and `<relation>_exists`, in snake_case. `withAvg`,
`withMin` and `withMax` are on `Query`: `User.query().withAvg("posts", "views")`.

**On an object you have.**

```grav
user.load("posts")                    // now, as with() would have
user.loadMissing("posts")             // unless it is loaded already
user.relationLoaded("posts")          // whether it is
user.load("posts", fn(q: Builder) { q.where("published", true) })   // with a constraint
user.loadCount("posts").countOf("posts")
user.posts().get()[0].title = "Edited"
user.push()                           // saves the user and every loaded related object, all the way down
```

## Model features

### Timestamps

A model with `createdAt` and `updatedAt` fields (`DateTime?`) gets them filled
in: both when it is inserted (`createdAt` only when it is null), and
`updatedAt` on each save that changes something. A query's `update` and
`increment` set `updatedAt` too, and `upsert` and `insertOrIgnore` fill both.
A model without such fields has no timestamps; `@NoTimestamps` turns them off
for one that has them, and `@Timestamps("created", "updated")` names other
fields. `implements HasTimestamps` gives a model both fields.

### Soft deletes

```grav
class Post extends Model implements SoftDeletes {   // brings deletedAt and @SoftDeletes
    public id: long = 0
    public title: string = ""
}

// or, with the field written out (and named as you like):
@SoftDeletes("removedAt")
class Draft extends Model {
    public id: long = 0
    public removedAt: DateTime? = null
}

post.delete()                       // sets deletedAt; the row stays
post.trashed()                      // true
Post.count()                        // leaves deleted rows out (so do find, whereHas, with, ...)
Post.withTrashed().count()          // every row
Post.onlyTrashed().get()            // only deleted ones
post.restore()                      // deletedAt back to null
post.forceDelete()                  // really deletes the row
Post.onlyTrashed().where("title", "Old").restore()   // on a query too
Post.where("views", 0).forceDelete()
```

A class marked `@SoftDeletes` without the `DateTime?` field is a `StateError`
the first time it is used.

### Change tracking

A model remembers the values its row has, so a save sends only the columns
that changed, and none at all (no UPDATE) when nothing did.

```grav
let ada = User.firstWhere("email", "ada@example.com")
ada.isDirty()                       // false
ada.name = "Ada K."
ada.isDirty()                       // true; isDirty("name") true, isDirty("age") false
ada.isClean("age")                  // true
ada.getDirty()                      // {name: "Ada K."}
ada.getOriginal("name")             // "Ada"
ada.save()                          // UPDATE users SET name = ?, updated_at = ? WHERE id = ?
ada.wasChanged("name")              // true: what the last save changed
ada.getChanges()                    // {name: ..., updatedAt: ...}
ada.syncOriginal()                  // takes the current values as the row's
```

### Hooks

Override these on a model; throw from a `before` hook to stop the change.

```grav
class User extends Model {
    ...
    fn beforeSave() { self.email = Str.lower(Str.trim(self.email)) }
    fn beforeDelete() { if (self.role == "owner") { throw new StateError("the owner stays") } }
    fn afterCreate() { print("welcome, " + self.name) }
}
```

They are `beforeSave`, `afterSave`, `beforeCreate`, `afterCreate`,
`beforeUpdate`, `afterUpdate`, `beforeDelete` and `afterDelete`. A save of a
new object runs, in order: the behaviors' `saving`, `beforeSave`, `creating`,
`beforeCreate`, the INSERT, `afterCreate`, `created`, `afterSave`, `saved` (an
update the same, with `updating`, `beforeUpdate`, `afterUpdate` and `updated`).
A delete runs `beforeDelete`, `deleting`, the DELETE (or the soft delete's
UPDATE), `deleted`, `afterDelete`; `forceDelete()` runs the same.

Every save Orbit makes of a model runs them: its own `save()`, `create`,
`update`, `push`, `firstOrCreate` and `updateOrCreate`, and the saves that
relations and factories make. A query's `update` and `delete` change rows
without loading them, so they run no hooks.

`u.saveQuietly()` saves without any of them, and without the behaviors'
lifecycle hooks (so `@Uuids` fills nothing in); timestamps are still set.

### $touches: touching a related row's timestamp

`@Touches("relation", ...)` on a model touches the named relation's
`updatedAt` every time it saves — so saving a comment can bump its post's:

```grav
@Touches("post")
class Comment extends Model implements HasTimestamps {
    public id: long = 0
    public postId: long = 0
    public body: string = ""
    fn post() -> BelongsTo<Post> { return self.belongsTo() }
}

comment.body = "edited"
comment.save()              // post.updatedAt is now, too
```

It is a raw `UPDATE` through the relation's own query — not a load and a
`save()` — so it works for `hasMany`, `belongsToMany` and `morphMany` too
(every matching row, none of them loaded, and no hooks run on them), as well
as `belongsTo`, `hasOne`, `morphOne` and `morphTo`:

```grav
@Touches("spokes")
class Hub extends Model {
    public id: long = 0
    fn spokes() -> HasMany<Spoke> { return self.hasMany() }
}

hub.save()                  // every spoke's updatedAt is now, in one UPDATE
```

Nothing happens when the relation has no matching row, or its related class
has no `updatedAt`.

### Prunable: deleting old rows in batches

A model implementing `fn prunable() -> Query<Self>` can prune itself:
`Model.prune(chunk = 1000)` runs that query a chunk at a time, calling the
optional `fn pruning()` on each match before `forceDelete()`-ing it (even for
a `@SoftDeletes` class: prune removes rows for good), and gives how many it
removed.

```grav
class Reservation extends Model {
    public id: long = 0
    public expiresAt: DateTime = DateTime.now()
    // Rows expired for a week.
    fn prunable() -> Query<Reservation> { return Reservation.where("expiresAt", "<", DateTime.now().addDays(-7)) }
    fn pruning() { Log.info("pruning reservation ${self.id}") }
}

Reservation.prune()                 // run it from a schedule, or a maintenance command
```

A class with no `prunable()` method is a `StateError` naming it.

### Serialization

```grav
let m = user.toMap()                // field name -> value; @Hidden fields left out
let json = user.toJson()            // DateTime as ISO text, Decimal as a string, Bytes as hex
user.only(["name", "email"])        // a map of just these
user.except(["age"])                // all but these
user.makeHidden(["email"]).toJson() // hide fields on this object
user.makeVisible(["secret"]).toMap() // show @Hidden ones on this object
```

Loaded relations are in the map too (a model as a map, a list as a list of
maps), and so are the extra columns a query selected (`posts_count`).

### Accessors, mutators and casts

Grav properties are Orbit's accessors and mutators. A getter marked
`@Appended` (or named by `@Appends(...)` on the class) is put into `toMap` and
`toJson`, and a setter is what `fill`, `create` and `update` call for its name:

```grav
@Appends("initials")
class Person extends Model {
    public id: long = 0
    public first: string = ""
    public last: string = ""

    @Appended get fullName() -> string { return self.first + " " + self.last }
    set fullName(v: string) {
        let i = Str.indexOf(v, " ")
        self.first = v[..i]
        self.last = v[i + 1..]
    }
    get initials() -> string { return self.first[..1] + self.last[..1] }
    get shout() -> string { return Str.upper(self.fullName) }       // not in toMap
}

let p = Person.create(fields("fullName", "Ada Lovelace"))   // the setter fills first and last
p.toMap()                          // {id: 1, first: "Ada", last: "Lovelace", fullName: "Ada Lovelace", initials: "AL"}
p.append(["shout"]).toJson()       // any other getter, for this object
p.makeHidden(["initials"])         // hides an appended one, as it hides a field
```

A setter marked `@Guarded` is left alone by mass assignment, as a field is.
Properties are not columns: keep the value in fields, and compute or convert
it in the accessors.

**Casts.** A field's type is its cast for the types Orbit maps (numbers, bools,
strings, enums, `DateTime`, `Decimal`, `Bytes`, `JsonValue`, `T?`). For any
other type, `@Cast("name")` names a `Cast` that turns the column's value into
the field's and back. `json` and `csv` are built in:

```grav
class Money {
    public cents: long
    constructor(cents: long) { self.cents = cents }
}
class MoneyCast extends Cast {
    fn get(value: any) -> any { return new Money(value as long) }    // column -> field
    fn set(value: any) -> any { return (value as Money).cents }      // field -> column
    fn column() -> string { return "long" }                          // the column's kind (createTable, Schema)
}
Casts.register("money", new MoneyCast())                             // at start-up, before the class is used

class Order extends Model {
    public id: long = 0
    @Cast("money") public total: Money = null
    @Cast("json") public options: HashMap<string, any> = null       // JSON text: objects as maps, arrays as Array<any>
    @Cast("csv") public tags: Array<string> = null                  // "a,b,c"
}

let o = Order.find(1)
o.options.put("gift", true)       // a change inside a cast value counts:
o.isDirty("options")              // true, so save() writes it
```

A null stays null both ways. The model keeps a cast field's snapshot as its
column has it, so changing the map or list in place shows in `isDirty` and is
saved; `getOriginal` gives the field's form back. A `@Cast` name no cast is
registered under is a `StateError` naming the field, the first time the class
is used.

## Behaviors (model traits)

A behavior is code a class gets by wearing a decorator, as `@SoftDeletes` gives
soft deletes. Write one by extending `Behavior` and overriding the hooks you
need, register it under its decorator's name, and put the decorator on models:

```grav
class Sluggable extends Behavior {
    // Before each save: slug = the source field (@Sluggable("title")), lower-case, dashed.
    fn saving(m: Model, d: Decorator) {
        let info = ClassInfo.of(m)
        let text = "${info.field(d.text(0)).get(m)}"
        info.field("slug").set(m, Str.replace(Str.lower(Str.trim(text)), " ", "-"))
    }
}

class Published extends Behavior {
    // A global scope: every query of the class sees only published rows.
    fn apply(q: Builder, map: TableMap, d: Decorator) { q.where("published", true) }
}

class Audited extends Behavior {
    public log: Array<string> = new Array<string>()
    fn created(m: Model, d: Decorator) { self.log.push("created " + ClassInfo.of(m).simpleName()) }
    fn deleting(m: Model, d: Decorator) { self.log.push("deleting " + ClassInfo.of(m).simpleName()) }
}

fn main() {
    Behaviors.register("Sluggable", new Sluggable())
    Behaviors.register("Published", new Published())
    Behaviors.register("Audited", new Audited())
    ...
}

@Audited
class Content extends Model {
    public id: long = 0
    public title: string = ""
}

@Sluggable("title") @Published @Uuids
@Table("articles")
class Article extends Content {          // wears @Audited too, from its base class
    public slug: string = ""
    public uuid: string = ""
    public published: bool = false
}

Article.count()                                    // published ones only
Article.withoutScope("Published").count()          // every article
Article.query().withoutScopes().count()            // without any behavior's scope
```

**The hooks.** Each takes the model and the decorator that put the behavior on
its class, whose arguments it can read (`d.text(0)`, `d.get("name")`,
`d.flag("strict", false)`):

| Hook | Runs |
|------|------|
| `boot(map: TableMap, d)` | once, when a class wearing it is first used: change its mapping (`map.find("secret").hidden = true`) |
| `apply(q: Builder, map: TableMap, d)` | on every query of the class, relation subqueries included: a global scope |
| `saving`, `saved` | around every save |
| `creating`, `created` | around an insert |
| `updating`, `updated` | around an update |
| `deleting`, `deleted` | around a delete (a soft one too) |
| `retrieved` | after a row is read into a model |

Throw from a `-ing` hook to stop the change. A decorator on a base class puts
the behavior on its subclasses too. One instance serves every class that wears
it. Register behaviors at start-up, before their classes are first used: a
class mapped before keeps what it had. `Behaviors.isRegistered(name)` says
whether one is.

**Built in:**

- `SoftDeletes`: `@SoftDeletes` or `@SoftDeletes("field")` (see above).
- `Timestamps`: on for every class unless it says `@NoTimestamps`;
  `@Timestamps("created", "updated")` names the fields.
- `Uuids`: `@Uuids`, or `@Uuids("field")`: a new row gets a random UUID (v4)
  in that string field (`uuid` by default) when it is empty.

Their classes are `SoftDeletesBehavior`, `TimestampsBehavior` and
`UuidsBehavior`, for extending.

### Traits: a behavior with its fields

A behavior's decorator says what to do; the fields it works on must still be
written in each model. A Grav `trait` carries both, so a model takes a behavior
in one word. Orbit has three:

| Trait | Gives the model |
|-------|-----------------|
| `SoftDeletes` | `deletedAt: DateTime?` and `@SoftDeletes` |
| `HasTimestamps` | `createdAt: DateTime?` and `updatedAt: DateTime?` |
| `HasUuids` | `uuid: string` and `@Uuids` |

```grav
class Post extends Model implements SoftDeletes, HasTimestamps, HasUuids {
    public id: long = 0
    public title: string = ""
}
```

Write your own the same way: a trait that wears your behavior's decorator and
declares the fields the behavior needs. A field the model declares itself wins
over the trait's, and a subclass gets the trait's members from its base.

```grav
@Sluggable("title")
trait HasSlug {
    public slug: string = ""
}

class Article extends Model implements HasSlug {
    public id: long = 0
    public title: string = ""
}
```

A trait's fields, helpers and decorators are copied into the model when it is
compiled, so reflection, mapping, mass assignment and every behavior see them
as the model's own. Traits with fields need a Grav compiler with trait state
(November 2026 or later).

### Observers

An observer is a `Behavior` attached to a class by a call instead of a
decorator — the same hooks (`saving`, `created`, `deleting`, ...), for code
that should not have to change the model:

```grav
class SendsWelcomeMail extends Behavior {
    fn created(m: Model, d: Decorator) { Mail.send((m as User).email, "Welcome!") }
}
User.observe(new SendsWelcomeMail())        // runs for User, and any subclass
```

`d` is a placeholder (`d.name` is `"Observer"`): an observer has no decorator
of its own to read arguments from. Register observers once, at start-up;
`User.observe(...)` works even after `User`'s mapping has already been built.

Beyond the hooks [Behaviors](#behaviors-model-traits) already lists
(`saving`, `creating`, ...), a soft-deleting model's full lifecycle is there
too: `trashed` (after a soft delete marks the row), `forceDeleting` and
`forceDeleted` (around a `forceDelete`, alongside the usual `deleting` and
`deleted`), and `restoring` and `restored` (around undoing a soft delete).

## Repository: classes that do not extend Model

`Repository<T>` gives the same saving and querying to a class with no base,
on a connection you name:

```grav
class Point {
    public id: long = 0
    public x: float = 0.0
    public y: float = 0.0
}

let points = new Repository<Point>(DB.connection())
points.createTable()
let p = new Point()
p.x = 1.5
points.save(p)                                   // INSERT; p.id filled in
p.y = 2.0
points.save(p)                                   // UPDATE
let near = points.query().where("x", "<", 2.0).orderBy("y").get()
let all = points.all()
points.saveAll(more)                             // in one transaction
points.delete(p)
```

It has `query()`, `where` (two forms), `all`, `find`, `findOrFail`, `count`,
`save`, `saveAll`, `delete`, `createTable`, `dropTable` and `tableName`. The
mapping and decorators are the same, and timestamps and soft deletes work;
change tracking, hooks, behaviors' lifecycle hooks and relations need a
`Model` (a plain object's save writes every column).

## The DB facade

**Transactions.**

```grav
let amount = Decimal.parse("25.00")
DB.transaction(fn() {
    let from = Account.findOrFail(1)
    let to = Account.findOrFail(2)
    from.balance = from.balance - amount
    to.balance = to.balance + amount
    from.save()
    to.save()
})                                     // committed; rolled back when it throws (and the exception goes on)

DB.transaction("reports", fn() { ... })        // on a named connection

DB.beginTransaction()
User.create(fields("name", "Tmp"))
DB.rollBack()                                  // or DB.commit()
DB.inTransaction()
```

A transaction inside another is a savepoint: only its own changes are undone.
`beginTransaction`, `commit`, `rollBack` and `inTransaction` take a connection
name too.

**Retries.** `DB.transaction(body, attempts)` runs it again, rolling back
first, when it fails on a deadlock or a serialization conflict — any other
error, or the last attempt's, goes on unchanged. Each retry waits a little
longer than the last.

```grav
DB.transaction(fn() {
    let acct = Account.findOrFail(1)
    acct.balance -= amount
    acct.save()
}, 3)                                  // up to 3 attempts total
DB.transaction("reports", body, 3)     // on a named connection
```

`DB.isDeadlock(e, name)` is the check itself, for code that wants to retry by
hand: PostgreSQL's or the standard's SQLSTATE (`40001` serialization failure,
`40P01` deadlock_detected), MySQL's own codes (1213 deadlock, 1205 lock wait
timeout), and, for SQLite — which has no SQLSTATE — `SQLITE_BUSY` or
`SQLITE_LOCKED` (5, 6) on the connection named `name`. The name tells it which
driver's codes apply; without one (or with a name nothing is connected under)
it falls back to the MySQL codes.

**Read and write connections.** `DB.connect(write, read, name)` sends writes
and transactions to `write`, but a model's reads (and `DB.select`,
`selectOne`, `scalar`) to `read` — a read replica — except inside a
transaction, where everything stays on `write` (the replica may not have its
own writes yet):

```grav
DB.connect(MySql.open(writeUrl), MySql.open(readUrl))
User.all()                            // from the replica
DB.transaction(fn() { User.create(fields("name", "Ada")) })   // writes, and reads inside it, go to write
```

A query that names its own connection (`.on(db)`, a `@Connection`) always uses
exactly that one.

**Several read replicas.** Give `connect` a list, or add them one at a time:
reads take them in turn (round robin), pass over any that is closed, and use
the write connection when none is open. `DB.stickyReads(seconds)` keeps a
connection's reads on its writer for a while after each write, so a program
reads back what it just wrote even while the replicas lag behind:

```grav
DB.connect(MySql.open(writeUrl), [MySql.open(replica1), MySql.open(replica2)])
DB.addReadReplica(MySql.open(replica3))
DB.stickyReads(2.0)                   // 2 s after a write, reads stay on the writer
DB.readReplicas()                     // the three of them
```

**One connection per thread.** A grav-db connection is for one thread at a
time, so a thread that uses Orbit while others do gives itself its own (and, if
wanted, its own replica): until it calls `DB.leaveThread()`, its models and
queries use them, and other threads keep theirs or the shared one.

```grav
Thread.spawn(fn() {
    DB.useOnThisThread(MySql.open(writeUrl), MySql.open(readUrl))
    Order.create(fields("total", 10))
    DB.leaveThread()
})
```

The query log, the query cache, N+1 counting and the model mappings are shared
by every thread (each behind its own lock); set them up before starting
threads.

**Raw SQL**, with `?` arguments, on the default connection:

| Call | Gives |
|------|-------|
| `DB.select(sql, args)` | a `ResultSet` |
| `DB.selectOne(sql, args)` | the first `Row`, or null |
| `DB.scalar(sql, args)` | the first column of the first row, or null |
| `DB.insert(sql, args)` | the new row's id |
| `DB.update(sql, args)`, `DB.delete(sql, args)` | the rows changed |
| `DB.statement(sql, args)` | the rows changed, for any statement |
| `DB.unprepared(sql)` | runs statements without arguments (a script) |

```grav
for (row in DB.select("SELECT name, age FROM users WHERE age > ?", [18])) {
    print(row.getString("name"))
}
let n = DB.scalar("SELECT COUNT(*) FROM users")
DB.update("UPDATE users SET active = ? WHERE age < ?", [false, 13])
```

**Tables without a model.** `DB.table(name)` is a `TableQuery`: the query
builder's clauses (with column names, and no relation conditions) and its
`Builder` answers (`count`, `exists`, `sum`, `pluck`, `value`, `update`,
`delete`, `increment`, `upsert`, ...), with `get`, `first`, `find`, `insert` and
`insertMany` giving and taking grav-db `Row`s and maps.

```grav
let names = DB.table("users").where("age", ">", 18).orderBy("name").pluck("name")
let rows = DB.table("users").whereIn("id", [1, 2]).get()       // a ResultSet
let row = DB.table("users").find(1)                             // a Row, or null
let id = DB.table("logs").insert(fields("level", "info", "message", "started"))
DB.table("logs").insertMany(batch)                              // batched; how many
DB.table("users").where("id", 5).update(fields("active", false))
DB.table("logs").where("level", "debug").delete()
DB.table("pages").where("slug", "home").increment("hits")
```

## The schema builder

```grav
Schema.create("posts", fn(t: Blueprint) {
    t.id()
    t.foreignId("user_id").constrained().cascadeOnDelete()
    t.varchar("title")
    t.varchar("slug", 100).unique()
    t.text("body").nullable()
    t.boolean("published").defaultValue(false)
    t.integer("views").defaultValue(0)
    t.decimal("price", 10, 2)
    t.json("meta").nullable()
    t.timestamps()
    t.softDeletes()
    t.index("title")
})

Schema.table("posts", fn(t: Blueprint) {          // Schema.alter is the same
    t.varchar("subtitle").nullable()
    t.renameColumn("body", "content")
    t.dropColumn("price")
})

Schema.rename("posts", "articles")
Schema.drop("articles")
Schema.dropIfExists("articles")
```

**Looking at the database.** `Schema.hasTable(name)`, `Schema.hasColumn(table,
column)`, `Schema.hasColumns(table, columns)`, `Schema.columns(table)` (the
names, in order) and `Schema.getTables()`. `Schema.dropColumns(table,
columns)` drops columns, and `Schema.dropAllTables()` drops every table.

**Foreign-key checks.** `Schema.disableForeignKeyConstraints()`,
`Schema.enableForeignKeyConstraints()`, and
`Schema.withoutForeignKeyConstraints(fn() { ... })` (PostgreSQL defers them to
the end of the transaction instead). SQLite checks foreign keys only on a
connection that turned them on: `Schema.enableForeignKeyConstraints()` does.

**Another connection.** `Schema` works on the default connection;
`Schema.createOn(db, table, f)`, `Schema.tableOn(db, table, f)` and
`Schema.hasTableOn(db, table)` take one.

**From a model.** `User.createTable()` makes the model's table from its fields
(when it does not exist yet), `User.dropTable()` drops it. The column types
for each field type:

| Field | SQLite | MySQL | PostgreSQL |
|-------|--------|-------|------------|
| numbered `int` / `long` id | `INTEGER PRIMARY KEY` | `INT` / `BIGINT UNSIGNED AUTO_INCREMENT` | `SERIAL` / `BIGSERIAL` |
| `int`, enum | `INTEGER` | `INT` | `INTEGER` |
| `long` | `INTEGER` | `BIGINT` | `BIGINT` |
| `float` | `REAL` | `DOUBLE` | `DOUBLE PRECISION` |
| `bool` | `BOOLEAN` | `BOOLEAN` | `BOOLEAN` |
| `string` | `TEXT` | `TEXT` (`VARCHAR(255)` when unique or the id) | `TEXT` |
| `string` with `length` | `VARCHAR(n)` | `VARCHAR(n)` | `VARCHAR(n)` |
| `DateTime` | `DATETIME` | `DATETIME(6)` | `TIMESTAMPTZ` |
| `Decimal` | `DECIMAL` | `DECIMAL(38, 10)` | `NUMERIC` |
| `Decimal` with `precision` | `DECIMAL(p, s)` | `DECIMAL(p, s)` | `DECIMAL(p, s)` |
| `Bytes` | `BLOB` | `LONGBLOB` | `BYTEA` |
| `JsonValue` | `JSON` | `JSON` | `JSONB` |
| `any` | `TEXT` | `TEXT` | `TEXT` |

It makes no foreign keys or indexes beyond `UNIQUE`: use a `Blueprint` (in a
migration) for those.

### Column types

| Blueprint | SQLite | MySQL | PostgreSQL |
|-----------|--------|-------|------------|
| `id(name = "id")`, `bigIncrements(name)` | `INTEGER PRIMARY KEY AUTOINCREMENT` | `BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY` | `BIGSERIAL PRIMARY KEY` |
| `increments(name)` | `INTEGER PRIMARY KEY AUTOINCREMENT` | `INT UNSIGNED AUTO_INCREMENT PRIMARY KEY` | `SERIAL PRIMARY KEY` |
| `foreignId(name)` | `INTEGER` | `BIGINT UNSIGNED` | `BIGINT` |
| `integer`, `unsignedInteger` | `INTEGER` | `INT` (`UNSIGNED`) | `INTEGER` |
| `bigInteger`, `unsignedBigInteger` | `INTEGER` | `BIGINT` (`UNSIGNED`) | `BIGINT` |
| `smallInteger`, `unsignedSmallInteger` | `INTEGER` | `SMALLINT` (`UNSIGNED`) | `SMALLINT` |
| `tinyInteger`, `unsignedTinyInteger` | `INTEGER` | `TINYINT` (`UNSIGNED`) | `SMALLINT` |
| `decimal(name, precision = 8, scale = 2)` | `DECIMAL(p, s)` | `DECIMAL(p, s)` | `NUMERIC(p, s)` |
| `real(name)` | `REAL` | `FLOAT` | `REAL` |
| `doublePrecision(name)` | `REAL` | `DOUBLE` | `DOUBLE PRECISION` |
| `boolean(name)` | `BOOLEAN` | `BOOLEAN` | `BOOLEAN` |
| `varchar(name, length = 255)` | `VARCHAR(n)` | `VARCHAR(n)` | `VARCHAR(n)` |
| `fixedChar(name, length = 255)` | `CHAR(n)` | `CHAR(n)` | `CHAR(n)` |
| `text`, `mediumText`, `longText` | `TEXT` | `TEXT`, `MEDIUMTEXT`, `LONGTEXT` | `TEXT` |
| `json(name)` | `JSON` | `JSON` | `JSONB` |
| `binary(name)` | `BLOB` | `LONGBLOB` | `BYTEA` |
| `uuid(name = "uuid")`, `foreignUuid(name)` | `TEXT` | `CHAR(36)` | `UUID` |
| `enumeration(name, values)` | `VARCHAR(255)` with a `CHECK` | `ENUM(...)` | `VARCHAR(255)` with a `CHECK` |
| `date(name)` | `DATE` | `DATE` | `DATE` |
| `dateTime`, `timestamp`, `timestampTz` | `DATETIME` | `DATETIME(6)` | `TIMESTAMPTZ` |
| `time(name)` | `TIME` | `TIME` | `TIME` |
| `year(name)` | `INTEGER` | `YEAR` | `SMALLINT` |

And the shorthands: `timestamps()` (nullable `created_at` and `updated_at`,
which a model's `createdAt` and `updatedAt` fill), `softDeletes(name =
"deleted_at")`, `rememberToken()` (a nullable `remember_token VARCHAR(100)`),
`ipAddress(name = "ip_address")` (`VARCHAR(45)`), `macAddress(name =
"mac_address")` (`VARCHAR(17)`), and `morphs(name)`, `nullableMorphs(name)`
and `uuidMorphs(name)` (`<name>_id` and `<name>_type`, indexed together).

### Column modifiers

Each returns the column, so they chain:

| Modifier | Does |
|----------|------|
| `nullable()`, `nullable(false)` | NULL allowed (columns are `NOT NULL` otherwise) |
| `defaultValue(v)` | a default: a number, bool, string or null |
| `defaultRaw(sql)`, `useCurrent()` | a default in SQL; `CURRENT_TIMESTAMP` |
| `unique()`, `index()`, `primary()` | a unique column, an index on it, the primary key |
| `unsigned()` | `UNSIGNED` (MySQL) |
| `change()` | in `Schema.table`: change the existing column to this definition (MySQL, PostgreSQL) |

### Foreign keys

```grav
t.foreignId("user_id").constrained()                      // REFERENCES users (id): the name without _id, plural
t.foreignId("author_id").constrained("users")             // another table; constrained("users", "uid") another column
t.foreignId("owner_id").references("id").on("accounts")   // the same, in two steps
t.foreignId("shop_id").constrained().onDelete("cascade").onUpdate("cascade")   // cascade, set null, restrict, no action, set default
t.foreignId("team_id").nullable().constrained().nullOnDelete()   // also cascadeOnDelete, restrictOnDelete, cascadeOnUpdate
```

A foreign key is named `<table>_<column>_foreign`, as `dropForeign(column)`
expects.

### Indexes and drops

```grav
Schema.table("posts", fn(t: Blueprint) {
    t.index("title")                     // posts_title_index
    t.index(["user_id", "created_at"])   // posts_user_id_created_at_index
    t.unique(["user_id", "slug"])        // posts_user_id_slug_unique
    t.fullText(["title", "body"])        // for whereFullText (MySQL FULLTEXT, PostgreSQL GIN; none on SQLite)
})
Schema.table("posts", fn(t: Blueprint) {
    t.dropIndex("posts_title_index")
    t.dropUnique(["user_id", "slug"])
    t.dropForeign("user_id")
    t.dropColumn("subtitle")
    t.dropColumns(["a", "b"])
    t.dropTimestamps()
    t.dropSoftDeletes()
    t.dropRememberToken()
    t.dropMorphs("commentable")
})
```

`t.primary(["user_id", "role_id"])` in `Schema.create` makes a composite
primary key.

SQLite cannot change a column, or add or drop a foreign key on an existing
table: Orbit says so with a `StateError` (make a new table and copy the rows).

## Migrations

A migration is a class with `up` and `down`. A `Migrator` runs the ones not
run yet, in the order they were added, and records them in a `migrations`
table:

```grav
class CreateUsers extends Migration {
    fn up() {
        Schema.create("users", fn(t: Blueprint) {
            t.id()
            t.varchar("name")
            t.varchar("email", 190).unique()
            t.timestamps()
        })
    }
    fn down() { Schema.dropIfExists("users") }
}

class CreatePosts extends Migration {
    fn up() { Schema.create("posts", fn(t: Blueprint) { t.id(); t.foreignId("user_id").constrained(); t.varchar("title"); t.timestamps() }) }
    fn down() { Schema.dropIfExists("posts") }
}

let m = new Migrator()
m.add(new CreateUsers()).add(new CreatePosts())
m.migrate()          // runs those not run yet, as one batch; their names
m.status()           // ["CreateUsers: ran (batch 1)", "CreatePosts: ran (batch 1)"]
m.rollback()         // undoes the last batch, newest first; rollback(2) the last two
m.reset()            // undoes every migration run
m.refresh()          // reset, then migrate
m.tryMigrate()       // migrate, or null while another process is migrating
```

Each migration runs in a transaction with its record. A migration's name is
its class name (override `fn name() -> string` for another); `m.table` names
the table that records them, and `m.on(db)` keeps that record on another
connection. Rolling back a migration that is not in the `Migrator` is a
`StateError`.

**Several servers at once.** Several servers often start together in a
deploy, and each may run `migrate`. `migrate`, `rollback`, `reset` and
`refresh` hold a lock while they work, so the other servers wait (up to
`m.lockWaitSeconds`, 600, then `StateError`). Once the lock is free they run
what is still pending, which is usually nothing. `tryMigrate()` doesn't wait:
it returns null while another process holds the lock. The lock is:

- MySQL: `GET_LOCK`
- PostgreSQL: an advisory lock

Both are freed if the process dies. Elsewhere (SQLite) the lock is a row in
`<table>_lock`, taken over when the process that holds it is gone from this
host, or after `m.lockStaleSeconds` (3600). A unique index on the migration
name is the backstop: if two runs ever get past the lock, the second one's
record is refused. On PostgreSQL and SQLite its schema changes roll back with
it; MySQL commits schema changes at once, so there they stay.

## Factories and seeders

**Fake** makes up values: `name()`, `firstName()`, `lastName()`, `userName()`,
`email()`, `uniqueEmail()` (never the same twice from one `Fake`), `word()`, `sentence(words =
6)`, `paragraph(sentences = 3)`, `city()`, `phone()`, `url()`, `number(min,
max)` (a `long`), `real(min, max, decimals = 2)`, `decimal(min, max, scale =
2)` (a `Decimal`, for money), `boolean(percent = 50)`, `pick(list)`,
`pastDate(days = 365)`, `futureDate(days = 365)` and `uuid()`. Seeded, it gives
the same values each run: `Fake.seed(42)` reseeds the shared one, `new
Fake(42)` makes another.

**Factory<T>** makes objects from a definition:

```grav
let definition = fn(f: Fake) -> HashMap<string, any> {
    return fields("name", f.name(), "email", f.uniqueEmail(), "age", f.number(18, 90))
}
let users = new Factory<User>(definition)

let one = users.create()                              // one User, saved
let draft = users.make()                              // one, not saved
let values = users.raw()                              // the fields one would get
let pinned = users.create(fields("name", "Ada"))      // with overrides, set last

let ten = new Factory<User>(definition).count(10).createMany()   // saved in one transaction; makeMany: not saved
let admins = new Factory<User>(definition).state(fields("role", "admin")).count(3).createMany()
let ranked = new Factory<User>(definition)
    .sequence(fn(i: int) -> HashMap<string, any> => fields("name", "User ${i}"))   // from the object's number: 0, 1, ...
    .afterCreating(fn(u: User) { u.posts().create(fields("title", "First post")) })
    .using(new Fake(42))                                                            // a seeded Fake of its own
    .count(5)
    .createMany()
```

`state` also takes a function of the `Fake` (`state(fn(f: Fake) ->
HashMap<string, any> => fields("age", f.number(13, 17)))`). A factory sets
every field it is given, `@Guarded` ones too. `count`, `state`, `sequence`,
`afterCreating` and `using` change the factory and return it, so a state stays
on it: start a new `Factory` for each variant.

**Seeders** put data in the database:

```grav
class UserSeeder extends Seeder {
    fn run() {
        User.create(fields("name", "Ada", "email", "ada@example.com"))
        let users = new Factory<User>(fn(f: Fake) -> HashMap<string, any> => fields("name", f.name(), "email", f.uniqueEmail()))
        users.count(20).createMany()
    }
}
class DatabaseSeeder extends Seeder {
    fn run() { self.call(new UserSeeder()); self.call(new PostSeeder()) }
}

Seeder.seed(new DatabaseSeeder())        // in one transaction
```

## Coming from Eloquent

Most of Eloquent's names are here and mean the same. What differs:

- **Relations are typed methods**, and you call them: `user.posts().get()`
  where Eloquent reads `$user->posts`. After `with("posts")`, `get()` gives the
  loaded list without a query. The type argument comes from the return type;
  give it (`self.belongsToMany::<Role>()`) when you chain on.
- **Statics forward only the common query methods** (see
  [the list](#what-the-static-methods-offer)); the rest start with
  `User.query()`.
- **Names are checked.** A name in a query must be a field or column of the
  model (a typo is a `ValueError` naming the class, before any SQL); in
  `DB.table` queries, and for tables in joins, a plain identifier. SQL goes in
  the `Raw` methods: `whereRaw`, `orWhereRaw`, `selectRaw`, `orderByRaw`,
  `havingRaw`.
- **Field names in camelCase.** Queries take field names (`createdAt`) as well
  as columns (`created_at`); `toMap` and `toJson` use field names.
- **Maps are `fields(...)`**: `User.create(fields("name", "Ada", "age", 36))`.
- **No `$fillable`, `$hidden`, `$casts`**: every field is fillable but
  `@Guarded` ones (and a numbered id); `@Hidden` hides; a field's type is its
  cast, and `@Cast("name")` covers other types. Accessors and mutators are
  [properties](#accessors-mutators-and-casts): `get` and `set`.
- **Local scopes are `@Scope` methods**, applied by name: `User.scope("popular", [100])`
  for Eloquent's `User::popular(100)`. Global
  scopes and traits are [behaviors](#behaviors-model-traits), put on by
  decorators; hooks are methods on the model or a behavior.
  [Observers](#observers) are behaviors attached by a call (`User.observe(...)`)
  instead of an event dispatcher.
- **Constraints in `with` are a second argument**: `with("posts", fn(q: Builder) { ... })`
  for `with(['posts' => fn])`, one relation per call.
- **Counts and aggregates** are read with `countOf("posts")` and
  `extra("posts_sum_views")`, a pivot column with `role.pivot("level")`.
- **Morph types** hold the class's simple name (`Post`) or its `@MorphName`,
  not a namespaced class name; `Orbit.morphMap` maps others. A `morphTo` is
  queried with `whereHasMorph(name, [types], f)`, not `whereHas`.
- **Errors**: `findOrFail` and `firstOrFail` throw std's `NotFound`; `sole`
  `NotFound` or `StateError`.
- **Numbers**: `sum` gives a `Decimal`, `avg` a `float`, `count` a `long`.
- **DECIMAL on SQLite is a float.** SQLite has no exact decimal type: it keeps
  a DECIMAL column's values as floating point, and Orbit reads them back as
  `Decimal`s of that float. Money is exact on MySQL and PostgreSQL.
- **`chunk` and `chunkById` order by the id**, replacing any order given.
- **`replicate()` gives a `Model`**: cast it (`u.replicate() as User`).
- **Factories change themselves**: `state` and `count` return the same
  factory, not a copy.
- **Migrations are classes you add to a `Migrator`**, named by their class;
  there are no migration files or command line. `Model.createTable()` makes a
  table straight from a model.
- **The schema builder's names** differ where Eloquent's are Grav's own type
  names and keywords: `varchar` (Eloquent's `string`), `fixedChar` (`char`),
  `real` (`float`), `doublePrecision` (`double`), `enumeration` (`enum`),
  `defaultValue` (`default`).
- **Timestamps are optional by presence**: a model without `createdAt` and
  `updatedAt` fields has none, without `$timestamps = false`.
- **Connections are objects**: `DB.connect(Sqlite.open(...))`, no
  configuration file.

## Tests

```bash
grav test tests/orbit.grav
grav test tests/diagnostics.grav
ORBIT_DB='mysql://user:password@localhost/orbit_test' grav test tests/orbit.grav
ORBIT_DB='postgresql://user:password@localhost/orbit_test' grav test tests/orbit.grav
```

Without `ORBIT_DB` they run on SQLite in memory; with a `mysql://` (or
`mariadb://`) or `postgresql://` URL, on that server. They cover models and
mass assignment, the query builder, every kind of relation (polymorphic and
through ones too), eager loading, `whereHas` and `withCount`, aggregates of
relations, pivot columns, soft deletes, timestamps, change tracking, upserts,
transactions, behaviors and their scopes, the schema builder, migrations, and
factories and seeders.

`tests/diagnostics.grav` covers the query log, the debugbar, N+1 detection,
remembered results and their invalidation, read replicas and per-thread
connections (on SQLite files in the temporary directory).

**Fuzzing.** `tests/fuzz.grav` runs random query trees (and/or with SQL's
precedence, nested and negated groups, `IN` with empty lists, `BETWEEN`,
`LIKE` with `%` and `_`, NULLs, and values with quotes, backslashes, SQL
comment marks and non-ASCII text) both as SQL and over an in-memory copy of the
table, with random writes in between, checking each answer uncached and through
`remember()`; random names, operators and directions must be refused before any
SQL is sent; random values must round-trip through every field type.
`ORBIT_FUZZ_SEED` and `ORBIT_FUZZ_ROUNDS` (300) pick a longer run:

```bash
grav test tests/fuzz.grav
ORBIT_FUZZ_SEED=7 ORBIT_FUZZ_ROUNDS=5000 grav test tests/fuzz.grav
```

**Concurrent load and soak.** `tests/stress/load.grav` runs THREADS threads
(8), each with its own write and read connection on one SQLite file in WAL
mode, through OPS operations each (1500): transfers in retried transactions,
in-place increments, remembered and plain reads, eager and lazy loads and
inserts, with the log, cache and N+1 counting on; the totals must add up at the
end. `tests/stress/soak.grav` does the same for SECONDS (600), pruning old rows
as it goes, and fails if memory keeps growing (the end may exceed a quarter of
the way in by 25%, or 8 MB). Build them with `--release`, or with `--race` for
ThreadSanitizer:

```bash
grav tests/stress/load.grav --release -o /tmp/orbit_load --emit bin && /tmp/orbit_load 8 1500
grav tests/stress/soak.grav --release -o /tmp/orbit_soak --emit bin && /tmp/orbit_soak 600 4
grav tests/stress/load.grav --race -o /tmp/orbit_race --emit bin && /tmp/orbit_race 4 300
```

The tests drop and make their own tables (`users`, `posts`, `comments`,
`roles`, `tags`, `migrations` and others) in the database the URL names: give
them a database of their own. A throwaway PostgreSQL needs no setup beyond
the server's own programs:

```bash
initdb -D /tmp/pg -U grav --auth=trust && pg_ctl -D /tmp/pg -o "-k /tmp -p 54329" -w start
createdb -h /tmp -p 54329 -U grav orbit_test
ORBIT_DB='postgresql://grav@/orbit_test?host=/tmp&port=54329' grav test tests/orbit.grav
```

## License

MIT: see [LICENSE](LICENSE).
