"""Test tambahan buatan kelompok.

Isi dengan:
1. Satu test regresi untuk setiap bug yang kalian perbaiki (gagal sebelum perbaikan,
   lulus sesudahnya). Beri nama yang menjelaskan bug-nya.
2. Lima test kasus tepi, masing-masing dengan komentar singkat mengapa kasus itu berisiko.
"""
import pytest
from crud.lexer import TokenType as T, tokenize

def test_regresi_bug1_keyword_huruf_kecil():
    toks = tokenize("select id from t where aktif = 1")
    assert toks[0].type == T.KEYWORD and toks[0].value == "SELECT"
    assert toks[2].type == T.KEYWORD and toks[2].value == "FROM"
    assert toks[4].type == T.KEYWORD and toks[4].value == "WHERE"
    
def test_regresi_bug2_escape_kutip_ganda_dalam_string():
    toks = tokenize("SELECT 'O''Brien' FROM t")
    assert toks[1].type == T.STRING and toks[1].value == "O'Brien"
    assert sum(t.type == T.STRING for t in toks) == 1

def test_regresi_bug5_operator_tidak_sama_dengan():
    toks = tokenize("SELECT id FROM t WHERE a <> 1")
    ops = [t.value for t in toks if t.type == T.OP]
    assert ops == ["<>"]