# Laporan Bug

Salin blok di bawah untuk setiap bug. Bagian **Akar masalah** wajib ditulis dengan kata-kata
sendiri dan memakai konsep dari *Crafting Interpreters* (sebutkan bab). Bagian ini diuji lisan.

---

## Bug 1: Kata Kunci Huruf Kecil Salah Dikenali Sebagai Kolom Biasa

**Ditemukan oleh:** Darva

**Gejala.** Waktu pertama kali menjalankan perintah `python -m pytest` di terminal, pengujian di file `tests/test_lexer.py` pada fungsi `test_keyword_huruf_kecil` langsung gagal merah. Saat query seperti `select id from t;` diperiksa, kata `select` tidak dianggap sebagai kata kunci (`KEYWORD`), melainkan dicap sebagai nama kolom biasa (`IDENT`). Padahal menurut SPESIFIKASI.md Bagian 2.2, SQL tidak peduli huruf besar atau kecil (`select`, `Select`, dan `SELECT` itu sama saja) dan nilainya harus otomatis diubah menjadi huruf kapital `SELECT`.

**Reproduksi minimal.**
```sql
select id from t;
```

**Akar masalah.** Di file `crud/lexer.py` pada fungsi `_word()`, pembuat kode mengecek kata kunci dengan baris: `if text in KEYWORDS:`. 
Masalahnya, di Python perbandingan string itu sensitif huruf besar-kecil (*case-sensitive*). Karena daftar `KEYWORDS` isinya huruf besar semua (`SELECT`, `FROM`, dll.), Python merasa `'select'` (huruf kecil) tidak ada di daftar tersebut. Akhirnya kode melompat ke blok `else` dan kata `select` malah dianggap nama kolom biasa (`IDENT`). 
Sesuai penjelasan di **Buku *Crafting Interpreters* Bab 4 (Scanning - Sub-bab 4.7 Reserved Words and Identifiers)**, scanner membedakan kata kunci dan nama kolom dengan mencari kata tersebut di kamus kata kunci. Karena SQL tidak peduli huruf besar-kecil, scanner seharusnya menyamakan format hurufnya dulu (diubah ke kapital dengan `.upper()`) sebelum dicocokkan ke kamus agar tidak keliru menganggap kata kunci sebagai nama kolom biasa.

**Peran AI.** Saya menanyakan ke AI kenapa `select` huruf kecil di pytest bisa gagal padahal katanya SQL tidak sensitif huruf. AI menunjukkan bahwa baris `if text in KEYWORDS` di lexer masih case-sensitive. Saya memverifikasinya sendiri dengan mencoba memanggil `tokenize("select id")` di terminal dan melihat token yang keluar memang `IDENT`.

---

## Bug 2: Tanda Kutip Ganda di Dalam Teks String Terpotong

**Ditemukan oleh:** Darva

**Gejala.** Waktu kami memeriksa file contoh `data/sample/pemeliharaan.sql`, di baris 6 ada tulisan nama orang `'O''Brien'`. Saat kami coba jalankan leksingnya, kata tersebut malah terpotong menjadi `'O'` saja, lalu sisa hurufnya membuat program error. Padahal menurut SPESIFIKASI.md Bagian 2.4, di dalam aturan SQL kalau ada dua tanda kutip tunggal berdampingan (`''`), itu maksudnya bukan penutup kalimat, melainkan cara menulis satu karakter tanda kutip di dalam teks. Jadi `'O''Brien'` seharusnya tetap utuh menjadi satu kata string bernilai `O'Brien`.

**Reproduksi minimal.**
```sql
SELECT 'O''Brien' FROM t;
```

**Akar masalah.** Di file `crud/lexer.py` pada fungsi pembaca string `_string()`, perulangan pembacaan karakter langsung berhenti (`break`) seketika menemukan karakter tanda kutip tunggal `'`. 
Kodenya tidak mengecek karakter berikutnya (*tidak melakukan lookahead*). Padahal tanda kutip dalam SQL punya dua kemungkinan: bisa sebagai penutup kalimat teks, atau sebagai tanda *escape* jika langsung diikuti tanda kutip lagi (`''`).
Sesuai penjelasan di **Buku *Crafting Interpreters* Bab 4 (Scanning - Sub-bab 4.6 Longer Lexemes / String Literals)**, saat membaca teks string yang karakternya punya makna ganda (*escape sequence*), scanner wajib mengintip satu karakter ke depan (*lookahead*) sebelum memutuskan apakah itu tanda penutup string atau bukan.

**Peran AI.** Saya menanyakan ke AI bagaimana sebenarnya SQL membedakan tanda kutip penutup dengan tanda kutip di dalam nama seperti O'Brien tanpa tanda garis miring (backslash). AI menjelaskan konsep escape `''` dan perlunya lookahead. Saya memverifikasinya dengan membaca fungsi `_string()` yang memang langsung berhenti tanpa melihat karakter berikutnya.

---

## Bug 3: Derajat Operator AND dan OR Dianggap Sama Kuat

**Ditemukan oleh:** Darva

**Gejala.** Waktu menjalankan perintah `python -m crud.cli data/sample/audit.sql --ast` di terminal untuk melihat pohon sintaks (AST) pada baris 2, ada query `WHERE ... OR ... AND ...`. Anehnya, di pohon yang dicetak, operator `AND` ditaruh di paling atas (menjadi root), yang artinya query dibaca seolah-olah `(a OR b) AND c`. Padahal menurut SPESIFIKASI.md Bagian 3.1, operator `AND` derajatnya lebih tinggi (tingkat 2) daripada `OR` (tingkat 1), mirip seperti perkalian lebih didahulukan daripada penjumlahan. Jadi seharusnya query dibaca sebagai `a OR (b AND c)`.

**Reproduksi minimal.**
```sql
SELECT id FROM t WHERE a = 1 OR b = 2 AND c = 3;
```

**Akar masalah.** Di file `crud/parser.py`, fungsi `_logical()` menangani kata `AND` dan `OR` di dalam satu perulangan yang sama: `while self._check_kw("AND", "OR"):`. 
Karena digabung, parser menganggap `AND` dan `OR` kekuatannya setara, sehingga parser hanya membaca lurus dari kiri ke kanan (yang datang duluan dikerjakan duluan).
Mengacu pada **Buku *Crafting Interpreters* Bab 6 (Parsing Expressions - Sub-bab 6.2 Precedence and Associativity)**, tata bahasa untuk operator yang beda tingkatan harus dipisah ke fungsi yang berbeda secara berjenjang (*stratified functions*). Fungsi operator berderajat rendah (seperti `OR`) harus memanggil fungsi operator berderajat lebih tinggi (seperti `AND`), bukan disatukan di satu fungsi.

**Peran AI.** Saya menanyakan ke AI kenapa pohon AST di `audit.sql` baris 2 operator `AND`-nya berada di paling luar/atas. AI menjelaskan bahwa fungsi `_logical()` di parser mencampur `AND` dan `OR` jadi satu perulangan. Saya memverifikasinya sendiri dengan membaca alur kode `_logical()` di baris 251 `crud/parser.py`.

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

<!-- Bug 5, 6, 7, 8 akan ditambahkan oleh Dava di branch dava_plp -->
