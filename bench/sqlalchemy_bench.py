# Orbit's comparison: the same work as orbit_bench.grav, in SQLAlchemy 2.0's ORM.
#   BENCH_DB=<url> python3 sqlalchemy_bench.py
import os, time
from datetime import datetime
from urllib.parse import urlparse, parse_qs, unquote
from sqlalchemy import create_engine, text, select, func, ForeignKey, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, Session, selectinload

class Base(DeclarativeBase): pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(190))
    age: Mapped[int]
    active: Mapped[bool]
    created_at: Mapped[datetime | None] = mapped_column(default=datetime.now)
    updated_at: Mapped[datetime | None] = mapped_column(default=datetime.now, onupdate=datetime.now)
    posts: Mapped[list["Post"]] = relationship(back_populates="user")

class Post(Base):
    __tablename__ = "posts"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(200))
    views: Mapped[int]
    created_at: Mapped[datetime | None]
    updated_at: Mapped[datetime | None]
    user: Mapped[User] = relationship(back_populates="posts")

N = 10000
url = os.environ.get("BENCH_DB", "")
if url == "":
    if os.path.exists("/tmp/sqlalchemy_bench.db"): os.remove("/tmp/sqlalchemy_bench.db")
    engine = create_engine("sqlite:////tmp/sqlalchemy_bench.db")
elif url.startswith("mysql://"):
    p = urlparse(url)
    engine = create_engine(f"mysql+mysqldb://{p.username}:{p.password}@{p.hostname}{p.path}?charset=utf8mb4".replace("*", "%2A"))
else:
    p = urlparse(url); q = parse_qs(p.query)
    engine = create_engine(f"postgresql+psycopg2://{p.username}@/{p.path.lstrip('/')}?host={q['host'][0]}&port={q['port'][0]}")

d = engine.dialect.name
pk = "BIGSERIAL PRIMARY KEY" if d == "postgresql" else "BIGINT AUTO_INCREMENT PRIMARY KEY" if d == "mysql" else "INTEGER PRIMARY KEY AUTOINCREMENT"
ts = "TIMESTAMP" if d == "postgresql" else "DATETIME"
with engine.begin() as c:
    c.execute(text("DROP TABLE IF EXISTS posts")); c.execute(text("DROP TABLE IF EXISTS users"))
    c.execute(text(f"CREATE TABLE users (id {pk}, name VARCHAR(100) NOT NULL, email VARCHAR(190) NOT NULL, age INTEGER NOT NULL, active BOOLEAN NOT NULL, created_at {ts} NULL, updated_at {ts} NULL)"))
    c.execute(text(f"CREATE TABLE posts (id {pk}, user_id BIGINT NOT NULL, title VARCHAR(200) NOT NULL, views INTEGER NOT NULL, created_at {ts} NULL, updated_at {ts} NULL)"))
    c.execute(text("CREATE INDEX posts_user_id ON posts (user_id)")); c.execute(text("CREATE INDEX users_age ON users (age)"))

def phase(name, t): print(f"{name}\t{int((time.perf_counter() - t) * 1000)}")
total = time.perf_counter()

# 1. create, one model at a time (each flushed, so it has its id, as create() does)
t = time.perf_counter()
with Session(engine) as s, s.begin():
    for i in range(N):
        u = User(name=f"user {i}", email=f"user{i}@example.com", age=18 + i % 60, active=i % 3 != 0)
        s.add(u); s.flush()
phase("create", t)

t = time.perf_counter()
rows = [{"user_id": i // 5 + 1, "title": f"post {i}", "views": i % 1000} for i in range(N)]
with Session(engine) as s, s.begin():
    s.execute(Post.__table__.insert(), rows)
phase("bulk_insert", t)

t = time.perf_counter()
found = 0
with Session(engine) as s:
    for i in range(N):
        if s.get(User, (i * 7919) % N + 1) is not None: found += 1
phase("find", t)

t = time.perf_counter()
seen = 0
with Session(engine) as s:
    for i in range(1000):
        seen += len(s.scalars(select(User).where(User.active == True, User.age > 18 + i % 40).order_by(User.age).limit(50)).all())
        s.expunge_all()
phase("where", t)

t = time.perf_counter()
allc = 0
for i in range(5):
    with Session(engine) as s: allc += len(s.scalars(select(User)).all())
phase("all", t)

t = time.perf_counter()
with Session(engine) as s, s.begin():
    for u in s.scalars(select(User).order_by(User.id).limit(2000)).all():
        u.age = u.age + 1
phase("update", t)

t = time.perf_counter()
posts = 0
for i in range(5):
    with Session(engine) as s:
        for u in s.scalars(select(User).options(selectinload(User.posts)).order_by(User.id).limit(2000)).all(): posts += len(u.posts)
phase("eager", t)

t = time.perf_counter()
agg = 0.0
with Session(engine) as s:
    for i in range(1000):
        agg += s.scalar(select(func.count()).select_from(User).where(User.age > i % 60))
        agg += float(s.scalar(select(func.avg(User.age)).where(User.active == True)))
phase("aggregate", t)

phase("total", total)
print(f"check\t{found} {seen} {allc} {posts} {'true' if agg > 0 else 'false'}")
