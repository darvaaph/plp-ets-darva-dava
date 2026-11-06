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

**Ditemukan oleh:** Dava · **Diperbaiki oleh:** Dava

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

**Perbaikan.** Di file `crud/analyzer.py` pada fungsi `analyze_statement()`, kami mengubah operasi yang diteruskan ke `_collect()` untuk `UPDATE` dari `"U"` menjadi `"R"`, baik pada `assignment.value` (subquery di `SET`) maupun `stmt.where`. Target `UPDATE` tetap ditandai `"U"` oleh `usage[stmt.table.name].add("U")`, sehingga hanya tabel yang dibaca lewat subquery yang berubah menjadi `R`. Alternatif menambahkan parameter khusus subquery pada `_collect()` kami tolak karena seluruh tabel yang ditemukan fungsi itu di dalam ekspresi `SET`/`WHERE` memang hanya berasal dari subquery, jadi cukup satu nilai argumen.

**Test regresi.** `test_regresi_bug8_subquery_update_dibaca_bukan_diubah` di `tests/test_tambahan.py`.

**Peran AI.** AI membandingkan penanganan `UPDATE` dan `DELETE` di `analyzer.py` dan menunjukkan perbedaan operasi yang dikirim ke `_collect()`. Kami memverifikasinya dengan menjalankan `analyze_statement()` pada query tersebut dan test regresinya sampai lulus.



---

## Bug 9: Kata Kunci Opsional OUTER Pada LEFT OUTER JOIN Menyebabkan ParseError

**Ditemukan oleh:** Darva · **Diperbaiki oleh:** Darva

**Gejala.** Saat mengekstraksi file contoh `data/sample/pemeliharaan.sql`, query pertama pada baris 3–6 (`select c.id, c.nama, a.kota from crm.pelanggan c left outer join crm.alamat a on a.pelanggan_id = c.id where c.aktif = 1;`) gagal di-parse dengan pesan error `ParseError: Baris 5, kolom 6: diharapkan JOIN, ditemukan 'OUTER'`. Akibatnya parser masuk ke *panic mode* dan membuang statement tersebut, sehingga tabel `crm.pelanggan` dan `crm.alamat` hilang dari matriks CRUD. Padahal menurut SPESIFIKASI.md Bagian 3, aturan tata bahasa join mengizinkan kata kunci `OUTER` secara opsional setelah `LEFT`: `join = [ "INNER" | "LEFT" [ "OUTER" ] ] "JOIN" table_ref "ON" expr ;`.

**Reproduksi minimal.**

```sql
SELECT c.id FROM crm.pelanggan c LEFT OUTER JOIN crm.alamat a ON a.pelanggan_id = c.id;
```

```powershell
python -c "from crud.pipeline import analyze_source; print(analyze_source('SELECT c.id FROM crm.pelanggan c LEFT OUTER JOIN crm.alamat a ON a.pelanggan_id = c.id;'))"
```

**Akar masalah.** Di file `crud/parser.py` pada fungsi `_join()`, parser mengecek kata kunci `LEFT` dengan `elif self._match_kw("LEFT"): kind = "LEFT"`, tetapi langsung melanjutkan ke `self._expect_kw("JOIN")` tanpa mengecek kemungkinan adanya kata kunci opsional `OUTER`.

Menurut **Buku *Crafting Interpreters* Bab 6 (Parsing Expressions - Sub-bab 6.3 Recursive Descent Parsing)**, setiap fungsi pada parser turunan rekursif merepresentasikan aturan produksi tata bahasa. Jika sebuah aturan memiliki klausa opsional seperti `[ "OUTER" ]`, parser wajib mengonsumsi token tersebut secara kondisional menggunakan fungsi *match* sebelum menuntut token wajib berikutnya (`JOIN`). Karena token opsional `OUTER` dilewati, parser mendapati token `OUTER` padahal yang diekspektasikan adalah `JOIN`, sehingga terjadi `ParseError`.

**Perbaikan.** Di file `crud/parser.py` pada fungsi `_join()`, setelah menetapkan `kind = "LEFT"`, kami menambahkan pengecekan `self._match_kw("OUTER")`. Jika kata `OUTER` ditemukan, token tersebut dikonsumsi; jika tidak ada (hanya `LEFT JOIN`), parser tetap berjalan normal menuju `self._expect_kw("JOIN")`. Alternatif mengabaikan kata `OUTER` di lexer kami tolak karena `OUTER` merupakan kata kunci SQL yang sah dan bernilai semantik di dalam tata bahasa.

**Test regresi.** `test_regresi_bug9_left_outer_join` di `tests/test_tambahan.py`.

**Peran AI.** AI membantu mengidentifikasi kegagalan parse saat menguji file `data/sample/pemeliharaan.sql` dan menunjukkan bahwa `_join()` lupa mengonsumsi kata kunci opsional `OUTER`. Kami memverifikasinya dengan mencocokkan tata bahasa EBNF pada SPESIFIKASI.md Bagian 3 dan merancang test regresi di `tests/test_tambahan.py`.

---

## Bug 10: Subquery SELECT Bertanda Kurung pada INSERT INTO ... (SELECT ...) Menyebabkan ParseError

**Ditemukan oleh:** Darva & Dava · **Diperbaiki oleh:** (Belum diperbaiki / Tahap Analisis)

**Gejala.** Saat query `INSERT INTO` memakai subquery `SELECT` yang diapit tanda kurung `(...)` baik tanpa daftar kolom (misalnya `INSERT INTO arsip (SELECT id, total FROM pesanan);`) maupun dengan daftar kolom (misalnya `INSERT INTO arsip (id, total) (SELECT id, total FROM pesanan);`), parser gagal memproses query dan memicu error `ParseError: Baris 1, kolom 19: diharapkan VALUES atau SELECT, ditemukan '('`. Akibatnya, statement valid ini dibuang oleh parser melalui mekanisme *panic mode*, sehingga tabel target dan tabel sumber tidak tercatat pada matriks CRUD.

**Reproduksi minimal.**

```sql
INSERT INTO arsip (SELECT id, total FROM pesanan);
```

```powershell
python -c "from crud.parser import parse_sql; print(parse_sql('INSERT INTO arsip (SELECT id, total FROM pesanan);'))"
```

**Akar masalah.** Di file `crud/parser.py` pada fungsi `_insert()`, baris `if self._check(T.LPAREN) and not self._next_is_select():` sengaja dirancang agar kurung buka `(` tidak dibaca sebagai daftar kolom bila diikuti kata kunci `SELECT`. Akan tetapi, parser hanya melompati blok pembacaan kolom tanpa mengonsumsi karakter `(` tersebut. Akibatnya, saat eksekusi berlanjut ke baris `if self._check_kw("SELECT"):`, token saat ini masih berupa kurung buka `(` (`T.LPAREN`), sehingga pengecekan gagal dan parser terlempar ke klausa error `raise ParseError("diharapkan VALUES atau SELECT", self._peek())`.

Menurut **Buku *Crafting Interpreters* Bab 6 (Parsing Expressions - Sub-bab 6.3 Recursive Descent Parsing)**, parser turunan rekursif harus mengonsumsi token pembatas (*delimiters/enclosures*) secara simetris dan konsisten. Jika sebuah produksi tata bahasa mengizinkan bentuk bertanda kurung (*parenthesized subclause*), parser wajib mengonsumsi token kurung buka `(` terlebih dahulu sebelum memanggil fungsi aturan di dalamnya (`_select()`), serta memastikan token kurung tutup `)` dikonsumsi secara seimbang di akhir aturan tersebut.

**Perbaikan.** (Rencana perbaikan) Di file `crud/parser.py` pada fungsi `_insert()`, sebelum memproses query `SELECT`, parser perlu memeriksa dan mengonsumsi kurung buka opsional dengan `parenthesized = self._match(T.LPAREN) is not None`. Jika tanda kurung ada, parser memanggil `query = self._select()` lalu menuntut kurung penutup dengan `self._expect(T.RPAREN, "')' penutup subquery")`. Jika tidak ada tanda kurung (bentuk lurus `INSERT INTO t SELECT ...`), parser langsung memanggil `query = self._select()`. Alternatif membuang kondisi `and not self._next_is_select()` ditolak karena akan membuat `(SELECT ...)` keliru dibaca sebagai daftar kolom.

**Test regresi.** `test_regresi_bug10_insert_select_berkurung` di `tests/test_tambahan.py`.

**Peran AI.** AI membantu menganalisis alur token pada fungsi `_insert()` saat kami melakukan audit menyeluruh terhadap variasi penulisan query di luar *happy path*, lalu menunjukkan bahwa karakter `(` tertahan tanpa dikonsumsi akibat kondisi `not self._next_is_select()`. Darva dan Dava bersama-sama memverifikasi temuan ini dengan mereproduksi error di terminal Python dan menelusuri eksekusi token di parser.

---

## Bug 11: Diagnostic Resolver Tingkat 'Error' Menghasilkan Exit Code 0 (Status Sukses Palsu) di CLI

**Ditemukan oleh:** Darva & Dava · **Diperbaiki oleh:** (Belum diperbaiki / Tahap Analisis)

**Gejala.** Saat antarmuka baris perintah (`crud.cli`) dijalankan pada file SQL yang mengandung kesalahan semantik pada tahap resolusi (contohnya pada `data/sample/audit.sql` baris 18 yang memuat alias tidak terdefinisi: `SELECT s.id FROM pengguna u`), CLI memang mencetak pesan kesalahan ke `stderr`, namun proses CLI selesai dengan status keberhasilan (*exit code*) bernilai `0`. Akibatnya, lingkungan eksekusi (seperti terminal PowerShell, skrip bash CI/CD, atau *test runner* otomatis) menganggap proses berjalan sukses tanpa galat, padahal terdapat kesalahan fatal pada file tersebut.

**Reproduksi minimal.**

```sql
-- File berisi alias tidak terdefinisi (seperti data/sample/audit.sql baris 18)
SELECT s.id FROM pengguna u WHERE u.aktif = 1;
```

```powershell
python -m crud.cli data/sample/audit.sql
echo $LASTEXITCODE
```
Nilai `$LASTEXITCODE` yang keluar adalah `0` (seharusnya `1`).

**Akar masalah.** Di file `crud/cli.py` pada fungsi `main()`, penanda kesalahan `had_error = False` hanya diubah menjadi `True` saat mendeteksi `res.lex_error` atau `res.parse_errors`. Pada perulangan diagnostik resolver:
```python
for diag in res.diagnostics:
    print(f"{path.name}: {diag}", file=sys.stderr)
```
Kode hanya mencetak teks diagnostik tanpa memeriksa apakah tingkat keparahannya bernilai `diag.level == "error"`. Akibatnya, pada akhir fungsi `main()`, baris `return 1 if had_error else 0` tetap mengembalikan `0` karena `had_error` masih bernilai `False`.

Menurut **Buku *Crafting Interpreters* Bab 11 (Resolving and Binding - Sub-bab 11.1 Static Scope & 11.3 A Resolver Class)** serta standar rekayasa perangkat lunak, pass resolusi semantik merupakan tahap validasi krusial yang setara dengan tahap scanning dan parsing. Apabila sebuah pass semantik menemukan pelanggaran fatal (*semantic error* seperti referensi variabel/alias tak dikenal), lingkungan pemroses (*driver/CLI*) wajib menandai status proses sebagai gagal (*error exit status non-zero*) agar pipeline otomatisasi tidak menganggap input yang salah sebagai input yang valid.

**Perbaikan.** (Rencana perbaikan) Di file `crud/cli.py` pada loop `for diag in res.diagnostics:`, tambahkan pemeriksaan tingkat keparahan: bila `diag.level == "error"`, maka ubah `had_error = True`. Diagnostik bertaraf `"warning"` (seperti kolom ambigu atau subquery tanpa alias) tetap dibiarkan tanpa mengubah `had_error` agar peringatan tidak membatalkan eksekusi normal.

**Test regresi.** `test_regresi_bug11_cli_exit_code_error_resolver` di `tests/test_tambahan.py`.

**Peran AI.** AI menunjukkan inkonsistensi perilaku CLI yang tidak mengecek properti `level` pada list `diagnostics`, sehingga status proses tetap `0` meskipun terdapat error semantik. Darva dan Dava bersama-sama memverifikasi temuan ini dengan menguji perintah CLI pada file `data/sample/audit.sql` di terminal PowerShell dan memeriksa isi variabel `$LASTEXITCODE`.
