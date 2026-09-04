#!/usr/bin/env python3
"""
Pruebas exhaustivas del Proyecto 1.

A diferencia de tests.py (30 casos fijos escritos a mano), esta suite genera
miles de casos y los compara contra un ORACULO INDEPENDIENTE: el modulo `re`
de Python. Si nuestro pipeline y `re` discrepan en aunque sea una cadena, hay
un bug.

Ademas verifica invariantes estructurales que deben cumplirse siempre, sin
importar la expresion.

Uso:
    python pruebas_exhaustivas.py            # suite completa
    python pruebas_exhaustivas.py --rapido   # version corta
    python pruebas_exhaustivas.py --semilla 7
"""

import argparse
import itertools
import random
import re
import sys
import time

from src.shunting_yard import a_postfix, validar, EPSILON, UNARIOS, BINARIOS
from src.thompson import construir_afn
from src.subconjuntos import construir_afd, cerradura_epsilon
from src.minimizacion import minimizar, verificar_equivalencia
from src.simulacion import simular_afn, simular_afd

ALFABETO = ['a', 'b']
ANCHO = 74


# ----------------------------------------------------------------------
# Generador de expresiones regulares al azar
# ----------------------------------------------------------------------

def generar_regex(profundidad=3, alfabeto=ALFABETO, rnd=random):
    """Arma una expresion regular al azar, valida por construccion."""
    if profundidad <= 0:
        return rnd.choice(alfabeto)

    forma = rnd.choices(
        ['simbolo', 'epsilon', 'union', 'concat', 'kleene', 'positiva', 'opcional'],
        weights=[30, 4, 16, 24, 10, 8, 8],
    )[0]

    sub = lambda: generar_regex(profundidad - 1, alfabeto, rnd)  # noqa: E731

    if forma == 'simbolo':
        return rnd.choice(alfabeto)
    if forma == 'epsilon':
        return EPSILON
    if forma == 'union':
        return f'({sub()}|{sub()})'
    if forma == 'concat':
        return f'{sub()}{sub()}' if rnd.random() < .5 else f'({sub()}{sub()})'
    # Los unarios se parentizan casi siempre, pero a veces no: si el operando
    # es un solo caracter no hace falta, y sin parentesis se ejercita el caso
    # `ε*`, que es justo el que rompia la traduccion del oraculo.
    operador = {'kleene': '*', 'positiva': '+', 'opcional': '?'}[forma]
    interno = sub()
    if len(interno) == 1 and rnd.random() < .4:
        return f'{interno}{operador}'
    return f'({interno}){operador}'


def traducir(regex):
    """Traduce nuestra sintaxis a la del modulo `re` de Python.

    La unica diferencia relevante es epsilon. Se emite como `(?:)`, un grupo
    vacio que no captura, y NO como la cadena vacia: borrarlo sin mas rompe
    la traduccion cuando lleva un operador detras. Con `replace(EPSILON, '')`,
    `aε*b` se convierte en `a*b`, que acepta `aaab` cuando el lenguaje real
    es `{ab}`, y `ε*` da directamente `re.error: nothing to repeat`.
    El oraculo mentiria en silencio, que es peor que fallar.
    """
    return regex.replace(EPSILON, '(?:)')


def cadenas_hasta(n, alfabeto=ALFABETO):
    """Todas las cadenas de longitud 0..n sobre el alfabeto."""
    for largo in range(n + 1):
        for tupla in itertools.product(alfabeto, repeat=largo):
            yield ''.join(tupla)


# ----------------------------------------------------------------------
# Infraestructura de reporte
# ----------------------------------------------------------------------

class Reporte:
    def __init__(self):
        self.bloques = []
        self.total = 0
        self.fallas = []

    def bloque(self, nombre):
        print(f'\n{nombre}')
        print('-' * ANCHO)
        self._actual = nombre

    def revisar(self, condicion, detalle):
        self.total += 1
        if not condicion:
            self.fallas.append((self._actual, detalle))
            print(f'  FALLA  {detalle}')
        return condicion

    def nota(self, texto):
        print(f'  {texto}')

    def resumen(self):
        print('\n' + '=' * ANCHO)
        if self.fallas:
            print(f'{len(self.fallas)} FALLAS de {self.total} verificaciones\n')
            for bloque, detalle in self.fallas[:25]:
                print(f'  [{bloque}] {detalle}')
            if len(self.fallas) > 25:
                print(f'  ... y {len(self.fallas) - 25} mas')
        else:
            print(f'TODO CORRECTO — {self.total} verificaciones, 0 fallas')
        print('=' * ANCHO)
        return len(self.fallas)


def construir_todo(regex):
    """Corre el pipeline completo y devuelve los cuatro automatas."""
    tokens, postfix = a_postfix(regex)
    afn = construir_afn(tokens)
    afd = construir_afd(afn)
    min_agr = minimizar(afd, 'agrupacion')
    min_myh = minimizar(afd, 'myhill')
    return postfix, afn, afd, min_agr, min_myh


# ----------------------------------------------------------------------
# 1. Oraculo: comparar contra el modulo `re`
# ----------------------------------------------------------------------

def prueba_oraculo(rep, n_regex, largo_max, rnd):
    rep.bloque(f'1. ORACULO — {n_regex} expresiones al azar contra el modulo `re`')

    comparaciones = 0
    saltadas = 0

    for _ in range(n_regex):
        regex = generar_regex(rnd.randint(2, 4), rnd=rnd)
        patron_py = traducir(regex)

        try:
            compilado = re.compile(patron_py)
        except re.error:
            saltadas += 1
            continue

        try:
            _, afn, afd, min_agr, min_myh = construir_todo(regex)
        except Exception as e:  # noqa: BLE001
            rep.revisar(False, f'{regex!r} no se pudo construir: {e}')
            continue

        for w in cadenas_hasta(largo_max):
            esperado = compilado.fullmatch(w) is not None
            r_afn, _ = simular_afn(afn, w)
            r_afd, _ = simular_afd(afd, w)
            r_agr, _ = simular_afd(min_agr, w)
            r_myh, _ = simular_afd(min_myh, w)
            comparaciones += 1

            if not (r_afn == r_afd == r_agr == r_myh == esperado):
                rep.revisar(False,
                            f'r={regex!r} w={w!r}: re={esperado} '
                            f'AFN={r_afn} AFD={r_afd} '
                            f'MIN_agr={r_agr} MIN_myh={r_myh}')
                break
        else:
            rep.revisar(True, '')

    rep.nota(f'{comparaciones} comparaciones contra `re` '
             f'({saltadas} expresiones saltadas por incompatibilidad)')


# ----------------------------------------------------------------------
# 2. Invariantes estructurales
# ----------------------------------------------------------------------

def prueba_invariantes(rep, n_regex, rnd):
    rep.bloque(f'2. INVARIANTES — {n_regex} expresiones')

    for _ in range(n_regex):
        regex = generar_regex(rnd.randint(2, 4), rnd=rnd)
        try:
            postfix, afn, afd, min_agr, min_myh = construir_todo(regex)
        except Exception as e:  # noqa: BLE001
            rep.revisar(False, f'{regex!r} no se construyo: {e}')
            continue

        etq = f'r={regex!r}'

        # --- Thompson ---
        rep.revisar(len(afn.aceptacion) == 1,
                    f'{etq}: el AFN de Thompson debe tener 1 solo estado de '
                    f'aceptacion, tiene {len(afn.aceptacion)}')

        n_simbolos = sum(1 for t in postfix
                         if t not in UNARIOS and t not in BINARIOS)
        rep.revisar(len(afn.estados) <= 2 * len(postfix),
                    f'{etq}: el AFN tiene {len(afn.estados)} estados, '
                    f'mas de 2n para n={len(postfix)}')

        # el estado de aceptacion del AFN no tiene transiciones de salida
        final = next(iter(afn.aceptacion))
        salidas = [k for k in afn.transiciones if k[0] == final]
        rep.revisar(not salidas,
                    f'{etq}: el estado de aceptacion del AFN tiene salidas: '
                    f'{salidas}')

        # epsilon nunca esta en el alfabeto
        rep.revisar(EPSILON not in afn.alfabeto,
                    f'{etq}: epsilon se coló en el alfabeto del AFN')

        # --- Subconjuntos ---
        rep.revisar(afd.inicio == 0, f'{etq}: el AFD no arranca en el estado 0')
        rep.revisar(afd.alfabeto == afn.alfabeto,
                    f'{etq}: el alfabeto cambió entre AFN y AFD')

        # determinismo: el dict ya lo garantiza, pero verificamos el tipo
        for (origen, simbolo), destino in afd.transiciones.items():
            if not isinstance(destino, int):
                rep.revisar(False, f'{etq}: transicion no determinista en '
                                   f'({origen}, {simbolo})')
                break
        else:
            rep.revisar(True, '')

        # todos los estados del AFD son alcanzables por construccion
        alcanzables = {afd.inicio}
        pila = [afd.inicio]
        while pila:
            e = pila.pop()
            for s in afd.alfabeto:
                d = afd.mover(e, s)
                if d is not None and d not in alcanzables:
                    alcanzables.add(d)
                    pila.append(d)
        rep.revisar(alcanzables == afd.estados,
                    f'{etq}: el AFD tiene estados inalcanzables: '
                    f'{sorted(afd.estados - alcanzables)}')

        # --- Minimizacion ---
        rep.revisar(len(min_agr.estados) <= len(afd.estados),
                    f'{etq}: el minimo tiene MAS estados que el AFD '
                    f'({len(min_agr.estados)} > {len(afd.estados)})')

        rep.revisar(len(min_agr.estados) == len(min_myh.estados),
                    f'{etq}: los dos metodos dan distinto tamaño '
                    f'({len(min_agr.estados)} vs {len(min_myh.estados)})')

        rep.revisar(min_agr.transiciones == min_myh.transiciones
                    and min_agr.aceptacion == min_myh.aceptacion
                    and min_agr.inicio == min_myh.inicio,
                    f'{etq}: los dos metodos dan AFDs distintos')

        # idempotencia: minimizar lo ya minimo no cambia nada
        otra_vez = minimizar(min_agr, 'agrupacion')
        rep.revisar(len(otra_vez.estados) == len(min_agr.estados),
                    f'{etq}: minimizar dos veces cambia el resultado '
                    f'({len(min_agr.estados)} -> {len(otra_vez.estados)})')


# ----------------------------------------------------------------------
# 3. Minimalidad real: ningun par de estados equivalentes sobrevive
# ----------------------------------------------------------------------

def _distinguibles(afd, largo=8):
    """Devuelve los pares de estados que NINGUNA cadena corta distingue."""
    estados = sorted(afd.estados)
    sospechosos = []
    for i, p in enumerate(estados):
        for q in estados[i + 1:]:
            iguales = True
            for w in cadenas_hasta(largo, sorted(afd.alfabeto) or ['a']):
                if _acepta_desde(afd, p, w) != _acepta_desde(afd, q, w):
                    iguales = False
                    break
            if iguales:
                sospechosos.append((p, q))
    return sospechosos


def _acepta_desde(afd, estado, cadena):
    actual = estado
    for simbolo in cadena:
        actual = afd.mover(actual, simbolo)
        if actual is None:
            return False
    return actual in afd.aceptacion


def prueba_minimalidad(rep, n_regex, rnd):
    rep.bloque(f'3. MINIMALIDAD — {n_regex} expresiones, por fuerza bruta')

    for _ in range(n_regex):
        regex = generar_regex(rnd.randint(2, 3), rnd=rnd)
        try:
            _, _, _, min_agr, _ = construir_todo(regex)
        except Exception:  # noqa: BLE001
            continue

        if len(min_agr.estados) > 12:
            continue  # la fuerza bruta se pone cara

        equivalentes = _distinguibles(min_agr, largo=7)
        rep.revisar(not equivalentes,
                    f'r={regex!r}: el AFD "minimo" todavia tiene pares '
                    f'equivalentes: {equivalentes}')

        # ningun estado muerto: desde todos se llega a aceptar
        for e in min_agr.estados:
            alcanza = any(_acepta_desde(min_agr, e, w)
                          for w in cadenas_hasta(7, sorted(min_agr.alfabeto)))
            rep.revisar(alcanza,
                        f'r={regex!r}: el estado {e} del minimo esta muerto')


# ----------------------------------------------------------------------
# 4. Casos limite y entradas hostiles
# ----------------------------------------------------------------------

CASOS_VALIDOS = [
    # (regex, cadenas que acepta, cadenas que rechaza)
    ('a', ['a'], ['', 'aa', 'b']),
    (EPSILON, [''], ['a']),
    ('a*', ['', 'a', 'aaaaaaaaaa'], ['b', 'ab']),
    ('a+', ['a', 'aaa'], ['', 'b']),
    ('a?', ['', 'a'], ['aa']),
    ('(a)', ['a'], ['', 'aa']),
    ('((((a))))', ['a'], ['', 'aa']),
    ('(a*)*', ['', 'a', 'aaaa'], ['b']),
    ('(a|b)**', ['', 'ab', 'ba'], ['c']),
    ('((a|b)*ab)+', ['ab', 'abab', 'aab'], ['', 'a', 'ba']),
    (f'({EPSILON}|a)*b', ['b', 'ab', 'aaab'], ['', 'a']),
    (f'a{EPSILON}*b', ['ab'], ['', 'a', 'b', 'aab']),
    ('a\\*b', ['a*b'], ['ab', 'aab']),
    ('\\(a\\|b\\)', ['(a|b)'], ['a', 'ab']),
    ('a\\\\b', ['a\\b'], ['ab']),
    ('a.b', ['ab'], ['a.b', 'axb']),          # el punto es concatenacion
    ('a b', ['ab'], ['a b']),                  # los espacios se ignoran
    ('(A|b)*', ['', 'A', 'Ab', 'bA'], ['a']),  # mayusculas
    ('$|@', ['$', '@'], ['', '$@']),           # simbolos no alfanumericos
    ('(0|1)*00', ['00', '1100', '000'], ['', '0', '01']),
]

CASOS_INVALIDOS = [
    '', '   ', '*', '+', '?', '|', '||', '()', '(', ')', '(a', 'a)',
    'a|', '|a', '(|a)', '\\', 'a\\',
]


def prueba_casos_limite(rep):
    rep.bloque(f'4. CASOS LIMITE — {len(CASOS_VALIDOS)} validos, '
               f'{len(CASOS_INVALIDOS)} invalidos')

    for regex, aceptadas, rechazadas in CASOS_VALIDOS:
        try:
            _, afn, afd, min_agr, min_myh = construir_todo(regex)
        except Exception as e:  # noqa: BLE001
            rep.revisar(False, f'{regex!r} deberia construirse: {e}')
            continue

        for w, esperado in ([(x, True) for x in aceptadas]
                            + [(x, False) for x in rechazadas]):
            resultados = [
                simular_afn(afn, w)[0],
                simular_afd(afd, w)[0],
                simular_afd(min_agr, w)[0],
                simular_afd(min_myh, w)[0],
            ]
            rep.revisar(all(r == esperado for r in resultados),
                        f'r={regex!r} w={w!r}: esperado {esperado}, '
                        f'obtenido {resultados}')

    for regex in CASOS_INVALIDOS:
        try:
            validar(regex)
            construir_todo(regex)
            rep.revisar(False, f'{regex!r} deberia ser rechazada y no lo fue')
        except ValueError:
            rep.revisar(True, '')          # el error correcto
        except Exception as e:  # noqa: BLE001
            rep.revisar(False, f'{regex!r} lanzo {type(e).__name__} '
                               f'en vez de ValueError: {e}')


# ----------------------------------------------------------------------
# 5. Estres: expresiones grandes y cadenas largas
# ----------------------------------------------------------------------

def prueba_estres(rep):
    rep.bloque('5. ESTRES — expresiones grandes y cadenas largas')

    # a) anidamiento profundo
    profunda = '(' * 25 + 'a' + ')' * 25 + '*'
    try:
        _, afn, afd, min_agr, _ = construir_todo(profunda)
        rep.revisar(simular_afd(min_agr, 'aaaa')[0],
                    'anidamiento de 25 niveles: deberia aceptar "aaaa"')
        rep.nota(f'anidamiento de 25 niveles: AFN {len(afn.estados)} estados, '
                 f'minimo {len(min_agr.estados)}')
    except Exception as e:  # noqa: BLE001
        rep.revisar(False, f'anidamiento profundo fallo: {e}')

    # b) union larga
    larga = '|'.join('ab' * (i + 1) for i in range(12))
    try:
        _, afn, afd, min_agr, _ = construir_todo(larga)
        rep.revisar(simular_afd(min_agr, 'abab')[0],
                    'union de 12 ramas: deberia aceptar "abab"')
        rep.nota(f'union de 12 ramas: AFN {len(afn.estados)}, '
                 f'AFD {len(afd.estados)}, minimo {len(min_agr.estados)}')
    except Exception as e:  # noqa: BLE001
        rep.revisar(False, f'union larga fallo: {e}')

    # c) explosion del AFD: el lenguaje "el n-esimo simbolo desde el final
    #    es una a" necesita recordar los ultimos n simbolos, o sea 2^n estados
    for n in range(1, 8):
        regex = '(a|b)*a' + '(a|b)' * (n - 1)
        _, afn, afd, min_agr, _ = construir_todo(regex)
        rep.revisar(len(min_agr.estados) == 2 ** n,
                    f'{regex!r}: el minimo deberia tener {2**n} estados, '
                    f'tiene {len(min_agr.estados)}')
    rep.nota('explosion del AFD verificada para n = 1..7 (2^n estados, '
             'el minimo teorico)')

    # d) cadena larga, tiempo lineal
    _, afn, afd, min_agr, _ = construir_todo('(a|b)*abb')
    w = 'ab' * 20000 + 'abb'
    tiempos = {}
    for nombre, automata, simular in [('AFN', afn, simular_afn),
                                      ('AFD', afd, simular_afd),
                                      ('MIN', min_agr, simular_afd)]:
        inicio = time.perf_counter()
        resultado, _ = simular(automata, w)
        tiempos[nombre] = time.perf_counter() - inicio
        rep.revisar(resultado, f'{nombre}: deberia aceptar la cadena larga')
    rep.nota(f'cadena de {len(w)} simbolos — ' +
             ', '.join(f'{k} {v:.3f}s' for k, v in tiempos.items()))


# ----------------------------------------------------------------------
# 6. Coherencia interna del pipeline
# ----------------------------------------------------------------------

def prueba_coherencia(rep, n_regex, rnd):
    rep.bloque(f'6. COHERENCIA — {n_regex} expresiones')

    for _ in range(n_regex):
        regex = generar_regex(rnd.randint(2, 4), rnd=rnd)
        try:
            _, afn, afd, min_agr, _ = construir_todo(regex)
        except Exception:  # noqa: BLE001
            continue

        etq = f'r={regex!r}'

        # la cadena vacia se acepta sii el inicial del AFD es de aceptacion
        vacia_afn, _ = simular_afn(afn, '')
        rep.revisar(vacia_afn == (afd.inicio in afd.aceptacion),
                    f'{etq}: discrepancia con la cadena vacia entre AFN y AFD')

        # el estado 0 del AFD es la e-closure del inicial del AFN
        cierre = cerradura_epsilon(afn, {afn.inicio})
        acepta_cierre = bool(cierre & afn.aceptacion)
        rep.revisar(acepta_cierre == (afd.inicio in afd.aceptacion),
                    f'{etq}: el estado 0 del AFD no refleja la e-closure '
                    f'del inicial del AFN')

        # las etiquetas de trazabilidad cubren todos los estados
        rep.revisar(set(afd.etiquetas) == afd.estados,
                    f'{etq}: faltan etiquetas de subconjuntos en el AFD')

        # simular con simbolos ajenos al alfabeto siempre rechaza
        ajeno = 'z'
        if ajeno not in afn.alfabeto:
            rep.revisar(not simular_afn(afn, ajeno)[0]
                        and not simular_afd(afd, ajeno)[0]
                        and not simular_afd(min_agr, ajeno)[0],
                        f'{etq}: un simbolo fuera del alfabeto fue aceptado')


# ----------------------------------------------------------------------
# 7. Robustez: basura aleatoria como entrada
# ----------------------------------------------------------------------

BASURA = list('ab()|*+?.\\') + [EPSILON, ' ']


def prueba_robustez(rep, n_entradas, rnd):
    """Ninguna entrada, por absurda que sea, debe lanzar algo que no sea
    ValueError. Un TypeError, un KeyError o un IndexError significan que el
    codigo asumio algo que la entrada no cumplia."""
    rep.bloque(f'7. ROBUSTEZ — {n_entradas} entradas de basura aleatoria')

    validas = 0
    for _ in range(n_entradas):
        largo = rnd.randint(0, 14)
        regex = ''.join(rnd.choice(BASURA) for _ in range(largo))
        try:
            validar(regex)
            construir_todo(regex)
            validas += 1
        except (ValueError, RecursionError):
            pass                    # rechazo legitimo
        except Exception as e:      # noqa: BLE001
            rep.revisar(False, f'{regex!r} lanzo {type(e).__name__}: {e}')

    rep.revisar(True, '')
    rep.nota(f'{validas} resultaron ser expresiones validas y se procesaron; '
             f'el resto se rechazo con ValueError')


# ----------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rapido', action='store_true',
                        help='menos casos, para iterar rapido')
    parser.add_argument('--semilla', type=int, default=None,
                        help='semilla del generador (por defecto, al azar)')
    args = parser.parse_args()

    semilla = args.semilla if args.semilla is not None else random.randrange(10**6)
    rnd = random.Random(semilla)

    n = ((40, 40, 15, 40, 3000) if args.rapido
         else (300, 400, 60, 300, 40000))
    largo = 5 if args.rapido else 6

    print('=' * ANCHO)
    print('PRUEBAS EXHAUSTIVAS — Proyecto 1')
    print(f'semilla: {semilla}   (reproducí con --semilla {semilla})')
    print('=' * ANCHO)

    rep = Reporte()
    inicio = time.perf_counter()

    prueba_oraculo(rep, n[0], largo, rnd)
    prueba_invariantes(rep, n[1], rnd)
    prueba_minimalidad(rep, n[2], rnd)
    prueba_casos_limite(rep)
    prueba_estres(rep)
    prueba_coherencia(rep, n[3], rnd)
    prueba_robustez(rep, n[4], rnd)

    print(f'\nTiempo total: {time.perf_counter() - inicio:.1f}s')
    return rep.resumen()


if __name__ == '__main__':
    sys.exit(1 if main() else 0)
