"""
Construccion de subconjuntos: convierte un AFN en un AFD equivalente.

Cada estado del AFD corresponde a un conjunto de estados del AFN.
"""

from .automata import AFD
from .shunting_yard import EPSILON


def cerradura_epsilon(afn, estados):
    """e-closure(T): estados alcanzables desde T usando solo transiciones epsilon."""
    pila = list(estados)
    cerradura = set(estados)

    while pila:
        estado = pila.pop()
        for destino in afn.mover(estado, EPSILON):
            if destino not in cerradura:
                cerradura.add(destino)
                pila.append(destino)

    return frozenset(cerradura)


def mover(afn, estados, simbolo):
    """move(T, a): estados alcanzables desde T consumiendo el simbolo a."""
    resultado = set()
    for estado in estados:
        resultado |= afn.mover(estado, simbolo)
    return resultado


def construir_afd(afn):
    """Aplica la construccion de subconjuntos y retorna el AFD resultante."""
    alfabeto = set(afn.alfabeto)

    inicial = cerradura_epsilon(afn, {afn.inicio})
    subconjuntos = {inicial: 0}       # frozenset -> id del estado del AFD
    orden = [inicial]
    pendientes = [inicial]
    transiciones = {}

    while pendientes:
        actual = pendientes.pop(0)
        id_actual = subconjuntos[actual]

        for simbolo in sorted(alfabeto):
            destino = cerradura_epsilon(afn, mover(afn, actual, simbolo))
            if not destino:
                continue  # transicion no definida (estado muerto implicito)

            if destino not in subconjuntos:
                subconjuntos[destino] = len(subconjuntos)
                orden.append(destino)
                pendientes.append(destino)

            transiciones[(id_actual, simbolo)] = subconjuntos[destino]

    aceptacion = {
        subconjuntos[sub] for sub in orden
        if sub & afn.aceptacion
    }

    etiquetas = {
        subconjuntos[sub]: '{' + ', '.join(str(e) for e in sorted(sub)) + '}'
        for sub in orden
    }

    return AFD(
        estados=set(subconjuntos.values()),
        alfabeto=alfabeto,
        transiciones=transiciones,
        inicio=0,
        aceptacion=aceptacion,
        etiquetas=etiquetas,
    )
