"""Test tambahan buatan kelompok.

Isi dengan:
1. Satu test regresi untuk setiap bug yang kalian perbaiki (gagal sebelum perbaikan,
   lulus sesudahnya). Beri nama yang menjelaskan bug-nya.
2. Lima test kasus tepi, masing-masing dengan komentar singkat mengapa kasus itu berisiko.
"""
import pytest
from crud.lexer import TokenType as T, tokenize
from crud.parser import parse_sql

def test_regresi_bug1_keyword_huruf_kecil():
    toks = tokenize("select id from t where aktif = 1")
    assert toks[0].type == T.KEYWORD and toks[0].value == "SELECT"
    assert toks[2].type == T.KEYWORD and toks[2].value == "FROM"
    assert toks[4].type == T.KEYWORD and toks[4].value == "WHERE"
    
def test_regresi_bug2_escape_kutip_ganda_dalam_string():
    toks = tokenize("SELECT 'O''Brien' FROM t")
    assert toks[1].type == T.STRING and toks[1].value == "O'Brien"
    assert sum(t.type == T.STRING for t in toks) == 1
    
def test_regresi_bug3_and_lebih_kuat_dari_or():
    """SPESIFIKASI.md 3.1: a = 1 OR (b = 2 AND c = 3), bukan (a OR b) AND c."""
    script = parse_sql("SELECT id FROM t WHERE a = 1 OR b = 2 AND c = 3;")
    assert script.errors == [], script.errors
    where = script.statements[0].where
    assert where.op == "OR"            # OR jadi root (derajat terendah)
    assert where.right.op == "AND"     # kelompok AND jadi anak kanan OR
    assert where.left.op == "="        # a = 1 di kiri OR

def test_tepi_campuran_and_or_urutan_terbalik():
    """Kasus tepi: AND dulu baru OR - kelompok AND harus mengikat lebih erat
    di sisi kiri, bukan terbawa ke kanan. Risiko: salah menentukan sisi anak."""
    script = parse_sql("SELECT id FROM t WHERE a = 1 AND b = 2 OR c = 3;")
    where = script.statements[0].where
    assert where.op == "OR" and where.left.op == "AND" and where.right.op == "="

def test_regresi_bug5_operator_tidak_sama_dengan():
    toks = tokenize("SELECT id FROM t WHERE a <> 1")
    ops = [t.value for t in toks if t.type == T.OP]
    assert ops == ["<>"]

def test_regresi_bug6_panic_mode_lanjut_ke_statement_berikutnya():
    sql = """
    SELECT id FROM pelanggan;
    SELECT id nama, FROM pesanan;
    UPDATE produk SET stok = 1;
    """
    script = parse_sql(sql)
    assert len(script.errors) == 1
    assert len(script.statements) == 2