# Laporan Akhir

## 1. Hasil evaluasi

Berikut adalah keluaran eksekusi `python evaluate.py` setelah seluruh berkas sampel pada `data/ground_truth.csv` dilengkapi (27 triple):

```text
Dievaluasi: audit.sql, campuran_error.sql, laporan_penjualan.sql, pemeliharaan.sql (27 triple)

Metode   Precision  Recall     F1
parser        1.00    1.00   1.00
regex         0.65    0.81   0.72

[regex]
  salah ditemukan (FP): ('audit.sql', 16, 'sesi', 'R')
  salah ditemukan (FP): ('campuran_error.sql', 4, 'pesanan', 'R')
  salah ditemukan (FP): ('campuran_error.sql', 8, 'keranjang', 'R')
  salah ditemukan (FP): ('laporan_penjualan.sql', 2, 'pelanggan', 'D')
  salah ditemukan (FP): ('laporan_penjualan.sql', 2, 'pelanggan', 'R')
  salah ditemukan (FP): ('laporan_penjualan.sql', 2, 'pesanan', 'R')
  salah ditemukan (FP): ('laporan_penjualan.sql', 2, 'rahasia', 'R')
  salah ditemukan (FP): ('laporan_penjualan.sql', 15, 'pesanan', 'R')
  salah ditemukan (FP): ('pemeliharaan.sql', 2, 'crm.alamat', 'R')
  salah ditemukan (FP): ('pemeliharaan.sql', 2, 'crm.pelanggan', 'R')
  salah ditemukan (FP): ('pemeliharaan.sql', 2, 'pelanggan_lama', 'U')
  salah ditemukan (FP): ('pemeliharaan.sql', 15, 'crm.alamat', 'R')
  terlewat (FN):       ('audit.sql', 2, 'pesanan', 'R')
  terlewat (FN):       ('laporan_penjualan.sql', 3, 'pelanggan', 'R')
  terlewat (FN):       ('laporan_penjualan.sql', 3, 'pesanan', 'R')
  terlewat (FN):       ('pemeliharaan.sql', 3, 'crm.alamat', 'R')
  terlewat (FN):       ('pemeliharaan.sql', 3, 'crm.pelanggan', 'R')
```

---

## 2. Tiga kasus di mana regex salah

Dari hasil evaluasi di atas, pendekatan *regular expression* (regex) mengalami kegagalan pada tiga tahapan kompilasi yang berbeda:

### Kasus 1: Kegagalan Tahap Lexing (Komentar Blok Dianggap Query Aktif)
* **SQL:**  
  `data/sample/pemeliharaan.sql` baris 2:
  ```sql
  /* Catatan lama: UPDATE pelanggan_lama SET aktif = 0 WHERE id = 1; */
  ```
* **Kesalahan Regex:**  
  Regex menghasilkan *False Positive* `('pemeliharaan.sql', 2, 'pelanggan_lama', 'U')`. Regex mencocokkan pola string mentah kata kunci `UPDATE ... SET` tanpa memahami apakah teks tersebut berada di dalam komentar atau bukan.
* **Mengapa Parser Benar (Konsep Lexing):**  
  Pada tahap *lexical analysis* (`crud/lexer.py`), scanner mengenali penanda komentar blok `/*` dan mengonsumsi seluruh karakter hingga penutup `*/` tanpa menghasilkan token gramatika ke parser. Akibatnya, teks di dalam komentar sama sekali tidak masuk ke pohon AST dan tidak dihitung sebagai operasi CRUD.

### Kasus 2: Kegagalan Tahap Parsing (Query Multi-baris pada Klausa FROM Terlewat)
* **SQL:**  
  `data/sample/audit.sql` baris 2–3:
  ```sql
  SELECT p.id, p.nama
  FROM pelanggan p,
       pesanan o
  WHERE p.id = o.pelanggan_id;
  ```
* **Kesalahan Regex:**  
  Regex hanya menangkap tabel `pelanggan`, tetapi melewatkan tabel `pesanan` sehingga menghasilkan *False Negative* `('audit.sql', 2, 'pesanan', 'R')`. Pola regex yang berbasis baris (*line-by-line*) atau pola kecocokan lokal gagal menangkap daftar tabel yang dipisahkan oleh tanda koma dan baris baru (*newline*).
* **Mengapa Parser Benar (Konsep Parsing):**  
  Parser memproses aliran token (*token stream*) bebas spasi dan baris baru. Fungsi `_select()` di `crud/parser.py` mengenali aturan gramatika klausa `FROM` yang dapat memuat banyak tabel dipisahkan koma (`table_ref (COMMA table_ref)*`). Kedua tabel berhasil dibaca menjadi simpul `ast.TableRef` di dalam atribut `sources`, sehingga tabel `pesanan` tetap terdeteksi sebagai operasi `R`.

### Kasus 3: Kegagalan Tahap Analisis Semantik (Operasi DELETE Dideteksi sebagai READ)
* **SQL:**  
  `data/sample/audit.sql` baris 16:
  ```sql
  DELETE FROM sesi s
  WHERE s.kedaluwarsa < '2026-01-01';
  ```
* **Kesalahan Regex:**  
  Regex menghasilkan *False Positive* `('audit.sql', 16, 'sesi', 'R')`. Ekstraktor regex menggunakan pola pencarian kata kunci `FROM\s+([a-zA-Z0-9_]+)` yang diasumsikan sebagai operasi pembacaan data (*Read*). Pola ini mengabaikan kata kerja utama statement di depannya (`DELETE`), sehingga operasi penghapusan data justru salah dicatat sebagai operasi baca.
* **Mengapa Parser Benar (Konsep Analisis Semantik):**  
  Parser mengenali tata bahasa secara menyeluruh dan membangun simpul AST yang tepat yaitu `ast.Delete(table=TableRef('sesi', 's'), ...)`. Pada tahap analisis semantik (`crud/analyzer.py`), fungsi `_delete()` memproses simpul tersebut dan secara tegas menetapkan operasi `D` (*Delete*) untuk tabel target `sesi`, bukan operasi `R`.

---

## 3. Batas pendekatan kami

Meskipun seluruh 11 bug bawaan dan 3 fitur TODO telah selesai diperbaiki serta lulus 100% test suite, masih terdapat beberapa keterbatasan arsitektur pada analisis statis ini:

### 1. Common Table Expressions (CTE) / Klausa `WITH ... AS (...)`
* **Contoh Situasi:**
  ```sql
  WITH ringkasan_pesanan AS (
      SELECT pelanggan_id, SUM(total) AS akumulasi
      FROM pesanan
      GROUP BY pelanggan_id
  )
  SELECT p.nama, r.akumulasi
  FROM pelanggan p
  JOIN ringkasan_pesanan r ON p.id = r.pelanggan_id;
  ```
* **Akibat pada CRUD Matrix:**  
  Parser akan memicu `ParseError` karena gramatika saat ini belum mengenal kata kunci `WITH`. Jika kata kunci `WITH` dilewati, tabel sementara `ringkasan_pesanan` akan keliru dicatat sebagai tabel fisik database yang dibaca (`R`), padahal tabel fisik aslinya adalah `pesanan`.
* **Informasi yang Dibutuhkan:**  
  Aturan gramatika parser baru untuk klausa `WITH`, serta tabel simbol sementara pada resolver untuk mencatat derived table/CTE dan menelusuri sumber tabel fisik aslinya.

### 2. SQL Dinamis dan Prosedur Tersimpan (*Stored Procedure*)
* **Contoh Situasi:**
  ```sql
  EXECUTE IMMEDIATE 'UPDATE ' || nama_tabel || ' SET status = 1 WHERE id = ' || id_pengguna;
  ```
* **Akibat pada CRUD Matrix:**  
  Operasi `U` (*Update*) pada tabel target sama sekali tidak akan tercatat di matriks CRUD (*False Negative* total). Analisis kode statis tidak dapat mengevaluasi nilai variabel string yang baru terbentuk saat aplikasi berjalan di runtime.
* **Informasi yang Dibutuhkan:**  
  Dibutuhkan analisis aliran data (*data-flow / taint analysis*) antar-variabel atau pelacakan dinamis melalui log audit mesin database saat query benar-benar dieksekusi.

### 3. Keterbatasan Resolusi Kolom Multi-tabel Tanpa Skema (*Schemaless*)
* **Contoh Situasi:**
  ```sql
  SELECT nama, total
  FROM crm.pelanggan p
  JOIN logistik.pesanan o ON p.id = o.pelanggan_id;
  ```
* **Akibat pada CRUD Matrix:**  
  Operasi tabel tingkat makro tetap tercatat (`crm.pelanggan`: `R`, `logistik.pesanan`: `R`). Namun saat menggunakan opsi `--kolom`, kolom `nama` dan `total` yang tidak memiliki qualifier (`p.nama` atau `o.total`) tidak dapat di-resolve (`resolved = None`) dan hanya memunculkan *warning* ambigu. Matriks ketergantungan kolom menjadi tidak lengkap.
* **Informasi yang Dibutuhkan:**  
  Katalog skema fisik database (file DDL `CREATE TABLE` atau koneksi metadata database langsung) untuk mengetahui daftar kolom yang dimiliki oleh masing-masing tabel.

### 4. Keterbatasan terhadap Relasi Tak Langsung (Database View dan Trigger)
* **Contoh Situasi:**
  ```sql
  -- Query membaca view:
  SELECT * FROM ringkasan_pendapatan;

  -- Query yang memicu trigger:
  UPDATE pesanan SET status = 'selesai' WHERE id = 100;
  ```
  Di dalam database nyata:
  1. `ringkasan_pendapatan` sebenarnya adalah sebuah *VIEW* yang di dalamnya membaca tabel `transaksi`, `pajak`, dan `rekening`.
  2. Saat perintah `UPDATE pesanan` dijalankan, di database terdapat *TRIGGER* `AFTER UPDATE` yang otomatis melakukan `INSERT INTO log_audit` dan `UPDATE saldo_toko`.
* **Akibat pada CRUD Matrix:**  
  Ekstraktor hanya menganalisis teks query yang tertulis secara langsung. Akibatnya, pembacaan tabel dasar di balik *VIEW* (`transaksi`: `R`, `pajak`: `R`) serta operasi otomatis dari *TRIGGER* (`log_audit`: `C`, `saldo_toko`: `U`) tidak akan pernah terdeteksi, sehingga banyak operasi CRUD penting yang luput dari pencatatan (*False Negative*).
* **Informasi yang Dibutuhkan:**  
  Definisi DDL skema database lengkap (`CREATE VIEW ... AS SELECT ...` dan `CREATE TRIGGER ...`), sehingga resolver dapat menelusuri query di balik *VIEW* secara rekursif dan memetakan aksi yang dijalankan oleh *TRIGGER*.

### 5. Dialek Khusus Vendor dan Klausa Campuran (*Multi-Operation Statements*)
* **Contoh Situasi:**
  Sintaks gabungan operasi *Insert-atau-Update* pada berbagai dialek database:
  ```sql
  -- PostgreSQL / SQLite (Upsert):
  INSERT INTO pengguna (id, nama) VALUES (1, 'Budi')
  ON CONFLICT (id) DO UPDATE SET nama = 'Budi';

  -- Oracle / SQL Server / ANSI:2003:
  MERGE INTO pesanan_arsip a USING pesanan p ON (a.id = p.id)
  WHEN MATCHED THEN UPDATE SET a.total = p.total
  WHEN NOT MATCHED THEN INSERT (id, total) VALUES (p.id, p.total);
  ```
* **Akibat pada CRUD Matrix:**  
  Parser saat ini dirancang untuk subset gramatika SQL standar tunggal (`SELECT`, `INSERT`, `UPDATE`, `DELETE` murni). Saat menemukan klausa `MERGE` atau `ON CONFLICT`, parser akan memicu `ParseError` dan membuang statement tersebut lewat *panic recovery*. Akibatnya, kombinasi operasi `C` dan `U` yang terjadi bersamaan pada satu query tersebut gagal diekstrak sama sekali.
* **Informasi yang Dibutuhkan:**  
  Perluasan tata bahasa (*grammar expansion*) pada parser untuk mengenali aturan gramatika khusus dialek vendor (*multi-dialect grammar*), serta dukungan analyzer untuk memetakan satu statement ke lebih dari satu jenis operasi CRUD secara simultan.

---

## 4. Pembagian kerja

Pengerjaan tugas ini dilakukan secara kolaboratif menggunakan metodologi *pair programming* dengan pembagian peran yang seimbang antara **Darva** dan **Dava**:

### Pembagian Tugas Utama:
* **Darva:**
  - Analisis arsitektur pipeline multi-pass dan penyiapan baseline pengujian.
  - Perbaikan Bug 1 (sensitivitas huruf kapital/kecil pada identifier di lexer).
  - Perbaikan Bug 5 (maximal munch operator `<>` pada lexer).
  - Implementasi Fitur TODO(T3) (penanganan komentar blok multi-baris `/* ... */`).
  - Implementasi Fitur TODO(T1) (parsing klausa `INSERT INTO ... SELECT`).
  - Investigasi & perbaikan Bug 9 (`LEFT OUTER JOIN` melewatkan token `OUTER`).
  - Penambahan edge case test publik `column_usage(stmt)` (Test 1).
  - Penambahan edge case test integrasi end-to-end `pemeliharaan.sql` & `campuran_error.sql` (Test 2).
  - Pelabelan manual ground truth berkas `data/sample/pemeliharaan.sql`.
* **Dava:**
  - Perbaikan Bug 2 (penanganan string escape tanda kutip berurutan `''`).
  - Perbaikan Bug 3 (pemisahan presedensi berjenjang operator `OR` dan `AND`).
  - Perbaikan Bug 4 (keseimbangan push/pop scope pada `DELETE` di resolver).
  - Perbaikan Bug 8 (penyesuaian operasi subquery pada `UPDATE` menjadi `R`).
  - Implementasi Fitur TODO(T2) (resolusi kolom tanpa qualifier terbatas scope terdalam).
  - Investigasi & perbaikan Bug 10 (dukungan subquery berkurung pada `INSERT INTO ... (SELECT)`).
  - Investigasi & perbaikan Bug 11 (perbaikan exit code CLI pada diagnostik resolver error).
  - Penambahan edge case test antarmuka CLI opsi `--detail` dan `--kolom` (Test 3).
  - Pelabelan manual ground truth berkas `data/sample/audit.sql`.
* **Dikerjakan Bersama (Darva & Dava):**
  - Audit kasus tepi bersama AI untuk mengantisipasi *hidden tests*.
  - Penyusunan 5 keputusan desain arsitektur pada `docs/KARTU_DESAIN.md`.
  - Penyusunan analisis regex dan batas arsitektur pada `docs/LAPORAN_AKHIR.md`.
  - Refleksi penggunaan AI pada `docs/LOG_AI.md`.

### Cara Memastikan Keduanya Memahami Seluruh Kode:
1. **Rotasi Driver-Navigator:** Setiap pengerjaan bug atau fitur dilakukan bergantian; jika satu orang menjadi *driver* yang mengetik kode, orang kedua bertindak sebagai *navigator* yang membaca spesifikasi dan memverifikasi logika.
2. **Siklus Test-Driven Development (TDD):** Sebelum kode diperbaiki, kami selalu menulis test regresi terlebih dahulu di `tests/test_tambahan.py` dan membuktikan test tersebut *gagal (fase merah)*. Setelah solusi diterapkan, kami memastikan test *lulus (fase hijau)*.
3. **Verifikasi Silang:** Setiap commit dan Pull Request selalu diuji bersama di komputer masing-masing dengan menjalankan `pytest` (51 test passed) dan `python evaluate.py` (skor 1.00), sehingga kedua anggota siap mempertanggungjawabkan seluruh baris kode saat sesi ujian lisan individual.
