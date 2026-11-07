# Laporan Bug

Dokumen ini mencatat 11 bug yang ditemukan dan diperbaiki pada pipeline ekstraktor CRUD SQL (Lexer, Parser, Resolver, Analyzer, dan CLI). Setiap entri menguraikan gejala, reproduksi minimal, analisis akar masalah (tahap pipeline, konsep dan bab rujukan *Crafting Interpreters*, serta pasal SPESIFIKASI.md), perbaikan kode, test regresi di 	ests/test_tambahan.py, serta peran AI dalam investigasi.

---

## Bug 1: Kata Kunci Huruf Kecil Salah Dikenali Sebagai Kolom Biasa

**Ditemukan oleh:** Darva · **Diperbaiki oleh:** Darva

**Gejala.** Saat menjalankan `python -m pytest`, pengujian `test_keyword_huruf_kecil` di `tests/test_lexer.py` gagal. Saat query seperti `select id from t;` diperiksa, kata `select` tidak dianggap sebagai kata kunci (`KEYWORD`), melainkan dicap sebagai nama kolom biasa (`IDENT`). Padahal menurut SPESIFIKASI.md Bagian 2.2, keyword SQL bersifat *case-insensitive* (`select`, `Select`, dan `SELECT` itu sama saja) dan nilainya harus otomatis dinormalisasi menjadi huruf kapital `SELECT`.

**Reproduksi minimal.**

```sql

select id from t;

```

**Akar masalah.** * **Tahap pipeline:** Lexer / Scanning (`crud/lexer.py` pada fungsi `_word()`).
* **Konsep & Bab *Crafting Interpreters*:** Bab 4 (*Scanning* - Sub-bab 4.7 *Reserved Words and Identifiers*) dan SPESIFIKASI.md Bagian 2.2.
* **Penyebab teknis:** Kode awal mengecek kata kunci dengan `if text in KEYWORDS:`, padahal daftar `KEYWORDS` seluruhnya memakai huruf kapital (`SELECT`, `FROM`, dll.). Operator `in` pada Python melakukan pencocokan string yang membedakan huruf besar dan kecil (*case-sensitive*), sehingga kata kunci huruf kecil seperti `'select'` tidak cocok dan malah masuk ke blok `else` sebagai nama kolom biasa (`IDENT`). Sesuai Bab 4.7, pada bahasa yang tidak peka huruf kapital (*case-insensitive*) seperti SQL, scanner wajib menormalisasi lexeme ke huruf kapital terlebih dahulu (`.upper()`) sebelum mencocokkannya ke tabel kata kunci.

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

**Akar masalah.** * **Tahap pipeline:** Lexer / Scanning (`crud/lexer.py` pada fungsi `_string()`).
* **Konsep & Bab *Crafting Interpreters*:** Bab 4 (*Scanning* - Sub-bab 4.6 *Longer Lexemes / String Literals*) dan SPESIFIKASI.md Bagian 2.4.
* **Penyebab teknis:** Pembacaan karakter langsung berhenti (`break`) seketika menemukan karakter tanda kutip tunggal `'`. Scanner tidak memeriksa karakter berikutnya (*tidak melakukan lookahead*). Padahal tanda kutip tunggal di dalam SQL memiliki fungsi ganda: dapat berupa penutup string atau bagian dari escape sequence jika diikuti tanda kutip berikutnya secara berdampingan (`''`). Sesuai konsep Bab 4.6, saat memindai literal yang mendukung aturan escape, scanner wajib mengintip satu karakter ke depan (*one-character lookahead*) sebelum memutuskan akhir suatu lexeme.

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

**Akar masalah.** * **Tahap pipeline:** Parser / Parsing Ekspresi (`crud/parser.py` pada fungsi `_logical()`).
* **Konsep & Bab *Crafting Interpreters*:** Bab 6 (*Parsing Expressions* - Sub-bab 6.1 *Ambiguity and the Parsing Game* & 6.2 *Recursive Descent Parsing*), Bab 9 (*Control Flow* - Sub-bab 9.3 *Logical Operators*), dan SPESIFIKASI.md Bagian 3.1.
* **Penyebab teknis:** Fungsi `_logical()` sebelumnya menangani operator `AND` dan `OR` di dalam satu perulangan yang sama: `while self._check_kw("AND", "OR"):`. Karena digabung di satu fungsi yang sama, parser memperlakukan kedua operator memiliki prioritas yang setara dan mengevaluasinya rata dari kiri ke kanan. Sesuai konsep Bab 6.2 dan 9.3, recursive descent parser menerapkan tingkatan prioritas operator melalui hierarki pemanggilan fungsi: fungsi untuk operator prioritas lebih rendah (`OR`) harus memanggil fungsi untuk operator prioritas lebih tinggi (`AND`).

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

**Akar masalah.** * **Tahap pipeline:** Resolver / Resolusi Semantik (`crud/resolver.py` pada fungsi `_delete()`).
* **Konsep & Bab *Crafting Interpreters*:** Bab 11 (*Resolving and Binding* - Sub-bab 11.3.1 *Resolving Blocks* & 11.3 *A Resolver Class*) dan SPESIFIKASI.md Bagian 4.5.
* **Penyebab teknis:** Resolver membuka scope baru untuk statement `DELETE` dengan memanggil `self._push()`, tetapi lupa memanggil `self._pop()` saat statement selesai diproses. Akibatnya terjadi kebocoran scope (*scope leak*), di mana lingkungan lokal `DELETE` beserta alias tabelnya (misalnya `s` untuk `sesi`) tetap tertinggal di puncak tumpukan scope dan terbaca oleh query setelahnya. Sesuai konsep Bab 11.3, pembukaan dan penutupan scope harus selalu berpasangan: begitu sebuah statement selesai diproses, scope lokalnya wajib dibuang agar tidak mencemari statement berikutnya.

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

**Akar masalah.** * **Tahap pipeline:** Lexer / Scanning (`crud/lexer.py` pada fungsi `_scan_token()`).
* **Konsep & Bab *Crafting Interpreters*:** Bab 4 (*Scanning* - Sub-bab 4.5 *Recognizing Lexemes & Maximal Munch*) dan SPESIFIKASI.md Bagian 2.5.
* **Penyebab teknis:** Penanganan karakter `<` pada fungsi `_scan_token()` awalnya hanya menguji satu kemungkinan: `op = "<=" if self._match("=") else "<"`. Ketika karakter berikutnya adalah `>`, scanner langsung memutus token menjadi `"<"`, sedangkan karakter `>` tertinggal dan menjadi token operator baru pada putaran scanner berikutnya. Ini melanggar aturan dasar *Maximal Munch* (Bab 4.5), di mana scanner wajib selalu mengonsumsi rangkaian karakter terpanjang yang valid (*longest valid match*). Operator `<>` harus dikenali utuh sebagai satu kesatuan token operator pembanding.

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

**Akar masalah.** * **Tahap pipeline:** Parser / Error Recovery (`crud/parser.py` pada fungsi `_synchronize()`).
* **Konsep & Bab *Crafting Interpreters*:** Bab 6 (*Parsing Expressions* - Sub-bab 6.3.3 *Synchronizing a Recursive Descent Parser*) dan SPESIFIKASI.md Bagian 6.
* **Penyebab teknis:** Fungsi pemulihan kesalahan `_synchronize()` awalnya hanya berisi loop `while not self._at_end(): self._advance()`. Fungsi ini membuang seluruh sisa token terus-menerus hingga akhir berkas (`EOF`) tanpa pernah menetapkan titik sinkronisasi perantara. Sesuai konsep Bab 6.3.3, saat parser mengalami kegagalan pada *panic mode*, parser harus membuang token hanya sampai menemukan batas pernyataan berikutnya (*synchronization boundary / recovery point*)—dalam SQL berupa tanda titik koma (`;`)—lalu kembali ke mode normal agar pernyataan-pernyataan valid setelahnya tetap dapat diekstrak.

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

**Akar masalah.** * **Tahap pipeline:** Resolver / Resolusi Semantik (`crud/resolver.py` pada fungsi `_lookup()`).
* **Konsep & Bab *Crafting Interpreters*:** Bab 11 (*Resolving and Binding* - Sub-bab 11.1 *Static Scope* & 11.3.3 *Resolving Variable Expressions*) dan SPESIFIKASI.md Bagian 4.3.
* **Penyebab teknis:** Rantai scope dikumpulkan dalam list `chain` dari scope terdalam (`self.scope`) hingga scope terluar (akar). Namun pencariannya dipanggil menggunakan `for scope in reversed(chain):`. Pemanggilan `reversed()` justru membalik urutan pencarian sehingga scope terluar diperiksa terlebih dahulu. Sesuai konsep Bab 11.1 dan 11.3, resolusi leksikal wajib memeriksa rantai scope dari dalam ke luar agar deklarasi lokal di dalam subquery dapat menutupi (*shadow*) deklarasi bernama sama di query luar. Pembalikan urutan ini menyebabkan alias di query luar menimpa resolusi alias lokal di dalam subquery.

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

**Akar masalah.** * **Tahap pipeline:** Analyzer / Analisis Semantik AST (`crud/analyzer.py` pada fungsi `analyze_statement()`).
* **Konsep & Bab *Crafting Interpreters*:** Bab 5 (*Representing Code* - Sub-bab 5.3 *Working with Trees*) dan SPESIFIKASI.md Bagian 5 (Aturan Operasi CRUD).
* **Penyebab teknis:** Pada penanganan simpul `ast.Update`, analyzer memanggil `_collect(stmt.where, usage, "U")` dan `_collect(assignment.value, usage, "U")`, yang memaksakan operasi `"U"` (Update) ke seluruh sub-ekspresi di dalamnya. Sesuai SPESIFIKASI.md Bagian 5 dan penelusuran pohon AST pada Bab 5.3, operasi `"U"` hanya berlaku untuk tabel target yang datanya diubah. Subquery di dalam klausa `WHERE` atau nilai `SET` hanya dibaca untuk evaluasi kondisi atau perhitungan nilai, sehingga operasi yang diteruskan ke subquery seharusnya `"R"` (Read).

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

**Akar masalah.** * **Tahap pipeline:** Parser / Parsing Klausa Join (`crud/parser.py` pada fungsi `_join()`).
* **Konsep & Bab *Crafting Interpreters*:** Bab 6 (*Parsing Expressions* - Sub-bab 6.2 *Recursive Descent Parsing*) dan SPESIFIKASI.md Bagian 3.
* **Penyebab teknis:** Pada fungsi `_join()`, setelah membaca kata kunci `LEFT`, parser langsung memanggil `self._expect_kw("JOIN")` tanpa memeriksa kemungkinan adanya kata kunci opsional `OUTER`. Padahal aturan EBNF pada SPESIFIKASI.md Bagian 3 mendefinisikan produksi join sebagai `LEFT [ "OUTER" ] "JOIN"`. Sesuai konsep Bab 6.2, setiap simbol terminal opsional dalam aturan tata bahasa harus dikonsumsi secara kondisional (`_match_kw("OUTER")`) sebelum menuntut terminal wajib berikutnya. Karena kata kunci `OUTER` tidak dikonsumsi, parser mendapati token yang tidak diharapkan dan melempar `ParseError`.

**Perbaikan.** Di file `crud/parser.py` pada fungsi `_join()`, setelah menetapkan `kind = "LEFT"`, kami menambahkan pengecekan `self._match_kw("OUTER")`. Jika kata `OUTER` ditemukan, token tersebut dikonsumsi; jika tidak ada (hanya `LEFT JOIN`), parser tetap berjalan normal menuju `self._expect_kw("JOIN")`. Alternatif mengabaikan kata `OUTER` di lexer kami tolak karena `OUTER` merupakan kata kunci SQL yang sah dan bernilai semantik di dalam tata bahasa.

**Test regresi.** `test_regresi_bug9_left_outer_join` di `tests/test_tambahan.py`.

**Peran AI.** AI membantu mengidentifikasi kegagalan parse saat menguji file `data/sample/pemeliharaan.sql` dan menunjukkan bahwa `_join()` lupa mengonsumsi kata kunci opsional `OUTER`. Kami memverifikasinya dengan mencocokkan tata bahasa EBNF pada SPESIFIKASI.md Bagian 3 dan merancang test regresi di `tests/test_tambahan.py`.

---

## Bug 10: Subquery SELECT Bertanda Kurung pada INSERT INTO ... (SELECT ...) Menyebabkan ParseError

**Ditemukan oleh:** Darva & Dava · **Diperbaiki oleh:** Dava

**Gejala.** Saat query `INSERT INTO` memakai subquery `SELECT` yang diapit tanda kurung `(...)` baik tanpa daftar kolom (misalnya `INSERT INTO arsip (SELECT id, total FROM pesanan);`) maupun dengan daftar kolom (misalnya `INSERT INTO arsip (id, total) (SELECT id, total FROM pesanan);`), parser gagal memproses query dan memicu error `ParseError: Baris 1, kolom 19: diharapkan VALUES atau SELECT, ditemukan '('`. Akibatnya, statement valid ini dibuang oleh parser melalui mekanisme *panic mode*, sehingga tabel target dan tabel sumber tidak tercatat pada matriks CRUD.

**Reproduksi minimal.**

```sql
INSERT INTO arsip (SELECT id, total FROM pesanan);
```

```powershell
python -c "from crud.parser import parse_sql; print(parse_sql('INSERT INTO arsip (SELECT id, total FROM pesanan);'))"
```

**Akar masalah.** * **Tahap pipeline:** Parser / Parsing Klausa Insert (`crud/parser.py` pada fungsi `_insert()`).
* **Konsep & Bab *Crafting Interpreters*:** Bab 6 (*Parsing Expressions* - Sub-bab 6.2 *Recursive Descent Parsing*) dan SPESIFIKASI.md Bagian 3 & 3.2.
* **Penyebab teknis:** Pada fungsi `_insert()`, kondisi `not self._next_is_select()` berhasil mencegah tanda kurung subquery `(SELECT ...)` dibaca sebagai daftar kolom target, namun parser tidak mengonsumsi token `(`. Akibatnya, saat masuk ke pengecekan `SELECT`, token yang aktif masih berupa kurung buka (`T.LPAREN`), sehingga parser melempar `ParseError: diharapkan VALUES atau SELECT`. Sesuai konsep Bab 6.2, parser harus mengonsumsi kurung buka pembuka subquery (`self._advance()`) sebelum memanggil `_select()`, dan memastikan kurung tutup penutup subquery dipanggil setelah subquery selesai diparse.

**Perbaikan.** Di file `crud/parser.py` pada fungsi `_insert()`, kami menambahkan `parenthesized = self._check(T.LPAREN) and self._next_is_select()` sebelum pengecekan `SELECT`, lalu mengonsumsi token `(` dengan `self._advance()` bila bernilai benar. Setelah `query = self._select()` selesai, parser menuntut kurung penutup dengan `self._expect(T.RPAREN, "')' penutup subquery")`, sehingga `INSERT INTO arsip (SELECT ...)` maupun `INSERT INTO arsip (id, total) (SELECT ...)` keduanya sah untuk diparse. Bentuk tanpa kurung (`INSERT INTO t SELECT ...`) tidak berubah karena `parenthesized` bernilai `False`. Alternatif membuang kondisi `and not self._next_is_select()` pada pembacaan daftar kolom kami tolak karena `(SELECT ...)` bisa keliru dibaca sebagai daftar nama kolom.

**Test regresi.** `test_regresi_bug10_insert_select_berkurung` dan `test_regresi_bug10_insert_select_berkurung_dengan_kolom` di `tests/test_tambahan.py`.

**Peran AI.** AI membantu menganalisis alur token pada fungsi `_insert()` saat kami melakukan audit menyeluruh terhadap variasi penulisan query di luar *happy path*, lalu menunjukkan bahwa karakter `(` tertahan tanpa dikonsumsi akibat kondisi `not self._next_is_select()`. Darva dan Dava bersama-sama memverifikasi temuan ini dengan mereproduksi error di terminal Python, menelusuri alur token di `_insert()`, dan menjalankan test regresinya sampai lulus.

---

## Bug 11: Diagnostic Resolver Tingkat 'Error' Menghasilkan Exit Code 0 (Status Sukses Palsu) di CLI

**Ditemukan oleh:** Darva & Dava · **Diperbaiki oleh:** Dava

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

**Akar masalah.** * **Tahap pipeline:** CLI / Driver Antarmuka Baris Perintah (`crud/cli.py` pada fungsi `main()`).
* **Konsep & Bab *Crafting Interpreters*:** Bab 11 (*Resolving and Binding* - Sub-bab 11.1 *Static Scope* & 11.5 *Resolution Errors*) serta SPESIFIKASI.md Bagian 4 & 8.
* **Penyebab teknis:** Variabel pelacak error `had_error = False` awalnya hanya diperbarui jika terjadi error pada tahap lexer atau parser. Pada tahap resolver, kode hanya mencetak pesan diagnostik ke `stderr` tanpa memeriksa properti tingkat keparahan `diag.level`. Akibatnya, meskipun resolver mendeteksi error semantik fatal (seperti alias yang tidak terdefinisi), fungsi `main()` tetap mengembalikan exit code `0` (sukses). Sesuai konsep Bab 11.5, error pada tahap resolusi semantik adalah kesalahan fatal yang wajib membuat program mengembalikan status keluar non-nol (*exit code 1*), sedangkan diagnostik bertaraf `"warning"` tetap tidak boleh menggagalkan proses.

**Perbaikan.** Di file `crud/cli.py` pada fungsi `main()`, di dalam perulangan `for diag in res.diagnostics:` kami menambahkan pemeriksaan `if diag.level == "error": had_error = True` sebelum diagnostik dicetak. Dengan begitu error semantik dari resolver membuat `main()` mengembalikan `1`, sedangkan diagnostik bertaraf `"warning"` (misalnya kolom ambigu atau subquery tanpa alias) tetap tidak mengubah exit code. Alternatif menganggap semua diagnostik sebagai error kami tolak karena warning bukan kegagalan fatal dan akan membuat file yang masih valid dianggap gagal.

**Test regresi.** `test_regresi_bug11_cli_error_resolver_exit_code` dan `test_tepi_cli_warning_tetap_exit_code_nol` di `tests/test_tambahan.py`.

**Peran AI.** AI menunjukkan inkonsistensi perilaku CLI yang tidak mengecek properti `level` pada list `diagnostics`, sehingga status proses tetap `0` meskipun terdapat error semantik. Darva dan Dava bersama-sama memverifikasi temuan ini dengan menguji perintah CLI pada file `data/sample/audit.sql` di terminal PowerShell, memeriksa isi variabel `$LASTEXITCODE`, dan menjalankan test regresinya sampai lulus.
