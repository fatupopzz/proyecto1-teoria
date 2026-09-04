#!/usr/bin/env python3
"""Pruebas de validacion del pipeline completo.

Verifica que el AFN, el AFD y el AFD minimizado (por los dos metodos de
minimizacion) coincidan siempre en la respuesta, y que esa respuesta sea la
esperada. Tambien comprueba que agrupacion y Myhill-Nerode produzcan
exactamente el mismo AFD minimo.

Uso: python tests.py
"""

from src.shunting_yard import a_postfix
from src.thompson import construir_afn
from src.subconjuntos import construir_afd
from src.minimizacion import minimizar, verificar_equivalencia
from src.simulacion import simular_afn, simular_afd

# (regex, cadena, resultado esperado)
CASOS = [
    ("(b|b)*abb(a|b)*", "babbaaaa", True),
    ("(b|b)*abb(a|b)*", "bbbabb", True),
    ("(b|b)*abb(a|b)*", "aab", False),
    ("(b|b)*abb(a|b)*", "", False),
    ("(a*|b*)c", "aaac", True),
    ("(a*|b*)c", "abc", False),
    ("(a*|b*)c", "c", True),
    ("a*", "", True),
    ("a*", "aaaa", True),
    ("a*", "b", False),
    ("a+", "", False),
    ("a+", "aaa", True),
    ("a?", "", True),
    ("a?", "a", True),
    ("a?", "aa", False),
    ("ε", "", True),
    ("ε", "a", False),
    ("(a|ε)b", "b", True),
    ("(a|ε)b", "ab", True),
    ("(a|b)*a(a|b)(a|b)", "abab", False),
    ("(a|b)*a(a|b)(a|b)", "baab", True),
    ("(0|1)*1(0|1)(0|1)", "1100", True),
    ("(0|1)*1(0|1)(0|1)", "0000", False),
    ("a\\*b", "a*b", True),
    ("a\\*b", "aab", False),
    ("(ab)+", "ababab", True),
    ("(ab)+", "aba", False),
    ("b*ab?", "bbba", True),
    ("(a|b)*abb", "aababb", True),
    ("(a|b)*abb", "aabab", False),
]


def correr():
    fallos = 0
    for i, (regex, cadena, esperado) in enumerate(CASOS, 1):
        tokens, postfix = a_postfix(regex)
        afn = construir_afn(tokens)
        afd = construir_afd(afn)
        metodos_ok, afd_min, afd_myhill = verificar_equivalencia(afd)

        r_afn, _ = simular_afn(afn, cadena)
        r_afd, _ = simular_afd(afd, cadena)
        r_min, _ = simular_afd(afd_min, cadena)
        r_myhill, _ = simular_afd(afd_myhill, cadena)

        coinciden = r_afn == r_afd == r_min == r_myhill and metodos_ok
        correcto = coinciden and r_afn == esperado
        marca = "OK  " if correcto else "FALLA"

        if not correcto:
            fallos += 1

        print(f"{marca} [{i:02d}] r = {regex:<22} w = {cadena or '(vacia)':<10} "
              f"AFN={r_afn} AFD={r_afd} MIN={r_min} MYHILL={r_myhill} "
              f"esperado={esperado}"
              f"   postfix: {postfix}")

    print("\n" + "-" * 60)
    print(f"{len(CASOS) - fallos}/{len(CASOS)} pruebas correctas")
    return fallos


if __name__ == '__main__':
    exit(1 if correr() else 0)
