"""Simulacion de AFN y AFD sobre una cadena w."""

from .subconjuntos import cerradura_epsilon, mover


def simular_afn(afn, cadena):
    """Simula el AFN con conjuntos de estados.

    Retorna (aceptada, traza) donde traza es la lista de pasos.
    """
    actuales = cerradura_epsilon(afn, {afn.inicio})
    traza = [("inicio", sorted(actuales))]

    for simbolo in cadena:
        if simbolo not in afn.alfabeto:
            traza.append((simbolo, []))
            return False, traza
        actuales = cerradura_epsilon(afn, mover(afn, actuales, simbolo))
        traza.append((simbolo, sorted(actuales)))
        if not actuales:
            return False, traza

    aceptada = bool(actuales & afn.aceptacion)
    return aceptada, traza


def simular_afd(afd, cadena):
    """Simula el AFD siguiendo una sola transicion por simbolo.

    Retorna (aceptada, traza).
    """
    actual = afd.inicio
    traza = [("inicio", actual)]

    for simbolo in cadena:
        if simbolo not in afd.alfabeto:
            traza.append((simbolo, None))
            return False, traza
        siguiente = afd.mover(actual, simbolo)
        traza.append((simbolo, siguiente))
        if siguiente is None:
            return False, traza
        actual = siguiente

    return actual in afd.aceptacion, traza


def formato_traza_afn(traza):
    partes = []
    for simbolo, estados in traza:
        if simbolo == "inicio":
            partes.append('{' + ', '.join(map(str, estados)) + '}')
        else:
            destino = '{' + ', '.join(map(str, estados)) + '}' if estados else '{}'
            partes.append(f" --{simbolo}--> {destino}")
    return ''.join(partes)


def formato_traza_afd(traza):
    partes = []
    for simbolo, estado in traza:
        if simbolo == "inicio":
            partes.append(str(estado))
        else:
            partes.append(f" --{simbolo}--> {estado if estado is not None else 'X'}")
    return ''.join(partes)
