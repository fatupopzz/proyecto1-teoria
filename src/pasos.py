"""
Calculo paso a paso de la simulacion, para el visor web.

A diferencia de src/simulacion.py (que solo responde si/no), aqui se guarda
para cada paso que estados quedan activos y que aristas se recorrieron, de
modo que el visor pueda resaltarlas sobre el grafo.
"""

from .subconjuntos import cerradura_epsilon, mover


def pasos_afn(afn, cadena):
    """Retorna (pasos, aceptada) para el AFN.

    Cada paso: {simbolo, estados, aristas, muerto}
        aristas: lista de [origen, destino] que consumieron el simbolo
    """
    actual = cerradura_epsilon(afn, {afn.inicio})
    pasos = [{
        'simbolo': None,
        'estados': sorted(actual),
        'aristas': [],
        'muerto': False,
    }]

    for simbolo in cadena:
        if simbolo not in afn.alfabeto:
            pasos.append({'simbolo': simbolo, 'estados': [],
                          'aristas': [], 'muerto': True})
            return pasos, False

        aristas = []
        for origen in sorted(actual):
            for destino in sorted(afn.mover(origen, simbolo)):
                aristas.append([origen, destino])

        siguiente = cerradura_epsilon(afn, mover(afn, actual, simbolo))
        pasos.append({
            'simbolo': simbolo,
            'estados': sorted(siguiente),
            'aristas': aristas,
            'muerto': not siguiente,
        })

        actual = siguiente
        if not actual:
            return pasos, False

    return pasos, bool(actual & afn.aceptacion)


def pasos_afd(afd, cadena):
    """Retorna (pasos, aceptada) para el AFD.

    Cada paso: {simbolo, estados, aristas, muerto}
    (estados siempre trae un solo elemento, para uniformar con el AFN)
    """
    actual = afd.inicio
    pasos = [{
        'simbolo': None,
        'estados': [actual],
        'aristas': [],
        'muerto': False,
    }]

    for simbolo in cadena:
        siguiente = afd.mover(actual, simbolo) if simbolo in afd.alfabeto else None

        if siguiente is None:
            pasos.append({'simbolo': simbolo, 'estados': [],
                          'aristas': [], 'muerto': True})
            return pasos, False

        pasos.append({
            'simbolo': simbolo,
            'estados': [siguiente],
            'aristas': [[actual, siguiente]],
            'muerto': False,
        })
        actual = siguiente

    return pasos, actual in afd.aceptacion
