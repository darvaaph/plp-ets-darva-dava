# Laporan Bug

Salin blok di bawah untuk setiap bug. Bagian **Akar masalah** wajib ditulis dengan kata-kata
sendiri dan memakai konsep dari *Crafting Interpreters* (sebutkan bab). Bagian ini diuji lisan.

---

## Bug 1: Kata Kunci Huruf Kecil Salah Dikenali Sebagai Kolom Biasa

**Ditemukan oleh:** Darva · **Diperbaiki oleh:** Darva

**Gejala.** Waktu pertama kali menjalankan perintah `python -m pytest` di terminal, pengujian di file `tests/test_lexer.py` pada fungsi `test_keyword_huruf_kecil` langsung gagal merah. Saat query seperti `select id from t;` diperiksa, kata `select` tidak dianggap sebagai kata kunci (`KEYWORD`), melainkan dicap sebagai nama kolom biasa (`IDENT`). Padahal menurut SPESIFIKASI.md Bagian 2.2, SQL tidak peduli huruf besar atau kecil (`select`, `Select`, dan `SELECT` itu sama saja) dan nilainya harus otomatis diubah menjadi huruf kapital `SELECT`.

**Reproduksi minimal.**
```sql
select id from t;
```

**Akar masalah.** Di file `crud/lexer.py` pada fungsi `_word()`, pembuat kode mengecek kata kunci dengan baris: `if text in KEYWORDS:`. 
Masalahnya, di Python perbandingan string itu sensitif huruf besar-kecil (*case-sensitive*). Karena daftar `KEYWORDS` isinya huruf besar semua (`SELECT`, `FROM`, dll.), Python merasa `'select'` (huruf kecil) tidak ada di daftar tersebut. Akhirnya kode melompat ke blok `else` dan kata `select` malah dianggap nama kolom biasa (`IDENT`). 
Sesuai penjelasan di **Buku *Crafting Interpreters* Bab 4 (Scanning - Sub-bab 4.7 Reserved Words and Identifiers)**, scanner membedakan kata kunci dan nama kolom dengan mencari kata tersebut di kamus kata kunci. Karena SQL tidak peduli huruf besar-kecil, scanner seharusnya menyamakan format hurufnya dulu (diubah ke kapital dengan `.upper()`) sebelum dicocokkan ke kamus agar tidak keliru menganggap kata kunci sebagai nama kolom biasa.

**Perbaikan.** Di file `crud/lexer.py` pada fungsi `_word()`, teks dinormalisasi ke huruf kapital dengan `upper = text.upper()` sebelum dicocokkan ke `KEYWORDS`. Jika cocok, nilai `upper` disimpan sebagai token `KEYWORD`. Jika tidak cocok, teks asli tetap disimpan sebagai `IDENT`. Alternatif mengubah daftar `KEYWORDS` menjadi huruf kecil ditolak karena SPESIFIKASI.md bagian 2.2 menetapkan nilai token harus berupa huruf kapital.

**Test regresi.** `test_regresi_bug1_keyword_huruf_kecil` di `tests/test_tambahan.py`.

**Peran AI.** Saya menanyakan ke AI kenapa `select` huruf kecil di pytest bisa gagal padahal katanya SQL tidak sensitif huruf. AI menunjukkan bahwa baris `if text in KEYWORDS` di lexer masih case-sensitive. Saya memverifikasinya sendiri dengan mencoba memanggil `tokenize("select id")` di terminal dan melihat token yang keluar memang `IDENT`.

---

## Bug 2: Karakter Escape Dua Kutip Tunggal ('') di Dalam String Terpotong.

**Ditemukan oleh:** Darva · **Diperbaiki oleh:** Dava

**Gejala.** Waktu kami memeriksa file contoh `data/sample/pemeliharaan.sql`, di baris 6 ada tulisan nama orang `'O''Brien'`. Saat kami coba jalankan leksingnya, kata tersebut malah terpotong menjadi `'O'` saja, lalu sisa hurufnya membuat program error. Padahal menurut SPESIFIKASI.md Bagian 2.4, di dalam aturan SQL kalau ada dua tanda kutip tunggal berdampingan (`''`), itu maksudnya bukan penutup kalimat, melainkan cara menulis satu karakter tanda kutip di dalam teks. Jadi `'O''Brien'` seharusnya tetap utuh menjadi satu kata string bernilai `O'Brien`.

**Reproduksi minimal.**
```sql
SELECT 'O''Brien' FROM t;
```

**Akar masalah.** Di file `crud/lexer.py` pada fungsi pembaca string `_string()`, perulangan pembacaan karakter langsung berhenti (`break`) seketika menemukan karakter tanda kutip tunggal `'`. 
Kodenya tidak mengecek karakter berikutnya (*tidak melakukan lookahead*). Padahal tanda kutip dalam SQL punya dua kemungkinan: bisa sebagai penutup kalimat teks, atau sebagai tanda *escape* jika langsung diikuti tanda kutip lagi (`''`).
Sesuai penjelasan di **Buku *Crafting Interpreters* Bab 4 (Scanning - Sub-bab 4.6 Longer Lexemes / String Literals)**, saat membaca teks string yang karakternya punya makna ganda (*escape sequence*), scanner wajib mengintip satu karakter ke depan (*lookahead*) sebelum memutuskan apakah itu tanda penutup string atau bukan.

**Perbaikan.** Di `crud/lexer.py`, fungsi `_string()` (baris 153–163) kini mengintip satu karakter setelah kutip tunggal memakai helper `_match("'")` yang sudah tersedia. Kalau karakter berikutnya juga kutip, pasangan `''` dikonsumsi sebagai escape dan satu karakter `'` dimasukkan ke nilai string; kalau bukan, kutip diperlakukan sebagai penutup. Perubahan hanya tiga baris, tanpa method atau state baru.

Alternatif `replace("''", "'")` pada seluruh teks sumber ditolak karena merusak posisi baris/kolom token dan bisa mengubah token di luar string. Escape backslash (`\'`) dan string kutip ganda tidak ditambahkan karena di luar lingkup SPESIFIKASI.md bagian 2.4.

**Test regresi.** `test_regresi_bug2_escape_kutip_ganda_dalam_string` di `tests/test_tambahan.py` memastikan `'O''Brien'` menjadi satu token `STRING` bernilai `O'Brien`, bukan dua token. Status: `python -m pytest tests/test_tambahan.py -v` → 2 passed.

**Peran AI.** Gejala string `'O''Brien'` yang terpotong sempat ditanyakan ke AI. AI menjelaskan konsep escape `''` dan perlunya *lookahead* satu karakter, lalu menunjuk `_string()` yang berhenti tanpa mengecek karakter berikutnya. Rancangan perbaikan minimal dengan `_match("'")` juga diajukan AI. Pernyataan itu diverifikasi dengan membaca `_string()`, mencocokkannya ke SPESIFIKASI.md bagian 2.4, dan menjalankan `python -m pytest tests/test_tambahan.py` (2 passed).

---

## Bug 3: Derajat Operator AND dan OR Dianggap Sama Kuat

**Ditemukan oleh:** Darva · **Diperbaiki oleh:** Dava

**Gejala.** Waktu menjalankan perintah `python -m crud.cli data/sample/audit.sql --ast` di terminal untuk melihat pohon sintaks (AST) pada baris 2, ada query `WHERE ... OR ... AND ...`. Anehnya, di pohon yang dicetak, operator `AND` ditaruh di paling atas (menjadi root), yang artinya query dibaca seolah-olah `(a OR b) AND c`. Padahal menurut SPESIFIKASI.md Bagian 3.1, operator `AND` derajatnya lebih tinggi (tingkat 2) daripada `OR` (tingkat 1), mirip seperti perkalian lebih didahulukan daripada penjumlahan. Jadi seharusnya query dibaca sebagai `a OR (b AND c)`.

**Reproduksi minimal.**
```sql
SELECT id FROM t WHERE a = 1 OR b = 2 AND c = 3;
```

**Akar masalah.** Di file `crud/parser.py`, fungsi `_logical()` menangani kata `AND` dan `OR` di dalam satu perulangan yang sama: `while self._check_kw("AND", "OR"):`. 
Karena digabung, parser menganggap `AND` dan `OR` kekuatannya setara, sehingga parser hanya membaca lurus dari kiri ke kanan (yang datang duluan dikerjakan duluan).
Mengacu pada **Buku *Crafting Interpreters* Bab 6 (Parsing Expressions - Sub-bab 6.2 Precedence and Associativity)**, tata bahasa untuk operator yang beda tingkatan harus dipisah ke fungsi yang berbeda secara berjenjang (*stratified functions*). Fungsi operator berderajat rendah (seperti `OR`) harus memanggil fungsi operator berderajat lebih tinggi (seperti `AND`), bukan disatukan di satu fungsi.

**Perbaikan.** Di file `crud/parser.py`, fungsi `_logical()` dipersempit agar hanya menangani `OR` dan memanggil `_and()`, sedangkan fungsi baru `_and()` menangani `AND` dan memanggil `_not()`. Rantai `_expr()` tidak berubah sehingga seluruh pemanggilnya tetap aman. `BETWEEN a AND b` tetap benar karena `AND` milik `BETWEEN` sudah dikonsumsi `_comparison()` sebelum perulangan `_and()`. Alternatif mempertahankan satu perulangan `AND`/`OR` ditolak karena melanggar presedensi SPESIFIKASI.md bagian 3.1, sedangkan tabel presedensi dinilai berlebihan untuk dua tingkat operator.

**Test regresi.** `test_regresi_bug3_and_lebih_kuat_dari_or` di `tests/test_tambahan.py`.

**Peran AI.** Pohon AST `data/sample/audit.sql` baris 2 yang menaruh `AND` sebagai root sempat ditanyakan ke AI. AI menunjuk fungsi `_logical()` yang menggabungkan `AND` dan `OR` dalam satu perulangan dan menjelaskan pemisahan berjenjang pada Bab 6.2 *Crafting Interpreters*. Pernyataan itu diverifikasi dengan membaca `_logical()` baris 251–257 dan menjalankan `python -m pytest tests/test_tambahan.py` (test Bug 3 gagal sebelum perbaikan, 5 passed sesudahnya).

---

## Bug 4: Nama Alias dari DELETE Masih Nyangkut ke Query Berikutnya

**Ditemukan oleh:** Darva

**Gejala.** Waktu memeriksa hasil cetakan pohon AST pada file `data/sample/audit.sql` baris 16 dan 18, kami menemukan kejanggalan besar. Di baris 16 ada perintah `DELETE FROM sesi s`. Lalu di baris 18 ada perintah baru `SELECT s.id FROM pengguna u`. Yang aneh, kolom `s.id` di query kedua malah dianggap merujuk ke tabel `sesi` milik query pertama! Padahal menurut SPESIFIKASI.md Bagian 4.5, setiap statement SQL harus berdiri sendiri; setelah satu statement selesai, semua catatan aliasnya harus dibuang dan tidak boleh bocor ke query setelahnya.

**Reproduksi minimal.**
```sql
DELETE FROM sesi s WHERE s.id = 1;
SELECT s.id FROM pengguna u;
```

**Akar masalah.** Di file `crud/resolver.py` pada fungsi `_delete()`, resolver membuka ruangan lingkup baru (*scope*) dengan memanggil `self._push()` untuk mencatat tabel `sesi`. Namun di akhir fungsi, pembuat kode **lupa memanggil `self._pop()`** untuk menutup ruangan tersebut.
Akibatnya, catatan tentang tabel `sesi` masih tertinggal di dalam tumpukan memori (*scope stack*). Waktu query berikutnya dijalankan, query baru tersebut mengira dirinya berada di dalam query `DELETE` sebelumnya.
Sesuai konsep di **Buku *Crafting Interpreters* Bab 11 (Resolving and Binding - Sub-bab 11.3 A Resolver Class)**, setiap kali kita membuka blok/scope (`_push`), kita wajib menutupnya kembali (`_pop`) begitu blok tersebut selesai agar variabel di dalamnya tidak bocor keluar (*scope leak*).

**Peran AI.** Saya menanyakan ke AI kenapa kolom `s.id` pada `SELECT` di baris 18 bisa-bisanya mengenali tabel `sesi` dari baris 16. AI menyarankan untuk mengecek pemanggilan `_pop()` di setiap fungsi resolver. Saat saya cek fungsi `_delete()`, ternyata pemanggilan `_pop()` memang tidak ada sama sekali.

---

## Bug 5: Operator `<>` Terbelah Jadi Dua Token

**Ditemukan oleh:** Dava · **Diperbaiki oleh:** Darva

**Gejala.** SPESIFIKASI.md bagian 2.5 mewajibkan lexer mengambil operator terpanjang (*maximal munch*), jadi `<>` harus keluar sebagai satu token. Untuk mengujinya, query `SELECT id FROM t WHERE a <> 1;` di-tokenisasi lewat `tokenize()`. Hasilnya justru terbelah: `OP '<'` (baris 1, kolom 26) lalu `OP '>'` (baris 1, kolom 27). Parser otomatis kaget karena setelah `<` datang `>` yang tidak ia harapkan — padahal aturan maximal munch jelas dilanggar.

**Reproduksi minimal.**
```sql
SELECT id FROM t WHERE a <> 1;
```
```powershell
python -c "from crud.lexer import tokenize; print(tokenize('SELECT id FROM t WHERE a <> 1;'))"
```

**Akar masalah.** Di `crud/lexer.py`, blok pembaca karakter `<` di `_scan_token()` hanya menguji satu kemungkinan: `op = "<=" if self._match("=") else "<"`. Karena karakter berikutnya bukan `=`, token langsung diputus `"<"`; `>` tidak pernah diuji sebagai pasangan `<`, sehingga jatuh ke pemanggilan `_scan_token()` berikutnya dan berubah jadi token baru.

Menurut *Crafting Interpreters* Bab 4 (*Scanning*, sub-bab 4.5 *Recognizing Lexemes*), operator dua karakter dikenali lewat *lookahead* — mengecek karakter berikutnya sebelum token diputuskan. Di bab yang sama berlaku prinsip *maximal munch*: kalau dua aturan sama-sama cocok, yang terpanjang menang. Kode kita baru menguji `<=`, belum `<>`, jadi aturan terpanjangnya tidak pernah punya kesempatan menang.

**Perbaikan.** Di file `crud/lexer.py` pada fungsi `_scan_token()`, ditambahkan pengecekan `self._match(">")` saat membaca karakter `<` sehingga menghasilkan token `OP '<>'`. Alternatif membiarkan parser menyatukan dua token ditolak karena melanggar aturan maximal munch pada tahap lexer.

**Test regresi.** `test_regresi_bug5_operator_tidak_sama_dengan` di `tests/test_tambahan.py`.

**Peran AI.** Hasil `tokenize()` yang membelah `<>` sempat ditanyakan ke AI. AI menunjuk baris `if ch == "<"` di `lexer.py` yang hanya menguji `=` dan menjelaskan prinsip *maximal munch*. Pernyataan itu diverifikasi dengan membandingkan hasil `tokenize()` dengan daftar operator di SPESIFIKASI.md bagian 2.5.

---

## Bug 6: Statement Valid Setelah Error Ikut Terbuang Sampai Habis

**Ditemukan oleh:** Dava

**Gejala.** SPESIFIKASI.md bagian 6 menetapkan panic mode membuang token sampai dan termasuk `;` berikutnya, lalu lanjutkan dengan statement sesudahnya — setiap statement rusak hanya menghasilkan satu error. Menjalankan `python -m crud.cli data/sample/campuran_error.sql` memang hanya memunculkan satu error: `PARSE ERROR: Baris 4, kolom 17: diharapkan ekspresi, ditemukan 'FROM'`. Yang aneh, dua statement valid di bawahnya — `UPDATE produk SET stok = ...` (baris 6) dan `DELETE FROM keranjang ...` (baris 8) — hilang begitu saja dari `crud_matrix.csv`; isinya cuma `campuran_error.sql,R`. Padahal keduanya bebas error dan seharusnya tetap diproses.

**Reproduksi minimal.**
```sql
SELECT id, nama FROM pelanggan WHERE aktif = 1;
SELECT id nama, FROM pesanan;
UPDATE produk SET stok = stok - 1 WHERE id = :id;
```
```powershell
python -m crud.cli data/sample/campuran_error.sql
```

**Akar masalah.** Di `crud/parser.py`, fungsi `_synchronize()` (baris 90–94) hanya berisi `while not self._at_end(): self._advance()`. Begitu ada error, semua token dibuang terus tanpa pernah berhenti sampai akhir file, jadi statement 3 dan 4 ikut terlanjur dibuang sebelum sempat diparse.

Menurut *Crafting Interpreters* Bab 6 (*Parsing Expressions*, sub-bab 6.3.3 *Synchronizing a recursive descent parser*), `synchronize()` wajib segera berhenti setelah menemukan batas statement berikutnya — bagian dari konsep *panic mode* (sub-bab 6.3.1). Parser hanya "panik" selama statement yang rusak, statement sesudahnya harus selamat; kode kita kehilangan titik berhenti di `;` di dalam loop itu.

**Peran AI.** Hilangnya statement `UPDATE` dan `DELETE` dari matrix sempat ditanyakan ke AI karena keduanya jelas bebas error. AI menyuruh mencermati `_synchronize()`, dan loop-nya memang tidak pernah berhenti di `;`. Pernyataan itu diuji dengan menjalankan CLI pada file tersebut: hanya 1 dari 4 statement yang keluar.

---

## Bug 7: Alias dari Luar Subquery Mengalahkan Alias di Dalam Subquery

**Ditemukan oleh:** Dava

**Gejala.** SPESIFIKASI.md bagian 4.3 mengatur pencarian qualifier berjalan dari scope terdalam ke luar, sehingga alias di dalam subquery menutupi alias serupa di luar (*shadowing*). Pada query bersarang di `data/sample/audit.sql` baris 12–14, `SELECT x.id FROM pelanggan x WHERE x.id IN (SELECT x.pelanggan_id FROM pesanan x WHERE x.total > 500000);`, kolom `x.pelanggan_id` justru di-resolve ke `pelanggan` — alias milik query luar. Seharusnya hasilnya `pesanan`, karena tabel di subquery memang `pesanan`.

**Reproduksi minimal.**
```sql
SELECT x.id FROM pelanggan x
WHERE x.id IN (SELECT x.pelanggan_id FROM pesanan x WHERE x.total > 500000);
```
Resolve query tersebut, lalu cetak `resolved` milik kolom di dalam subquery → keluar `pelanggan`, harusnya `pesanan`.

**Akar masalah.** Di `crud/resolver.py`, fungsi `_lookup()` (baris 87–97) membangun rantai scope dari dalam ke luar (`chain[0]` = scope terdalam), tapi perulangannya ditulis `for scope in reversed(chain):` — pencarian justru dimulai dari scope terluar. Karena yang pertama ketemu langsung dipakai, nama dari scope paling luar selalu menang dan scope dalam tidak pernah sempat dicek.

Menurut *Crafting Interpreters* Bab 11 (*Resolving and Binding*, sub-bab 11.3 *A Resolver Class*), resolver mencari variabel dari lingkup paling dalam ke induknya dan berhenti di yang pertama ketemu, sama seperti rantai Environment. `reversed()` membalik urutan itu, jadi lingkup luar menutupi yang dalam — shadowing rusak dan subquery korelasi ikut salah.

**Peran AI.** Kekalahan alias `x` di subquery terhadap alias `x` di query luar sempat ditanyakan ke AI. AI mengarahkan ke fungsi `_lookup()` dan menunjuk `reversed(chain)`. Pernyataan itu diverifikasi dengan menjalankan resolve pada query di atas dan mencetak `resolved` kolom di dalam subquery: keluar `pelanggan`, harusnya `pesanan`.

---

## Bug 8: Subquery di UPDATE Dikasih Operasi U, Harusnya R

**Ditemukan oleh:** Dava

**Gejala.** SPESIFIKASI.md bagian 5 tegas: membaca tabel lewat subquery **selalu** `R`, apa pun jenis statement luarnya — berlaku juga untuk subquery di `SET` maupun `WHERE` pada `UPDATE`. Menjalankan analyzer pada statement `UPDATE pesanan SET status = 'BATAL' WHERE pelanggan_id IN (SELECT id FROM pelanggan WHERE diblokir = 1);` (audit.sql baris 20–21) menghasilkan `{'pesanan': {'U'}, 'pelanggan': {'U'}}`: tabel `pelanggan` di dalam subquery ikut-ikutan dapat `U`. Nilai yang benar adalah `{'pesanan': {'U'}, 'pelanggan': {'R'}}`.

**Reproduksi minimal.**
```sql
UPDATE pesanan SET status = 'BATAL'
WHERE pelanggan_id IN (SELECT id FROM pelanggan WHERE diblokir = 1);
```
```text
hasil analyze_statement() saat ini : {'pesanan': {'U'}, 'pelanggan': {'U'}}
seharusnya                        : {'pesanan': {'U'}, 'pelanggan': {'R'}}
```

**Akar masalah.** Di `crud/analyzer.py`, `analyze_statement()` (baris 19–23) menandai tabel target `UPDATE` dengan `U` — itu sudah benar. Masalahnya, dua baris setelahnya op `"U"` ikut diteruskan ke `_collect()` untuk ekspresi `SET` dan `WHERE`: `_collect(assignment.value, usage, "U")` dan `_collect(stmt.where, usage, "U")`. Padahal tugas `_collect` menandai semua tabel di dalamnya dengan op yang diteruskan, sehingga subquery ikut-ikutan `U`. Sebagai pembanding, penanganan `DELETE` di baris 26 sudah benar: `_collect(stmt.where, usage, "R")`. Jadi akar masalahnya cuma op yang salah pilih saat memanggil `_collect` untuk `SET` dan `WHERE`.

Aturan ini aturan lokal proyek (SPESIFIKASI.md Bagian 5), bukan dari buku, jadi patokannya tabel CRUD di spesifikasi.

**Peran AI.** Subquery `UPDATE` yang menerima `U` padahal isinya hanya dibaca sempat ditanyakan ke AI. AI membandingkan penanganan `UPDATE` dengan `DELETE` di file yang sama dan menunjuk beda op yang diteruskan ke `_collect()`. Pernyataan itu diverifikasi dengan menjalankan `analyze_statement()` pada query di atas.