#!/usr/bin/env python3
"""
Pruebas adversarias del Proyecto 1 (regex -> AFN -> AFD -> AFD minimo).

No repite lo que ya hace tests.py. Ataca el pipeline desde afuera:

    oraculo      Compara contra re.fullmatch de Python, que es una
                 implementacion independiente del mismo lenguaje.
    invariantes  Propiedades estructurales que los algoritmos prometen.
    minimalidad  Fuerza bruta sobre el AFD minimo: ningun par equivalente,
                 ningun estado muerto.
    algebra      Expresiones distintas con el mismo lenguaje deben producir
                 AFDs minimos identicos (el minimo es unico).
    basura       Miles de cadenas al azar como expresion regular: nada
                 puede escaparse que no sea ValueError.
    cli          main.py contra archivos raros (BOM, CRLF, binario, vacio).
    web          Los endpoints de app.py con JSON hostil.
    imagenes     Los PNG deben ser PNG de verdad, no un .dot silencioso.

Uso:
    python pruebas_adversarias.py
    python pruebas_adversarias.py --semilla 12345
    python pruebas_adversarias.py --solo oraculo --iteraciones 2000
    python pruebas_adversarias.py --rapido

Codigo de salida: cantidad de hallazgos (0 si todo paso).
"""

import argparse
import contextlib
import itertools
import os
import random
import re
import signal
import subprocess
import sys
import tempfile
import time
import traceback

RAIZ = os.path.dirname(os.path.abspath(__file__))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

from src.shunting_yard import a_postfix, validar, EPSILON, UNARIOS   # noqa: E402
from src.thompson import construir_afn                               # noqa: E402
from src.subconjuntos import construir_afd                           # noqa: E402
from src.minimizacion import (minimizar, verificar_equivalencia,     # noqa: E402
                              _completar, _particion_por_myhill, TRAMPA)
from src.simulacion import simular_afn, simular_afd                  # noqa: E402
from src.traza_min import traza_myhill, _nombre                      # noqa: E402


# ===================================================================
# Infraestructura de reporte
# ===================================================================

class Reporte:
    """Acumula hallazgos. Se guarda el caso minimo, no solo el mensaje,
    porque un hallazgo sin entrada reproducible no sirve para defender."""

    def __init__(self):
        self.hallazgos = []
        self.comparaciones = 0

    def falla(self, bloque, entrada, esperado, obtenido, nota=''):
        self.hallazgos.append({
            'bloque': bloque, 'entrada': entrada,
            'esperado': esperado, 'obtenido': obtenido, 'nota': nota,
        })
        print(f"  [FALLA] {bloque}")
        print(f"          entrada  : {entrada!r}")
        print(f"          esperado : {esperado}")
        print(f"          obtenido : {obtenido}")
        if nota:
            print(f"          nota     : {nota}")

    def ok(self, texto):
        print(f"  [ok] {texto}")


class TiempoAgotado(Exception):
    pass


_HAY_RELOJ = hasattr(signal, 'SIGALRM') and hasattr(signal, 'setitimer')


@contextlib.contextmanager
def limite_de_tiempo(segundos):
    """Corta el bloque si tarda mas de `segundos`.

    Hace falta por el oraculo, no por el proyecto. El motor `re` de Python
    es de backtracking: un patron con cerraduras anidadas sobre algo que
    acepta la cadena vacia, como (?:(?:(?:)|c)*)+, tarda tiempo exponencial
    en decidir que una cadena NO empareja. El proyecto simula automatas y
    no tiene ese problema, asi que el unico riesgo es que la prueba no
    termine nunca. Si no hay SIGALRM (Windows) el bloque corre sin corte y
    la heuristica de anidamiento se encarga sola."""
    if not _HAY_RELOJ:
        yield
        return

    def campana(*_):
        raise TiempoAgotado()

    previo = signal.signal(signal.SIGALRM, campana)
    signal.setitimer(signal.ITIMER_REAL, segundos)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previo)


# ===================================================================
# Generador de expresiones regulares con traduccion paralela a `re`
# ===================================================================
#
# Se construye un arbol y se renderiza dos veces: una con la sintaxis del
# proyecto y otra con la de `re`. Renderizar desde el mismo arbol garantiza
# que las dos cadenas denotan el mismo lenguaje por construccion, de modo
# que cualquier diferencia de resultado es un bug del proyecto (o de la
# traduccion, que es lo primero que se revisa a mano).
#
# La unica diferencia real entre las dos sintaxis es epsilon: en el proyecto
# se escribe 'e' griega, en `re` es la cadena vacia. Se emite como '(?:)'
# para que siga siendo un atomo y admita '*', '+' y '?' detras.

PRECEDENCIA_AST = {'alt': 1, 'cat': 2, 'star': 3, 'plus': 3, 'opt': 3,
                   'sim': 4, 'eps': 4}

POSTFIJOS = {'star': '*', 'plus': '+', 'opt': '?'}


class Nodo:
    __slots__ = ('clase', 'hijos', 'simbolo')

    def __init__(self, clase, *hijos, simbolo=None):
        self.clase = clase
        self.hijos = hijos
        self.simbolo = simbolo


def generar(rnd, alfabeto, profundidad):
    """Arbol al azar. La profundidad controla que tan anidada sale la
    expresion; con 5 ya salen cosas como ((a|b)+c*)?|((ba)*|c)+ ."""
    if profundidad <= 0:
        if rnd.random() < 0.88:
            return Nodo('sim', simbolo=rnd.choice(alfabeto))
        return Nodo('eps')

    # 'cat' y 'alt' pesan doble para que el arbol crezca a lo ancho y no
    # degenere en una torre de estrellas anidadas, que es un caso facil.
    clase = rnd.choice(['cat', 'cat', 'alt', 'alt',
                        'star', 'plus', 'opt', 'sim'])
    if clase == 'sim':
        return Nodo('sim', simbolo=rnd.choice(alfabeto))
    if clase in ('cat', 'alt'):
        return Nodo(clase,
                    generar(rnd, alfabeto, profundidad - 1),
                    generar(rnd, alfabeto, profundidad - 1))
    return Nodo(clase, generar(rnd, alfabeto, profundidad - 1))


def _envolver(nodo, minimo, dialecto, todo):
    texto = render(nodo, dialecto, todo)
    if not todo and PRECEDENCIA_AST[nodo.clase] >= minimo:
        return texto
    return '(' + texto + ')' if dialecto == 'proy' else '(?:' + texto + ')'


def render(nodo, dialecto, todo=False):
    """dialecto: 'proy' (sintaxis del proyecto) o 're' (sintaxis de Python).

    todo=True parentiza todo, aunque no haga falta. Comparar el resultado
    de las dos versiones es lo que prueba que la precedencia del Shunting
    Yard es la correcta: si difieren, el parser esta agrupando mal."""
    c = nodo.clase
    if c == 'sim':
        s = nodo.simbolo
        if dialecto == 'proy':
            # En el proyecto todo simbolo que colisiona con un operador se
            # escapa con '\'. Escapar de mas tambien debe funcionar.
            return '\\' + s if s in '()|*+?.\\' else s
        return re.escape(s)
    if c == 'eps':
        return EPSILON if dialecto == 'proy' else '(?:)'
    if c == 'cat':
        return ''.join(_envolver(h, 2, dialecto, todo) for h in nodo.hijos)
    if c == 'alt':
        return '|'.join(_envolver(h, 1, dialecto, todo) for h in nodo.hijos)
    return _envolver(nodo.hijos[0], 4, dialecto, todo) + POSTFIJOS[c]


def anidamiento_cerraduras(nodo):
    """Cuantas cerraduras sin cota (* o +) hay anidadas en el camino mas
    profundo del arbol.

    Sirve para protegerse del oraculo, no del proyecto: el motor `re` de
    Python es de backtracking, y un patron como (?:(?:b?)*)+ dentro de otra
    estrella tarda tiempo exponencial en el largo de la cadena que NO
    empareja. El proyecto, que simula automatas, no tiene ese problema. Para
    que la prueba termine se acortan las cadenas cuando el patron es de ese
    tipo; las cortas siguen corriendose completas."""
    propio = 1 if nodo.clase in ('star', 'plus') else 0
    if not nodo.hijos:
        return propio
    return propio + max(anidamiento_cerraduras(h) for h in nodo.hijos)


def compilar(regex):
    """Corre el pipeline entero y devuelve todas las piezas."""
    validar(regex)
    tokens, postfix = a_postfix(regex)
    afn = construir_afn(tokens)
    afd = construir_afd(afn)
    coinciden, min_agr, min_myh = verificar_equivalencia(afd)
    return tokens, postfix, afn, afd, min_agr, min_myh, coinciden


def huella(afd):
    """Identidad estructural de un AFD, para comparar dos AFDs minimos.

    Como minimizar() renumera los bloques por BFS desde el inicial y luego
    compacta, dos AFDs minimos del mismo lenguaje deben dar la misma huella
    caracter por caracter."""
    return (sorted(afd.estados), afd.inicio, sorted(afd.aceptacion),
            sorted(afd.transiciones.items()), sorted(afd.alfabeto))


def cadenas_exhaustivas(alfabeto, largo):
    out = ['']
    for n in range(1, largo + 1):
        out.extend(''.join(t) for t in itertools.product(alfabeto, repeat=n))
    return out


# ===================================================================
# 1. ORACULO INDEPENDIENTE
# ===================================================================

def bloque_oraculo(rep, rnd, iteraciones):
    print("\n[1] ORACULO: comparacion contra re.fullmatch")
    letras = ['a', 'b', 'c', 'd', 'e']
    fallas = 0
    cortadas = 0

    for it in range(iteraciones):
        n = rnd.randint(2, 5)
        alfabeto = letras[:n]
        # Alfabetos con simbolos que son operadores: obligan a pasar por el
        # camino del escape, que es donde un tokenizador suele romperse.
        if it % 4 == 3:
            alfabeto = rnd.sample(['a', 'b', '*', '|', '(', ')', '?', '+',
                                   '.', '\\'], n)
        arbol = generar(rnd, alfabeto, rnd.randint(1, 5))
        r_proy = render(arbol, 'proy')
        r_re = render(arbol, 're')

        try:
            _, _, afn, afd, m_agr, m_myh, _ = compilar(r_proy)
        except Exception as e:
            rep.falla('oraculo/construccion', r_proy, 'pipeline completo',
                      f'{type(e).__name__}: {e}')
            fallas += 1
            continue

        # Cortas exhaustivas (donde viven casi todos los bugs) mas unas
        # largas al azar (para pegarle a ciclos y a la cerradura epsilon).
        # Con cerraduras muy anidadas se acortan las largas: el que se
        # ahoga ahi es `re`, no el proyecto.
        pruebas = cadenas_exhaustivas(alfabeto, 3 if n > 3 else 4)
        anidadas = anidamiento_cerraduras(arbol)
        tope = 14 if anidadas < 2 else (8 if anidadas == 2 else 0)
        if tope:
            pruebas += [''.join(rnd.choice(alfabeto)
                                for _ in range(rnd.randint(5, tope)))
                        for _ in range(40)]

        patron = re.compile(r_re)
        discrepancia = None
        try:
            # El corte por tiempo nunca puede tapar un hallazgo: si salta,
            # es dentro de patron.fullmatch(), antes de comparar nada.
            with limite_de_tiempo(5.0):
                for w in pruebas:
                    esperado = patron.fullmatch(w) is not None
                    r1 = simular_afn(afn, w)[0]
                    r2 = simular_afd(afd, w)[0]
                    r3 = simular_afd(m_agr, w)[0]
                    r4 = simular_afd(m_myh, w)[0]
                    rep.comparaciones += 4
                    if not (esperado == r1 == r2 == r3 == r4):
                        discrepancia = (w, esperado, r1, r2, r3, r4)
                        break
        except TiempoAgotado:
            cortadas += 1

        if discrepancia:
            w, esperado, r1, r2, r3, r4 = discrepancia
            rep.falla('oraculo', f'r={r_proy!r} w={w!r}',
                      f're.fullmatch = {esperado}',
                      f'AFN={r1} AFD={r2} min_agr={r3} min_myh={r4}',
                      f'equivalente en sintaxis re: {r_re!r}')
            fallas += 1

    if not fallas:
        rep.ok(f"{iteraciones} expresiones, {rep.comparaciones} "
               f"comparaciones, cero discrepancias con re "
               f"({cortadas} cortadas por lentitud del motor `re`)")


# ===================================================================
# 2. INVARIANTES ESTRUCTURALES
# ===================================================================

def bloque_invariantes(rep, rnd, iteraciones):
    print("\n[2] INVARIANTES ESTRUCTURALES")
    letras = ['a', 'b', 'c']
    fallas = 0

    for _ in range(iteraciones):
        alfabeto = letras[:rnd.randint(2, 3)]
        arbol = generar(rnd, alfabeto, rnd.randint(1, 4))
        r = render(arbol, 'proy')
        tokens, _, afn, afd, m_agr, m_myh, coinciden = compilar(r)

        # -- Thompson: un solo estado de aceptacion --------------------
        if len(afn.aceptacion) != 1:
            rep.falla('invariante/afn-aceptacion-unica', r,
                      '1 estado de aceptacion', len(afn.aceptacion))
            fallas += 1
            continue
        final = next(iter(afn.aceptacion))

        # -- ...y sin transiciones de salida ---------------------------
        salidas = [k for k in afn.transiciones if k[0] == final]
        if salidas:
            rep.falla('invariante/afn-aceptacion-sin-salida', r,
                      'sin aristas salientes desde el final', salidas)
            fallas += 1

        # -- a lo sumo 2n estados --------------------------------------
        # Cada simbolo, cada unario y cada union aportan exactamente 2
        # estados; la concatenacion no aporta ninguno. Como cada uno de
        # esos tokens ocupa al menos un caracter de la expresion, 2n es
        # cota superior con n = largo de la expresion.
        n_sim = sum(1 for t in tokens if t.tipo == 'simbolo')
        n_un = sum(1 for t in tokens if t.tipo == 'op' and t.valor in UNARIOS)
        n_uni = sum(1 for t in tokens if t.tipo == 'op' and t.valor == '|')
        esperado = 2 * (n_sim + n_un + n_uni)
        if len(afn.estados) != esperado:
            rep.falla('invariante/afn-conteo-estados', r,
                      f'{esperado} estados', len(afn.estados))
            fallas += 1
        if len(afn.estados) > 2 * len(r):
            rep.falla('invariante/afn-cota-2n', r,
                      f'<= {2 * len(r)} estados', len(afn.estados))
            fallas += 1

        # -- epsilon nunca es parte del alfabeto -----------------------
        for nombre, aut in (('AFN', afn), ('AFD', afd),
                            ('min', m_agr), ('min_myhill', m_myh)):
            if EPSILON in aut.alfabeto:
                rep.falla('invariante/epsilon-en-alfabeto', r,
                          f'{nombre} sin epsilon en el alfabeto',
                          sorted(aut.alfabeto))
                fallas += 1

        # -- el AFD no tiene estados inalcanzables ---------------------
        for nombre, aut in (('AFD', afd), ('min', m_agr)):
            alcanzables = {aut.inicio}
            pila = [aut.inicio]
            while pila:
                q = pila.pop()
                for s in aut.alfabeto:
                    d = aut.transiciones.get((q, s))
                    if d is not None and d not in alcanzables:
                        alcanzables.add(d)
                        pila.append(d)
            if alcanzables != aut.estados:
                rep.falla('invariante/estados-inalcanzables', r,
                          f'{nombre}: todos alcanzables',
                          f'sobran {sorted(aut.estados - alcanzables)}')
                fallas += 1

        # -- los dos metodos dan el mismo AFD --------------------------
        if not coinciden or huella(m_agr) != huella(m_myh):
            rep.falla('invariante/metodos-difieren', r,
                      'agrupacion == myhill',
                      f'agr={huella(m_agr)[:3]} myh={huella(m_myh)[:3]}')
            fallas += 1

        # -- minimizar dos veces no cambia nada ------------------------
        # Se cruzan los metodos a proposito: minimizar por un metodo lo ya
        # minimizado por el otro tampoco puede mover nada.
        for metodo_1, metodo_2 in (('agrupacion', 'agrupacion'),
                                   ('agrupacion', 'myhill'),
                                   ('myhill', 'agrupacion')):
            base = minimizar(afd, metodo_1)
            otra = minimizar(base, metodo_2)
            if huella(base) != huella(otra):
                rep.falla('invariante/no-idempotente', r,
                          f'minimizar({metodo_1}) luego {metodo_2} = igual',
                          f'{len(base.estados)} -> {len(otra.estados)} estados')
                fallas += 1

        # -- parentizar de mas no cambia el lenguaje -------------------
        # Si el Shunting Yard agrupa mal por precedencia, la version con
        # todos los parentesis explicitos difiere de la version minima.
        r_todo = render(arbol, 'proy', todo=True)
        try:
            m_todo = compilar(r_todo)[4]
            if huella(m_todo) != huella(m_agr):
                rep.falla('invariante/precedencia', r,
                          f'mismo minimo que {r_todo!r}',
                          f'{len(m_agr.estados)} vs {len(m_todo.estados)} estados')
                fallas += 1
        except Exception as e:
            rep.falla('invariante/precedencia', r_todo, 'compila',
                      f'{type(e).__name__}: {e}')
            fallas += 1

        # -- la traza del visor coincide con la minimizacion real ------
        # El visor dibuja la tabla de pares con traza_myhill, que es codigo
        # aparte. Si se desincronizara, la defense mostraria una tabla que
        # no corresponde al AFD que se esta exhibiendo.
        traza = traza_myhill(afd)
        if traza is not None:
            estados_c, trans_c = _completar(afd)
            particion = _particion_por_myhill(estados_c, trans_c,
                                              afd.aceptacion, afd.alfabeto)
            clase = {}
            for i, bloque in enumerate(particion):
                for q in bloque:
                    clase[_nombre(q)] = i
            for par in traza['equivalentes']:
                if clase[par['p']] != clase[par['q']]:
                    rep.falla('invariante/traza-visor', r,
                              f"{par} equivalentes tambien en minimizar()",
                              'la tabla del visor los da equivalentes pero '
                              'minimizar() los separa')
                    fallas += 1
                    break
            for celda in traza['celdas']:
                if clase[celda['p']] == clase[celda['q']]:
                    rep.falla('invariante/traza-visor', r,
                              f"({celda['p']},{celda['q']}) distinguibles "
                              f"tambien en minimizar()",
                              'la tabla del visor los marca pero '
                              'minimizar() los fusiona')
                    fallas += 1
                    break

    if not fallas:
        rep.ok(f"{iteraciones} expresiones: Thompson, alfabeto, "
               f"alcanzabilidad, idempotencia, precedencia y traza del visor")


# ===================================================================
# 3. MINIMALIDAD REAL (fuerza bruta)
# ===================================================================

def _acepta_desde(afd, q, w):
    for s in w:
        q = afd.transiciones.get((q, s))
        if q is None:
            return False
    return q in afd.aceptacion


def bloque_minimalidad(rep, rnd, iteraciones):
    print("\n[3] MINIMALIDAD REAL: fuerza bruta sobre el AFD minimo")
    letras = ['a', 'b', 'c']
    fallas = 0
    revisados = 0

    for _ in range(iteraciones):
        alfabeto = letras[:rnd.randint(2, 3)]
        r = render(generar(rnd, alfabeto, rnd.randint(1, 4)), 'proy')
        m = compilar(r)[4]
        # Se limita el tamano porque la prueba es exponencial en el largo
        # de las cadenas testigo; con AFDs chicos igual se cubre todo.
        if len(m.estados) > 6:
            continue
        revisados += 1
        simbolos = sorted(m.alfabeto)

        # Dos estados distintos de un AFD minimo tienen que ser
        # distinguibles por alguna cadena. Por Myhill-Nerode basta con
        # probar cadenas de largo < numero de estados, pero se usa el doble
        # para no depender de esa cota al verificar.
        largo = min(2 * len(m.estados), 9)
        testigos = cadenas_exhaustivas(simbolos, largo) if simbolos else ['']

        lista = sorted(m.estados)
        for i, p in enumerate(lista):
            for q in lista[i + 1:]:
                if all(_acepta_desde(m, p, w) == _acepta_desde(m, q, w)
                       for w in testigos):
                    rep.falla('minimalidad/par-equivalente', r,
                              f'estados {p} y {q} distinguibles',
                              f'ninguna cadena de largo <= {largo} los separa',
                              f'el AFD "minimo" tiene {len(m.estados)} estados '
                              f'y podria tener menos')
                    fallas += 1

        # Ningun estado muerto: desde cualquier estado se debe poder
        # llegar a un estado de aceptacion (salvo si el lenguaje es vacio,
        # que con esta gramatica no puede pasar).
        for q in m.estados:
            visto, pila, vivo = {q}, [q], False
            while pila and not vivo:
                x = pila.pop()
                if x in m.aceptacion:
                    vivo = True
                    break
                for s in m.alfabeto:
                    d = m.transiciones.get((x, s))
                    if d is not None and d not in visto:
                        visto.add(d)
                        pila.append(d)
            if not vivo:
                rep.falla('minimalidad/estado-muerto', r,
                          f'estado {q} llega a algun estado de aceptacion',
                          'estado muerto en el AFD minimo')
                fallas += 1

    if not fallas:
        rep.ok(f"{revisados} AFDs minimos: sin pares equivalentes "
               f"y sin estados muertos")


# ===================================================================
# 4. PROPIEDADES ALGEBRAICAS
# ===================================================================

FAMILIAS_FIJAS = [
    ["(a|b)*", "(a*b*)*", "(b|a)*", "(a|b)*(a|b)*", "((a|b)*)*",
     "(a|b)*(a|b)*(a|b)*", "(a*|b*)*"],
    ["a(ba)*", "(ab)*a"],
    ["(a|ε)", "a?", "(ε|a)", "a|ε"],
    ["a+", "aa*", "a*a", "a(a)*"],
    ["a*", "(a*)*", "(a+)?", "(a?)*", "ε|a+", "(a|ε)*", "a*a*"],
    ["ε", "ε*", "ε+", "ε?", "εε", "(ε)"],
    ["a", "aε", "εa", "(a)", "((a))", "\\a"],
    ["(ab)+", "ab(ab)*", "a(ba)*b", "(ab)(ab)*"],
    ["(a|b)*abb", "(a|b)*abb", "(b|a)*abb"],
    ["(a|b)(a|b)", "aa|ab|ba|bb"],
    ["a*b*", "(a*)(b*)", "a*(b)*"],
    ["(a|b)+", "(a|b)(a|b)*", "(a|b)*(a|b)"],
]


def _identidades(rnd, nodo):
    """Devuelve reescrituras del arbol que preservan el lenguaje.

    Son identidades del algebra de expresiones regulares. Se aplican en la
    raiz; la recursion las lleva a subarboles cualesquiera."""
    c = nodo.clase
    fuera = []
    if c == 'alt':
        x, y = nodo.hijos
        fuera.append(Nodo('alt', y, x))                     # x|y = y|x
        fuera.append(Nodo('alt', Nodo('alt', x, y), x))     # (x|y)|x = x|y
    if c == 'star':
        x = nodo.hijos[0]
        fuera.append(Nodo('star', Nodo('star', x)))         # (x*)* = x*
        fuera.append(Nodo('cat', Nodo('star', x), Nodo('star', x)))
        fuera.append(Nodo('star', Nodo('alt', x, Nodo('eps'))))
        fuera.append(Nodo('opt', Nodo('plus', x)))          # x* = (x+)?
        fuera.append(Nodo('alt', Nodo('eps'), Nodo('plus', x)))
    if c == 'plus':
        x = nodo.hijos[0]
        fuera.append(Nodo('cat', x, Nodo('star', x)))       # x+ = xx*
        fuera.append(Nodo('cat', Nodo('star', x), x))       # x+ = x*x
        fuera.append(Nodo('plus', Nodo('plus', x)))         # (x+)+ = x+
    if c == 'opt':
        x = nodo.hijos[0]
        fuera.append(Nodo('alt', x, Nodo('eps')))           # x? = x|eps
        fuera.append(Nodo('alt', Nodo('eps'), x))
        fuera.append(Nodo('opt', Nodo('opt', x)))
    if c == 'cat':
        x, y = nodo.hijos
        fuera.append(Nodo('cat', x, Nodo('cat', Nodo('eps'), y)))
        fuera.append(Nodo('cat', Nodo('cat', x, Nodo('eps')), y))
        # x(yx)* = (xy)*x , la identidad que mas suele romper implementaciones
        fuera.append(Nodo('cat', x, y))
    if c in ('sim', 'eps'):
        fuera.append(Nodo('cat', Nodo('eps'), nodo))
        fuera.append(Nodo('cat', nodo, Nodo('eps')))
    return fuera


def _reescribir(rnd, nodo, presupuesto):
    """Aplica una identidad en un punto al azar del arbol."""
    if presupuesto <= 0:
        return nodo
    opciones = _identidades(rnd, nodo)
    if nodo.hijos and rnd.random() < 0.5:
        i = rnd.randrange(len(nodo.hijos))
        hijos = list(nodo.hijos)
        hijos[i] = _reescribir(rnd, hijos[i], presupuesto - 1)
        return Nodo(nodo.clase, *hijos, simbolo=nodo.simbolo)
    if not opciones:
        return nodo
    return rnd.choice(opciones)


def bloque_algebra(rep, rnd, iteraciones):
    print("\n[4] ALGEBRA: el AFD minimo es unico, expresiones equivalentes "
          "deben dar el mismo")
    fallas = 0

    for familia in FAMILIAS_FIJAS:
        huellas = []
        for r in familia:
            try:
                huellas.append((r, huella(compilar(r)[4])))
            except Exception as e:
                rep.falla('algebra/compilacion', r, 'compila',
                          f'{type(e).__name__}: {e}')
                fallas += 1
        if len(huellas) > 1 and any(h != huellas[0][1] for _, h in huellas):
            distintos = {}
            for r, h in huellas:
                distintos.setdefault(h, []).append(r)
            rep.falla('algebra/familia-fija', familia,
                      'un solo AFD minimo para toda la familia',
                      f'{len(distintos)} AFDs distintos: '
                      f'{[v for v in distintos.values()]}')
            fallas += 1

    # Pares equivalentes generados: se parte de un arbol al azar y se le
    # aplican identidades algebraicas. El lenguaje no cambia, asi que el
    # AFD minimo tampoco puede cambiar.
    letras = ['a', 'b', 'c']
    generados = 0
    cortadas = 0
    for _ in range(iteraciones):
        alfabeto = letras[:rnd.randint(2, 3)]
        base = generar(rnd, alfabeto, rnd.randint(1, 3))
        variante = base
        for _ in range(rnd.randint(1, 3)):
            variante = _reescribir(rnd, variante, 4)

        r1 = render(base, 'proy')
        r2 = render(variante, 'proy')
        if r1 == r2:
            continue
        generados += 1

        # Se confirma primero con `re` que de verdad son el mismo lenguaje,
        # antes de acusar al proyecto de nada. Con el mismo corte por tiempo
        # que el bloque del oraculo: las reescrituras anidan cerraduras y el
        # backtracking de `re` se dispara.
        p1 = re.compile(render(base, 're'))
        p2 = re.compile(render(variante, 're'))
        muestras = cadenas_exhaustivas(alfabeto, 4)
        try:
            with limite_de_tiempo(5.0):
                mismo = all((p1.fullmatch(w) is not None)
                            == (p2.fullmatch(w) is not None)
                            for w in muestras)
        except TiempoAgotado:
            cortadas += 1
            continue
        if not mismo:
            continue  # la reescritura no preserva el lenguaje: no es un bug

        h1, h2 = huella(compilar(r1)[4]), huella(compilar(r2)[4])
        if h1 != h2:
            rep.falla('algebra/par-generado', f'{r1!r} vs {r2!r}',
                      'AFDs minimos identicos (el minimo es unico)',
                      f'{len(h1[0])} estados vs {len(h2[0])} estados; '
                      f'transiciones {h1[3]} vs {h2[3]}',
                      're.fullmatch confirma que son el mismo lenguaje')
            fallas += 1

    if not fallas:
        rep.ok(f"{len(FAMILIAS_FIJAS)} familias fijas y {generados} pares "
               f"equivalentes generados: mismo AFD minimo siempre "
               f"({cortadas} cortados por lentitud del motor `re`)")


# ===================================================================
# 5. BASURA
# ===================================================================

ALFABETO_BASURA = list("ab()|*+?\\.ε \t\n\r#\"{}<>0[]^$-/:;'`~!@%&=,")


def bloque_basura(rep, rnd, iteraciones):
    print("\n[5] BASURA: solo se permite ValueError")
    vistos = {}
    for _ in range(iteraciones):
        largo = rnd.randint(0, 14)
        s = ''.join(rnd.choice(ALFABETO_BASURA) for _ in range(largo))
        try:
            validar(s)
            tokens, _ = a_postfix(s)
            afn = construir_afn(tokens)
            afd = construir_afd(afn)
            minimizar(afd, 'agrupacion')
            minimizar(afd, 'myhill')
            simular_afn(afn, 'ab')
            simular_afd(afd, 'ab')
        except ValueError:
            pass                     # unico error contractual del modulo
        except Exception as e:
            clave = type(e).__name__
            if clave not in vistos:
                vistos[clave] = (s, traceback.format_exc())

    # Ademas de basura al azar, entradas degeneradas concretas.
    degeneradas = ['', ' ', '\t', '()', '(', ')', '*', '+', '?', '|', '.',
                   '\\', 'a\\', '((a)', 'a)', '|a', 'a|', 'a||b', '*a',
                   '(*)', '(|)', 'a**', 'a?*+', '()*', 'ε', 'εε*', '\\\\',
                   '(())', 'a()b', '\n', '#comentario', 'a b']
    for s in degeneradas:
        try:
            validar(s)
            tokens, _ = a_postfix(s)
            afd = construir_afd(construir_afn(tokens))
            minimizar(afd)
            minimizar(afd, 'myhill')
        except ValueError:
            pass
        except Exception as e:
            clave = type(e).__name__
            if clave not in vistos:
                vistos[clave] = (s, traceback.format_exc())

    if vistos:
        for clave, (s, tb) in vistos.items():
            rep.falla('basura/excepcion-inesperada', s,
                      'ValueError', clave, tb.strip().splitlines()[-1])
    else:
        rep.ok(f"{iteraciones} cadenas al azar mas {len(degeneradas)} "
               f"degeneradas: nada distinto de ValueError")


# ===================================================================
# 6. CLI (main.py)
# ===================================================================

def _correr_main(ruta, cadena, cwd=None):
    # Siempre desde un directorio temporal: main.py escribe en './output',
    # y la prueba no tiene por que ensuciar el output/ del proyecto ni
    # pisar las imagenes que ya estan generadas para entregar.
    proc = subprocess.run(
        [sys.executable, os.path.join(RAIZ, 'main.py'), ruta, cadena],
        cwd=cwd or tempfile.mkdtemp(prefix='adv_cwd_'),
        capture_output=True, text=True, timeout=300)
    return proc


def bloque_cli(rep):
    print("\n[6] CLI: main.py contra archivos que nadie probo")
    tmp = tempfile.mkdtemp(prefix='adv_cli_')

    def escribir(nombre, datos):
        ruta = os.path.join(tmp, nombre)
        with open(ruta, 'wb') as f:
            f.write(datos)
        return ruta

    # -- BOM UTF-8 -------------------------------------------------------
    # Cualquier editor de Windows guarda con BOM. Si el BOM entra como
    # simbolo, el AFN queda mal y el programa no avisa nada.
    ruta = escribir('bom.txt', '﻿a|b\n'.encode('utf-8'))
    proc = _correr_main(ruta, 'a')
    if '\\ufeff' in proc.stdout or 'ufeff' in proc.stdout:
        rep.falla('cli/bom', 'archivo UTF-8 con BOM que contiene "a|b"',
                  "alfabeto ['a', 'b']",
                  "el BOM entra al alfabeto como un simbolo mas",
                  "main.py:135 abre con encoding='utf-8'; deberia ser "
                  "'utf-8-sig'")

    # -- CRLF de Windows -------------------------------------------------
    ruta = escribir('crlf.txt', b'a|b\r\nab*\r\n')
    proc = _correr_main(ruta, 'a')
    if proc.returncode != 0 or 'Traceback' in proc.stderr:
        rep.falla('cli/crlf', 'archivo con saltos CRLF', 'procesa 2 lineas',
                  proc.stderr.strip()[-300:])

    # -- archivo vacio ---------------------------------------------------
    ruta = escribir('vacio.txt', b'')
    proc = _correr_main(ruta, 'a')
    if proc.returncode != 0 or 'no contiene' not in proc.stdout:
        rep.falla('cli/vacio', 'archivo vacio',
                  'mensaje claro y salida limpia',
                  f'returncode={proc.returncode} {proc.stderr[-200:]}')

    # -- solo comentarios y lineas en blanco -----------------------------
    ruta = escribir('comentarios.txt', b'# nada\n\n   \n#otra\n')
    proc = _correr_main(ruta, 'a')
    if 'no contiene' not in proc.stdout:
        rep.falla('cli/comentarios', 'archivo solo con # y lineas vacias',
                  'mensaje "no contiene expresiones"',
                  proc.stdout.strip()[-200:])

    # -- archivo binario -------------------------------------------------
    ruta = escribir('binario.txt', bytes(range(256)))
    proc = _correr_main(ruta, 'a')
    if 'Traceback' in proc.stderr:
        rep.falla('cli/binario', 'archivo binario como entrada',
                  'mensaje de error legible',
                  proc.stderr.strip().splitlines()[-1],
                  'main.py:135 no maneja UnicodeDecodeError')

    # -- archivo inexistente ---------------------------------------------
    proc = _correr_main(os.path.join(tmp, 'no_existe.txt'), 'a')
    if 'no se encontro' not in proc.stdout or proc.returncode != 1:
        rep.falla('cli/inexistente', 'ruta que no existe',
                  'mensaje y exit 1',
                  f'returncode={proc.returncode}')

    # -- un directorio en lugar de un archivo -----------------------------
    proc = _correr_main(os.path.join(RAIZ, 'src'), 'a')
    if 'Traceback' in proc.stderr:
        rep.falla('cli/directorio', 'un directorio como argumento',
                  'mensaje de error legible',
                  proc.stderr.strip().splitlines()[-1],
                  'os.path.exists() da True para un directorio')

    # -- expresion invalida en medio del archivo --------------------------
    # Una linea mala no puede tumbar el resto del lote.
    ruta = escribir('mixto.txt', 'a|b\n((a\nab*\n'.encode('utf-8'))
    proc = _correr_main(ruta, 'a')
    if proc.stdout.count('EXPRESION') < 3 or 'Traceback' in proc.stderr:
        rep.falla('cli/linea-invalida', 'archivo con una regex mal formada',
                  'las otras dos lineas igual se procesan',
                  proc.stderr.strip()[-200:] or proc.stdout[-200:])

    # -- imagenes viejas que sobreviven a la corrida siguiente ------------
    # main.py numera por indice de expresion y no borra output/ antes de
    # empezar. Si el calificador corre primero un archivo largo y despues
    # uno corto, quedan PNG de la corrida anterior con numeros mayores, y
    # nada distingue unos de otros.
    aparte = tempfile.mkdtemp(prefix='adv_out_')
    largo = escribir('largo.txt', 'a\nb\nc\nab\nba\n'.encode('utf-8'))
    _correr_main(largo, 'a', cwd=aparte)
    corto = escribir('corto.txt', 'a\n'.encode('utf-8'))
    _correr_main(corto, 'a', cwd=aparte)
    salida = os.path.join(aparte, 'output')
    quedaron = sorted(os.listdir(salida)) if os.path.isdir(salida) else []
    sobrantes = [n for n in quedaron if not n.startswith('01_')]
    if sobrantes:
        rep.falla('cli/salida-vieja',
                  'correr main.py con 5 expresiones y despues con 1',
                  'output/ refleja solo la ultima corrida (solo 01_*)',
                  f'sobreviven {sobrantes}',
                  'main.py:111 no limpia output/ antes de generar')

    if not any(h['bloque'].startswith('cli/') for h in rep.hallazgos):
        rep.ok("BOM, CRLF, vacio, comentarios, binario, inexistente, "
               "directorio, linea invalida y salidas viejas")


# ===================================================================
# 7. WEB (app.py)
# ===================================================================

def bloque_web(rep):
    print("\n[7] WEB: endpoints de app.py con JSON hostil")
    try:
        import app as modulo_app
    except Exception as e:
        rep.ok(f"omitido: no se pudo importar app.py ({e})")
        return

    modulo_app.app.config['TESTING'] = True
    cliente = modulo_app.app.test_client()

    def pedir(url, payload=None, crudo=None):
        """Devuelve (codigo, texto) o ('EXCEPCION', detalle).

        Con TESTING=True Flask propaga la excepcion en vez de devolver un
        500, asi que una excepcion aqui es exactamente un 500 en produccion."""
        try:
            if crudo is not None:
                r = cliente.post(url, data=crudo,
                                 content_type='application/json')
            else:
                r = cliente.post(url, json=payload)
            return r.status_code, r.get_data(as_text=True)
        except Exception as e:
            return 'EXCEPCION', f'{type(e).__name__}: {e}'

    casos = [
        ('/api/procesar', {'crudo': '{esto no es json'},
         'JSON invalido'),
        ('/api/procesar', {'payload': {}},
         'objeto vacio'),
        ('/api/procesar', {'payload': {'regex': 123, 'cadena': ''}},
         'regex numerica'),
        ('/api/procesar', {'payload': {'regex': ['a'], 'cadena': ''}},
         'regex como lista'),
        ('/api/procesar', {'payload': {'regex': 'a', 'cadena': 5}},
         'cadena numerica'),
        ('/api/procesar', {'payload': {'regex': '\\\\', 'cadena': ''}},
         'regex con simbolo backslash literal'),
        ('/api/lote', {'payload': {'expresiones': [], 'cadena': ''}},
         'lote vacio'),
        ('/api/lote', {'payload': {'expresiones': [None, 1, {}, 'a'],
                                   'cadena': 'a'}},
         'lote con elementos no textuales'),
        ('/api/lote', {'payload': {'expresiones': 'abc', 'cadena': ''}},
         'expresiones como texto en vez de lista'),
        ('/api/imagenes', {'payload': {'expresiones': []}},
         'imagenes con lista vacia'),
        # JSON sintacticamente valido pero que no es un objeto. `or {}` no
        # lo cubre porque una lista o un texto no vacios son truthy, asi que
        # el .get() de la linea siguiente es el que explota.
        ('/api/procesar', {'crudo': '[1, 2]'},
         'cuerpo JSON que es una lista'),
        ('/api/procesar', {'crudo': '"hola"'},
         'cuerpo JSON que es un texto'),
        ('/api/procesar', {'crudo': '5'},
         'cuerpo JSON que es un numero'),
        ('/api/lote', {'crudo': '[1, 2]'},
         'cuerpo JSON que es una lista'),
        ('/api/imagenes', {'crudo': '[1, 2]'},
         'cuerpo JSON que es una lista'),
        ('/api/lote', {'payload': {'expresiones': {'x': 'a'}}},
         'expresiones como objeto en vez de lista'),
    ]

    for url, kw, descripcion in casos:
        codigo, cuerpo = pedir(url, kw.get('payload'), kw.get('crudo'))
        if codigo == 'EXCEPCION':
            rep.falla('web/500', f'POST {url} :: {descripcion}',
                      'respuesta JSON con ok=false y un mensaje',
                      f'excepcion no capturada -> HTTP 500: {cuerpo}',
                      'app.py devuelve 500 en vez de un error manejado')
        elif codigo != 200:
            rep.falla('web/codigo', f'POST {url} :: {descripcion}',
                      'HTTP 200', f'HTTP {codigo}')

    # -- expresion enorme -------------------------------------------------
    # El endpoint no tiene ningun tope de tamano; se mide cuanto tarda una
    # expresion larga pero perfectamente valida.
    grande = 'a' * 400
    t0 = time.time()
    codigo, _ = pedir('/api/procesar', {'regex': grande, 'cadena': 'a' * 400})
    demora = time.time() - t0
    if codigo == 'EXCEPCION':
        rep.falla('web/500', f'POST /api/procesar con regex de {len(grande)} '
                  f'caracteres', 'respuesta manejada',
                  f'excepcion no capturada: {_}')
    elif demora > 20:
        rep.falla('web/lentitud', f'regex de {len(grande)} caracteres',
                  'respuesta en pocos segundos',
                  f'{demora:.1f}s sin ningun tope ni aviso')

    # -- AFD grande: el visor no tiene guardia de tamano ------------------
    # Este es el caso que un calificador puede escribir sin querer.
    r_grande = '(a|b)*a' + '(a|b)' * 6
    t0 = time.time()
    codigo, cuerpo = pedir('/api/procesar', {'regex': r_grande,
                                             'cadena': 'abab'})
    demora = time.time() - t0
    if codigo == 'EXCEPCION':
        rep.falla('web/500', r_grande, 'respuesta manejada', cuerpo)
    elif demora > 3:
        rep.falla('web/escalabilidad', f'{r_grande!r} ({len(r_grande)} chars)',
                  'respuesta interactiva (< 1 s)',
                  f'{demora:.1f}s y {len(cuerpo)} bytes de JSON',
                  'el costo crece muy rapido: con dos (a|b) mas la peticion '
                  'pasa de los dos minutos')

    if not any(h['bloque'].startswith('web/') for h in rep.hallazgos):
        rep.ok(f"{len(casos)} peticiones hostiles y dos de tamano: "
               f"todas manejadas")


# ===================================================================
# 8. IMAGENES
# ===================================================================

PNG_MAGICO = b'\x89PNG\r\n\x1a\n'

# Simbolos que son sintaxis dentro de una etiqueta DOT. Van escapados con
# '\' porque varios son operadores de la regex.
REGEX_HOSTILES = [
    'a\\"b',        # comilla doble
    'a\\{b\\}',     # llaves (sintaxis de record en DOT)
    'a\\<b\\>',     # angulares (sintaxis de puerto en DOT)
    'a\\\\b',       # backslash literal
    '\\\\',         # solo un backslash
    'a\\|b',        # barra vertical literal
    'a b',          # espacio
    'a\\ b',        # espacio escapado
    'a\\;b',       # punto y coma escapado
    'á|ñ',          # no ascii
    '(a|b)*abb',    # control: normal
]


def bloque_imagenes(rep):
    print("\n[8] IMAGENES: el PNG tiene que ser un PNG")
    try:
        from src.visualizacion import (graficar_afn, graficar_afd,
                                       GRAPHVIZ_DISPONIBLE, a_svg, grafo_afn)
    except Exception as e:
        rep.ok(f"omitido: no se pudo importar visualizacion ({e})")
        return
    if not GRAPHVIZ_DISPONIBLE:
        rep.ok("omitido: graphviz no esta instalado")
        return

    tmp = tempfile.mkdtemp(prefix='adv_img_')
    for i, r in enumerate(REGEX_HOSTILES):
        try:
            _, _, afn, afd, m, _, _ = compilar(r)
        except Exception as e:
            rep.falla('imagenes/compilacion', r, 'compila',
                      f'{type(e).__name__}: {e}')
            continue

        salidas = [
            ('afn', graficar_afn(afn, os.path.join(tmp, f'{i}_afn'),
                                 f'AFN (Thompson) - r = {r}')),
            ('afd', graficar_afd(afd, os.path.join(tmp, f'{i}_afd'),
                                 f'AFD - r = {r}', mostrar_etiquetas=True)),
            ('min', graficar_afd(m, os.path.join(tmp, f'{i}_min'),
                                 f'AFD minimizado - r = {r}')),
        ]
        for nombre, ruta in salidas:
            if ruta is None:
                rep.falla('imagenes/sin-archivo', r,
                          f'{nombre}: un archivo PNG', 'None')
                continue
            with open(ruta, 'rb') as f:
                cabecera = f.read(8)
            if cabecera != PNG_MAGICO:
                rep.falla('imagenes/no-es-png', r,
                          f'{nombre}: archivo PNG valido',
                          f'{os.path.basename(ruta)} '
                          f'(cabecera {cabecera!r})',
                          'visualizacion.py:130 captura la falla de Graphviz '
                          'y escribe un .dot en silencio; main.py lo lista '
                          'como "imagen generada"')

        # El visor renderiza a SVG por otro camino, que no tiene el
        # try/except del render a archivo: ahi la falla si explota.
        try:
            a_svg(grafo_afn(afn))
        except Exception as e:
            rep.falla('imagenes/svg', r, 'SVG del AFN',
                      f'{type(e).__name__}: {str(e)[:160]}',
                      'a_svg() no atrapa nada y en app.py se llama fuera '
                      'del try, asi que sale un HTTP 500')

    if not any(h['bloque'].startswith('imagenes/') for h in rep.hallazgos):
        rep.ok(f"{len(REGEX_HOSTILES)} expresiones hostiles para DOT: "
               f"todos los PNG son PNG")


# ===================================================================
# 9. ESCALABILIDAD DE LA MINIMIZACION
# ===================================================================

def _medir(afd, metodo, repeticiones=3):
    """Mejor de N corridas, para que el ruido del reloj no decida el veredicto."""
    mejor = float('inf')
    for _ in range(repeticiones):
        t0 = time.time()
        minimizar(afd, metodo)
        mejor = min(mejor, time.time() - t0)
    return mejor


def bloque_escalabilidad(rep):
    print("\n[9] ESCALABILIDAD: como crece cada metodo de minimizacion")
    # Los dos metodos NO tienen por que tardar lo mismo, y exigirlo seria una
    # expectativa equivocada: la tabla de pares tiene C(n,2) celdas por
    # definicion, asi que Myhill-Nerode es cuadratico haga lo que haga,
    # mientras que el refinamiento de particiones es O(n log n). Lo que si se
    # puede exigir es que myhill crezca como n² y no como n³, que es lo que
    # pasaba cuando el punto fijo rehacia la pasada completa sobre todos los
    # pares en cada ronda. Ver HALLAZGOS.md #5.
    #
    # Se mide con 'a'*n, que da una cadena de estados larga y por lo tanto
    # muchas rondas de propagacion: es donde la diferencia entre n² y n³ se ve
    # mas limpia. Al duplicar n, un algoritmo cuadratico multiplica el tiempo
    # por ~4 y uno cubico por ~8; medido, el actual da 3.8 y el anterior 8.1.
    medidas = []
    for n in (100, 200, 400):
        afd = construir_afd(construir_afn(a_postfix('a' * n)[0]))
        medidas.append((len(afd.estados), _medir(afd, 'myhill')))
    razones = [b / a for (_, a), (_, b) in zip(medidas, medidas[1:]) if a > 0]
    detalle = ', '.join(f'{n} estados {t:.4f}s' for n, t in medidas)
    peor = max(razones) if razones else 0

    if peor > 6:      # justo a mitad de camino entre cuadratico y cubico
        rep.falla('escalabilidad/myhill-crece-de-mas',
                  "'a'*n para n = 100, 200, 400",
                  'al duplicar los estados el tiempo se multiplica por ~4 '
                  '(cuadratico)',
                  f'se multiplica por {peor:.1f} ({detalle})',
                  'sintoma de que el punto fijo volvio a recorrer todos los '
                  'pares en cada ronda en vez de propagar hacia atras')
    else:
        rep.ok(f'myhill se multiplica por {peor:.1f} al duplicar n '
               f'(cuadratico): {detalle}')

    # Tiempos absolutos en el tamano mas grande que el visor compara.
    r = '(a|b)*a' + '(a|b)' * 8          # 513 estados, por debajo de TOPE_COMPARAR
    afd = construir_afd(construir_afn(a_postfix(r)[0]))
    t0 = time.time()
    verificar_equivalencia(afd)
    demora = time.time() - t0
    if demora > 1.0:
        rep.falla('escalabilidad/tope-del-visor',
                  f'{r} ({len(afd.estados)} estados)',
                  'comparar los dos metodos en menos de 1 s',
                  f'{demora:.2f}s',
                  'el visor corre verificar_equivalencia() en cada tecla por '
                  'debajo de TOPE_COMPARAR')
    else:
        rep.ok(f'verificar_equivalencia() con {len(afd.estados)} estados '
               f'(el tope del visor): {demora:.3f}s')

    # Y el caso que antes tardaba 740 s.
    afd = construir_afd(construir_afn(a_postfix('a' * 300)[0]))
    t_myhill = _medir(afd, 'myhill')
    t_agrupacion = _medir(afd, 'agrupacion')
    if t_myhill > 1.0:
        rep.falla('escalabilidad/myhill-cadena-larga', "'a' * 300",
                  'menos de 1 s', f'{t_myhill:.2f}s',
                  f'agrupacion tarda {t_agrupacion:.2f}s sobre el mismo AFD')
    else:
        rep.ok(f"'a'*300 (301 estados): myhill {t_myhill:.3f}s, "
               f'agrupacion {t_agrupacion:.3f}s')


# ===================================================================
# Entrada
# ===================================================================

BLOQUES = {
    'oraculo': ('aleatorio', bloque_oraculo, 300),
    'invariantes': ('aleatorio', bloque_invariantes, 200),
    'minimalidad': ('aleatorio', bloque_minimalidad, 200),
    'algebra': ('aleatorio', bloque_algebra, 300),
    'basura': ('aleatorio', bloque_basura, 20000),
    'cli': ('simple', bloque_cli, None),
    'web': ('simple', bloque_web, None),
    'imagenes': ('simple', bloque_imagenes, None),
    'escalabilidad': ('simple', bloque_escalabilidad, None),
}


def main():
    ap = argparse.ArgumentParser(
        description='Pruebas adversarias del Proyecto 1.')
    ap.add_argument('--semilla', type=int, default=None,
                    help='semilla del generador (por defecto una al azar; '
                         'siempre se imprime para poder reproducir)')
    ap.add_argument('--iteraciones', type=int, default=None,
                    help='multiplica el trabajo de los bloques aleatorios')
    ap.add_argument('--rapido', action='store_true',
                    help='corrida corta, para uso interactivo')
    ap.add_argument('--solo', action='append', choices=sorted(BLOQUES),
                    help='corre solo estos bloques (se puede repetir)')
    args = ap.parse_args()

    semilla = args.semilla if args.semilla is not None \
        else random.randrange(2 ** 31)
    escala = 0.15 if args.rapido else 1.0

    print("=" * 70)
    print("PRUEBAS ADVERSARIAS - Proyecto 1 (Teoria de la Computacion)")
    print("=" * 70)
    print(f"semilla   : {semilla}")
    print(f"reproducir: python pruebas_adversarias.py --semilla {semilla}"
          + (" --rapido" if args.rapido else ""))
    print(f"python    : {sys.version.split()[0]}")

    rep = Reporte()
    elegidos = args.solo or sorted(BLOQUES)
    # Se respeta el orden de BLOQUES y no el alfabetico del filtro, para que
    # el reporte salga siempre en el mismo orden.
    orden = [n for n in BLOQUES if n in elegidos]

    t0 = time.time()
    for nombre in orden:
        tipo, funcion, base = BLOQUES[nombre]
        if tipo == 'simple':
            funcion(rep)
        else:
            n = args.iteraciones if args.iteraciones else max(
                1, int(base * escala))
            # Cada bloque arranca de una semilla derivada y estable, para
            # que --solo reproduzca exactamente lo mismo que la corrida
            # completa con la misma semilla.
            funcion(rep, random.Random(f'{semilla}:{nombre}'), n)

    print("\n" + "=" * 70)
    print(f"comparaciones contra el oraculo: {rep.comparaciones}")
    print(f"tiempo total                   : {time.time() - t0:.1f}s")
    if rep.hallazgos:
        print(f"HALLAZGOS: {len(rep.hallazgos)}")
        for h in rep.hallazgos:
            print(f"  - {h['bloque']}: {h['entrada']!r}")
    else:
        print("HALLAZGOS: 0")
    print(f"semilla: {semilla}")
    print("=" * 70)
    return len(rep.hallazgos)


if __name__ == '__main__':
    sys.exit(min(main(), 125))
