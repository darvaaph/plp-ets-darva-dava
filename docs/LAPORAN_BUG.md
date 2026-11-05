# Laporan Bug

Salin blok di bawah untuk setiap bug. Bagian **Akar masalah** wajib ditulis dengan kata-kata

sendiri dan memakai konsep dari *Crafting Interpreters* (sebutkan bab). Bagian ini diuji lisan.

---

## Bug 1: Kata Kunci Huruf Kecil Salah Dikenali Sebagai Kolom Biasa

**Ditemukan oleh:** Darva · **Diperbaiki oleh:** Darva

**Gejala.** Saat menjalankan `python -m pytest`, pengujian `test_keyword_huruf_kecil` di `tests/test_lexer.py` gagal. Saat query seperti `select id from t;` diperiksa, kata `select` tidak dianggap sebagai kata kunci (`KEYWORD`), melainkan dicap sebagai nama kolom biasa (`IDENT`). Padahal menurut SPESIFIKASI.md Bagian 2.2, keyword SQL bersifat *case-insensitive* (`select`, `Select`, dan `SELECT` itu sama saja) dan nilainya harus otomatis dinormalisasi menjadi huruf kapital `SELECT`.

**Reproduksi minimal.**

```sql

select id from t;

```

**Akar masalah.** Di file `crud/lexer.py` pada fungsi `_word()`, pengecekan kata kunci menggunakan baris: `if text in KEYWORDS:`. 

Karena daftar `KEYWORDS` berisi huruf kapital semua (`SELECT`, `FROM`, dll.), perbandingan string di Python yang bersifat *case-sensitive* menganggap `'select'` huruf kecil tidak ada di daftar, sehingga kode melompat ke blok `else` dan menjadikannya `IDENT`.

Menurut **Buku *Crafting Interpreters* Bab 4 (Scanning - Sub-bab 4.7 Reserved Words and Identifiers)**, scanner membedakan kata kunci dan identifier dengan mencocokkan kata ke kamus keyword. Karena SQL tidak peduli huruf besar-kecil, scanner harus menyamakan formatnya terlebih dahulu (diubah ke kapital dengan `.upper()`) sebelum dicocokkan ke kamus agar kata kunci tidak salah dianggap sebagai identifier.

**Perbaikan.** Di file `crud/lexer.py` pada fungsi `_word()`, kami mengubah teks ke huruf kapital dengan `upper = text.upper()` sebelum dicek ke `KEYWORDS`. Jika ada di kamus, nilai `upper` disimpan sebagai token `KEYWORD`. Jika tidak ada, teks asli disimpan sebagai `IDENT`. Alternatif mengubah daftar `KEYWORDS` menjadi huruf kecil kami tolak karena spesifikasi mewajibkan nilai token dinormalisasi ke huruf kapital.

**Test regresi.** `test_regresi_bug1_keyword_huruf_kecil` di `tests/test_tambahan.py`.

**Peran AI.** AI membantu menunjukkan baris `if text in KEYWORDS` yang masih peka huruf besar-kecil. Kami memverifikasinya sendiri dengan memanggil `tokenize("select id")` di terminal dan melihat token yang keluar memang `IDENT`.

---

## Bug 2: Karakter Escape Dua Kutip Tunggal ('') di Dalam String Terpotong

**Ditemukan oleh:** Darva · **Diperbaiki oleh:** Dava

**Gejala.** Di file contoh `data/sample/pemeliharaan.sql` baris 6, ada teks nama orang `'O''Brien'`. Saat di-tokenize, teks tersebut malah terpotong menjadi `'O'` saja dan sisa hurufnya menyebabkan error. Padahal menurut SPESIFIKASI.md Bagian 2.4, dua tanda kutip tunggal berdampingan (`''`) di dalam string mewakili satu karakter kutip, sehingga `'O''Brien'` seharusnya tetap utuh menjadi satu token string bernilai `O'Brien`.

**Reproduksi minimal.**

```sql

SELECT 'O''Brien' FROM t;

```

**Akar masalah.** Di file `crud/lexer.py` pada fungsi `_string()`, pembacaan karakter langsung berhenti (`break`) seketika menemukan karakter tanda kutip `'`. Kode lama tidak memeriksa karakter berikutnya (*tidak melakukan lookahead*). Padahal tanda kutip bisa berarti penutup string atau karakter escape jika diikuti kutip lagi (`''`).

Menurut **Buku *Crafting Interpreters* Bab 4 (Scanning - Sub-bab 4.6 Longer Lexemes / String Literals)**, saat membaca string dengan karakter escape, scanner wajib mengintip satu karakter ke depan (*lookahead*) sebelum memutuskan apakah itu penutup string atau bukan.

**Perbaikan.** Di file `crud/lexer.py` pada fungsi `_string()`, kami menambahkan pengecekan `if not self._match("'"): break`. Jika setelah tanda kutip ditemukan tanda kutip lagi, karakter kedua ikut dikonsumsi dan satu karakter kutip dimasukkan ke dalam string. Jika tidak ada kutip lagi, barulah pembacaan string selesai (`break`). Alternatif menggunakan `replace("''", "'")` setelah string dibaca kami tolak karena berisiko merusak penghitungan posisi kolom token.

**Test regresi.** `test_regresi_bug2_escape_kutip_ganda_dalam_string` di `tests/test_tambahan.py`.

**Peran AI.** AI menjelaskan konsep escape `''` dan menyarankan penggunaan helper `_match` untuk lookahead. Kami memverifikasinya dengan membaca fungsi `_string()` dan memastikan test regresi di `tests/test_tambahan.py` lulus.

---

## Bug 3: Derajat Operator AND dan OR Dianggap Sama Kuat

**Ditemukan oleh:** Darva · **Diperbaiki oleh:** Dava

**Gejala.** Saat memeriksa pohon AST pada file `data/sample/audit.sql` baris 2 (`WHERE ... OR ... AND ...`), operator `AND` ditaruh di puncak pohon (root), seolah-olah dibaca `(a OR b) AND c`. Padahal menurut SPESIFIKASI.md Bagian 3.1, operator `AND` berderajat lebih tinggi (tingkat 2) daripada `OR` (tingkat 1), mirip seperti perkalian lebih didahulukan daripada penjumlahan. Jadi seharusnya query dibaca sebagai `a OR (b AND c)`.

**Reproduksi minimal.**

```sql

SELECT id FROM t WHERE a = 1 OR b = 2 AND c = 3;

```

**Akar masalah.** Di file `crud/parser.py`, fungsi `_logical()` menangani `AND` dan `OR` di dalam perulangan yang sama: `while self._check_kw("AND", "OR"):`. Karena disatukan, parser menganggap keduanya setara dan membaca lurus dari kiri ke kanan.

Menurut **Buku *Crafting Interpreters* Bab 6 (Parsing Expressions - Sub-bab 6.2 Precedence and Associativity)**, tata bahasa untuk operator yang berbeda tingkatan harus dipisah ke fungsi yang berbeda secara berjenjang (*stratified functions*). Fungsi operator lemah (`OR`) harus memanggil fungsi operator yang lebih kuat (`AND`).

**Perbaikan.** Di file `crud/parser.py`, kami memisahkan fungsi `_logical()` menjadi dua tingkat. Fungsi `_logical()` sekarang khusus memproses `OR` dan memanggil `_and()`, sedangkan fungsi baru `_and()` memproses `AND` lalu memanggil `_not()`. Alternatif membuat tabel presedensi tidak kami pilih karena operator logika di sini hanya ada dua tingkat (`AND` dan `OR`), sehingga membuat fungsi berjenjang jauh lebih sederhana dan langsung sesuai spesifikasi.

**Test regresi.** `test_regresi_bug3_and_lebih_kuat_dari_or` di `tests/test_tambahan.py`.

**Peran AI.** AI menjelaskan cara memisahkan fungsi `_logical()` secara berjenjang. Kami memverifikasinya dengan mengecek pohon AST di terminal sebelum dan sesudah perbaikan.

---

## Bug 4: Nama Alias dari DELETE Masih Nyangkut ke Query Berikutnya

**Ditemukan oleh:** Darva · **Diperbaiki oleh:** Dava

**Gejala.** Pada file `data/sample/audit.sql` baris 16 ada perintah `DELETE FROM sesi s` dan di baris 18 ada `SELECT s.id FROM pengguna u`. Kolom `s.id` pada query kedua malah dianggap merujuk ke tabel `sesi` milik query pertama. Padahal menurut SPESIFIKASI.md Bagian 4.5, setiap statement harus berdiri sendiri dan alias dari query sebelumnya tidak boleh bocor ke query berikutnya.

**Reproduksi minimal.**

```sql

DELETE FROM sesi s WHERE s.id = 1;

SELECT s.id FROM pengguna u;

```

**Akar masalah.** Di file `crud/resolver.py` pada fungsi `_delete()`, resolver membuka scope baru dengan memanggil `self._push()`, tetapi lupa memanggil `self._pop()` di akhir fungsi. Akibatnya scope `DELETE` tidak pernah ditutup (*scope leak*), sehingga query setelahnya masih bisa melihat alias tersebut.

Menurut **Buku *Crafting Interpreters* Bab 11 (Resolving and Binding - Sub-bab 11.3 A Resolver Class)**, setiap kali kita membuka scope (`_push`), kita wajib menutupnya kembali (`_pop`) begitu blok selesai agar variabel di dalamnya tidak bocor keluar.

**Perbaikan.** Di file `crud/resolver.py` pada fungsi `_delete()`, kami menambahkan pemanggilan `self._pop()` setelah `self._expr(dele.where)`. Posisinya di akhir agar ekspresi `WHERE` masih dapat merujuk alias target `DELETE` (misalnya `s.id`), lalu scope ditutup sebelum statement berikutnya diproses. Alternatif mereset `self.scope = None` di `resolve_script()` kami tolak karena hanya menambal gejala dan menyembunyikan ketidakseimbangan `_push()`/`_pop()`.

**Test regresi.** `test_regresi_bug4_alias_delete_tidak_bocor` di `tests/test_tambahan.py`.

**Peran AI.** AI membantu menemukan bahwa fungsi `_delete()` tidak memiliki pemanggilan `_pop()`. Kami memverifikasinya dengan membandingkan `_delete()` dengan `_update()` yang sudah memiliki `self._pop()`, lalu menjalankan test regresi sampai lulus.

---

## Bug 5: Operator `<>` Terbelah Jadi Dua Token

**Ditemukan oleh:** Dava · **Diperbaiki oleh:** Darva

**Gejala.** SPESIFIKASI.md Bagian 2.5 mewajibkan lexer mengambil operator terpanjang (*maximal munch*), sehingga `<>` wajib menjadi satu token. Namun saat query `SELECT id FROM t WHERE a <> 1;` di-tokenize, hasilnya terbelah menjadi dua token terpisah: `OP '<'` lalu `OP '>'`. Akibatnya, parser gagal memproses query karena mengira ada dua operator berturut-turut tanpa nilai di antaranya.

**Reproduksi minimal.**

```sql

SELECT id FROM t WHERE a <> 1;

```

```powershell

python -c "from crud.lexer import tokenize; print(tokenize('SELECT id FROM t WHERE a <> 1;'))"

```

**Akar masalah.** Di `crud/lexer.py`, penanganan karakter `<` pada `_scan_token()` hanya menguji satu kemungkinan: `op = "<=" if self._match("=") else "<"`. Karena karakter berikutnya bukan `=`, token langsung diputus `"<"`, sedangkan `>` tertinggal dan menjadi token baru pada putaran berikutnya.

Menurut **Buku *Crafting Interpreters* Bab 4 (Scanning - Sub-bab 4.5 Recognizing Lexemes)**, operator dua karakter dikenali lewat *lookahead* dengan prinsip *maximal munch* (jika ada beberapa kemungkinan yang cocok, ambil yang terpanjang). Kode lama melanggar aturan ini karena tidak mengecek karakter `>`.

**Perbaikan.** Di file `crud/lexer.py` pada fungsi `_scan_token()`, kami menambahkan pengecekan `elif self._match(">"): op = "<>"` saat membaca karakter `<`. Alternatif menyatukan dua token di tahap parser kami tolak karena penggabungan karakter operator adalah tanggung jawab lexer sesuai prinsip *maximal munch*.

**Test regresi.** `test_regresi_bug5_operator_tidak_sama_dengan` di `tests/test_tambahan.py`.

**Peran AI.** AI membantu menunjukkan baris penanganan karakter `<` yang lupa memeriksa `>`. Kami memverifikasinya dengan menjalankan `tokenize()` di terminal dan menulis test regresi di `tests/test_tambahan.py`.

---

## Bug 6: Statement Valid Setelah Error Ikut Terbuang Sampai Habis

**Ditemukan oleh:** Dava · **Diperbaiki oleh:** Darva

**Gejala.** SPESIFIKASI.md Bagian 6 menetapkan bahwa *panic mode* harus membuang token sampai `;` berikutnya lalu melanjutkan statement setelahnya. Namun saat menjalankan `data/sample/campuran_error.sql`, dua statement valid setelah baris yang error (`UPDATE` dan `DELETE`) ikut hilang dari hasil analisis dan tidak masuk ke `crud_matrix.csv`.

**Reproduksi minimal.**

```sql

SELECT id, nama FROM pelanggan WHERE aktif = 1;

SELECT id nama, FROM pesanan;

UPDATE produk SET stok = stok - 1 WHERE id = :id;

```

```powershell

python -m crud.cli data/sample/campuran_error.sql

```

**Akar masalah.** Di `crud/parser.py`, fungsi `_synchronize()` hanya berisi loop `while not self._at_end(): self._advance()`. Kode ini membuang semua token terus-menerus sampai akhir file (EOF) tanpa pernah berhenti di tanda titik koma (`;`).

Menurut **Buku *Crafting Interpreters* Bab 6 (Parsing Expressions - Sub-bab 6.3.3 Synchronizing a recursive descent parser)**, fungsi sinkronisasi pada *panic mode* wajib mencari batas statement terdekat (seperti `;`) agar parser bisa pulih dan statement valid berikutnya tetap dapat diproses.

**Perbaikan.** Di file `crud/parser.py` pada fungsi `_synchronize()`, kami menambahkan kondisi `if self._advance().type == T.SEMICOLON: return`. Dengan begitu, pembuangan token langsung berhenti begitu tanda titik koma ditemukan dan parser kembali ke mode normal untuk memproses statement berikutnya. Alternatif mencari keyword awal statement (seperti `SELECT`, `UPDATE`) tidak kami pilih karena SPESIFIKASI.md Bagian 6 secara eksplisit menetapkan batas pemulihan adalah tanda titik koma (`;`).

**Test regresi.** `test_regresi_bug6_panic_mode_lanjut_ke_statement_berikutnya` di `tests/test_tambahan.py`.

**Peran AI.** AI menyarankan untuk memeriksa fungsi `_synchronize()` di parser. Kami memverifikasinya dengan membaca kode fungsi tersebut yang ternyata langsung melompat ke akhir file.

---

## Bug 7: Alias dari Luar Subquery Mengalahkan Alias di Dalam Subquery

**Ditemukan oleh:** Dava · **Diperbaiki oleh:** Darva

**Gejala.** SPESIFIKASI.md Bagian 4.3 mengatur bahwa pencarian alias harus berjalan dari scope terdalam ke luar (*shadowing*). Pada query bersarang di `data/sample/audit.sql` baris 12–14: `SELECT x.id FROM pelanggan x WHERE x.id IN (SELECT x.pelanggan_id FROM pesanan x ...);`, kolom `x.pelanggan_id` di dalam subquery malah di-resolve ke `pelanggan` (tabel luar), bukan ke `pesanan` (tabel subquery).

**Reproduksi minimal.**

```sql
SELECT x.id FROM pelanggan x
WHERE x.id IN (SELECT x.pelanggan_id FROM pesanan x WHERE x.total > 500000);
```

**Akar masalah.** Di `crud/resolver.py` pada fungsi `_lookup()`, rantai scope dikumpulkan dari dalam ke luar (`chain[0]` = scope terdalam), tetapi pencariannya ditulis `for scope in reversed(chain):`. Pemanggilan `reversed()` membuat pencarian dimulai dari scope terluar, sehingga alias di query luar menimpa alias di dalam subquery.

Menurut **Buku *Crafting Interpreters* Bab 11 (Resolving and Binding - Sub-bab 11.3 A Resolver Class)**, resolusi variabel harus mencari dari scope lokal/terdalam terlebih dahulu sebelum mencari ke scope induknya.

**Perbaikan.** Di file `crud/resolver.py` pada fungsi `_lookup()`, kami menghapus pemanggilan `reversed()` sehingga loop menjadi `for scope in chain:`. Karena elemen `chain` dikumpulkan mulai dari `self.scope` (scope terdalam) lalu naik ke `parent`, iterasi langsung mencari dari scope terdalam ke scope luar. Dengan begitu, alias lokal di dalam subquery menutupi (*shadow*) alias bernama sama dari query luar.

**Test regresi.** `test_regresi_bug7_shadowing_alias_subquery_menimpa_luar` di `tests/test_tambahan.py`.

**Peran AI.** AI membantu menganalisis alur loop pada `_lookup()` yang ternyata dibalik dengan `reversed()`. Kami memverifikasinya dengan membuat test regresi untuk kasus subquery yang menggunakan alias yang sama dengan query luar hingga test berhasil lulus.

---

## Bug 8: Subquery di UPDATE Dikasih Operasi U, Harusnya R

**Ditemukan oleh:** Dava

**Gejala.** SPESIFIKASI.md Bagian 5 menegaskan bahwa membaca tabel lewat subquery selalu menghasilkan operasi `R`. Namun pada query `UPDATE pesanan SET status = 'BATAL' WHERE pelanggan_id IN (SELECT id FROM pelanggan WHERE diblokir = 1);`, tabel `pelanggan` di dalam subquery malah ikut diberi operasi `U` (`{'pesanan': {'U'}, 'pelanggan': {'U'}}`), bukan `R`.

**Reproduksi minimal.**

```sql

UPDATE pesanan SET status = 'BATAL'

WHERE pelanggan_id IN (SELECT id FROM pelanggan WHERE diblokir = 1);

```

```text

hasil analyze_statement() saat ini : {'pesanan': {'U'}, 'pelanggan': {'U'}}

seharusnya                        : {'pesanan': {'U'}, 'pelanggan': {'R'}}

```

**Akar masalah.** Di `crud/analyzer.py` pada fungsi `analyze_statement()`, penanganan `UPDATE` memanggil `_collect(stmt.where, usage, "U")`. Karena yang diteruskan adalah `"U"`, semua tabel di dalam subquery klausa `WHERE` ikut ditandai sebagai Update. Sebagai pembanding, penanganan `DELETE` sudah benar dengan meneruskan `"R"`.

Aturan ini mengacu pada aturan proyek di SPESIFIKASI.md Bagian 5 (tabel aturan CRUD).

**Peran AI.** AI membandingkan penanganan `UPDATE` dan `DELETE` di `analyzer.py` dan menunjukkan perbedaan operasi yang dikirim ke `_collect`. Kami memverifikasinya dengan menjalankan fungsi analyzer pada query tersebut.
