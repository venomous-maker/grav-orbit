<?php
// Orbit's comparison: the same work as orbit_bench.grav, phase by phase.
//   BENCH_DB=<url> php eloquent_bench.php
require __DIR__ . '/vendor/autoload.php';

use Illuminate\Database\Capsule\Manager as DB;
use Illuminate\Database\Eloquent\Model;

class User extends Model {
    protected $guarded = [];
    protected $casts = ['active' => 'boolean', 'age' => 'integer'];
    public function posts() { return $this->hasMany(Post::class); }
}
class Post extends Model {
    protected $guarded = [];
}

$N = 10000;
$url = getenv('BENCH_DB') ?: '';
$db = new DB;
if ($url === '') {
    $db->addConnection(['driver' => 'sqlite', 'database' => '/tmp/eloquent_bench.db']);
    @unlink('/tmp/eloquent_bench.db'); touch('/tmp/eloquent_bench.db');
} elseif (str_starts_with($url, 'mysql://')) {
    $p = parse_url($url);
    $db->addConnection(['driver' => 'mysql', 'host' => $p['host'], 'database' => ltrim($p['path'], '/'),
        'username' => urldecode($p['user']), 'password' => urldecode($p['pass'] ?? ''), 'charset' => 'utf8mb4']);
} else {
    // postgresql://user[:pass]@[host]/db[?host=/socket/dir&port=N] (parse_url refuses an empty host)
    preg_match('#^postgres(?:ql)?://([^:@/]+)(?::([^@]*))?@([^/]*)/([^?]+)(?:\?(.*))?$#', $url, $m);
    parse_str($m[5] ?? '', $q);
    $db->addConnection(['driver' => 'pgsql', 'host' => $q['host'] ?? ($m[3] ?: 'localhost'), 'port' => $q['port'] ?? 5432,
        'database' => $m[4], 'username' => $m[1], 'password' => $m[2] ?? '']);
}
$db->setAsGlobal();
$db->bootEloquent();

$d = DB::connection()->getDriverName();
$id = $d === 'pgsql' ? 'BIGSERIAL PRIMARY KEY' : ($d === 'mysql' ? 'BIGINT AUTO_INCREMENT PRIMARY KEY' : 'INTEGER PRIMARY KEY AUTOINCREMENT');
$ts = $d === 'pgsql' ? 'TIMESTAMP' : 'DATETIME';
DB::statement('DROP TABLE IF EXISTS posts');
DB::statement('DROP TABLE IF EXISTS users');
DB::statement("CREATE TABLE users (id $id, name VARCHAR(100) NOT NULL, email VARCHAR(190) NOT NULL, age INTEGER NOT NULL, active BOOLEAN NOT NULL, created_at $ts NULL, updated_at $ts NULL)");
DB::statement("CREATE TABLE posts (id $id, user_id BIGINT NOT NULL, title VARCHAR(200) NOT NULL, views INTEGER NOT NULL, created_at $ts NULL, updated_at $ts NULL)");
DB::statement('CREATE INDEX posts_user_id ON posts (user_id)');
DB::statement('CREATE INDEX users_age ON users (age)');

function phase($name, $t) { printf("%s\t%d\n", $name, (hrtime(true) - $t) / 1e6); }
$total = hrtime(true);

$t = hrtime(true);
DB::transaction(function () use ($N) {
    for ($i = 0; $i < $N; $i++) {
        User::create(['name' => "user $i", 'email' => "user$i@example.com", 'age' => 18 + $i % 60, 'active' => $i % 3 != 0]);
    }
});
phase('create', $t);

$t = hrtime(true);
$rows = [];
for ($i = 0; $i < $N; $i++) {
    $rows[] = ['user_id' => intdiv($i, 5) + 1, 'title' => "post $i", 'views' => $i % 1000];
}
foreach (array_chunk($rows, 500) as $chunk) { DB::table('posts')->insert($chunk); }
phase('bulk_insert', $t);

$t = hrtime(true);
$found = 0;
for ($i = 0; $i < $N; $i++) {
    if (User::find(($i * 7919) % $N + 1) !== null) $found++;
}
phase('find', $t);

$t = hrtime(true);
$seen = 0;
for ($i = 0; $i < 1000; $i++) {
    $seen += User::where('active', true)->where('age', '>', 18 + $i % 40)->orderBy('age')->limit(50)->get()->count();
}
phase('where', $t);

$t = hrtime(true);
$all = 0;
for ($i = 0; $i < 5; $i++) { $all += User::all()->count(); }
phase('all', $t);

$t = hrtime(true);
DB::transaction(function () {
    foreach (User::query()->orderBy('id')->limit(2000)->get() as $u) {
        $u->age = $u->age + 1;
        $u->save();
    }
});
phase('update', $t);

$t = hrtime(true);
$posts = 0;
for ($i = 0; $i < 5; $i++) {
    foreach (User::with('posts')->orderBy('id')->limit(2000)->get() as $u) { $posts += $u->posts->count(); }
}
phase('eager', $t);

$t = hrtime(true);
$agg = 0.0;
for ($i = 0; $i < 1000; $i++) {
    $agg += User::where('age', '>', $i % 60)->count();
    $agg += (float) User::where('active', true)->avg('age');
}
phase('aggregate', $t);

phase('total', $total);
printf("check\t%d %d %d %d %s\n", $found, $seen, $all, $posts, $agg > 0 ? 'true' : 'false');
