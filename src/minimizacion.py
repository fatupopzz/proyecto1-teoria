"""
Minimizacion de AFD mediante refinamiento de particiones (Hopcroft).

Procedimiento:
    1. Se completa el AFD agregando un estado trampa para las transiciones
       no definidas (el algoritmo requiere una funcion de transicion total).
    2. Se parte en dos bloques: aceptacion y no aceptacion.
    3. Se refina hasta que no haya cambios.
    4. Se eliminan los estados muertos (desde los que no se alcanza aceptacion)
       y los inalcanzables.
"""

from .automata import AFD

TRAMPA = -1


def _completar(afd):
    """Agrega un estado trampa para que la funcion de transicion sea total."""
    transiciones = dict(afd.transiciones)
    estados = set(afd.estados)
    necesita_trampa = False

    for estado in afd.estados:
        for simbolo in afd.alfabeto:
            if (estado, simbolo) not in transiciones:
                transiciones[(estado, simbolo)] = TRAMPA
                necesita_trampa = True

    if necesita_trampa:
        estados.add(TRAMPA)
        for simbolo in afd.alfabeto:
            transiciones[(TRAMPA, simbolo)] = TRAMPA

    return estados, transiciones


def _particion_inicial(estados, aceptacion):
    finales = frozenset(e for e in estados if e in aceptacion)
    no_finales = frozenset(e for e in estados if e not in aceptacion)
    return [b for b in (finales, no_finales) if b]


def _refinar(particion, transiciones, alfabeto):
    """Refina la particion hasta alcanzar el punto fijo."""
    cambio = True
    while cambio:
        cambio = False
        nueva = []

        # bloque al que pertenece cada estado
        pertenece = {}
        for i, bloque in enumerate(particion):
            for estado in bloque:
                pertenece[estado] = i

        for bloque in particion:
            # se agrupan los estados por su "firma": el bloque destino
            # para cada simbolo del alfabeto
            grupos = {}
            for estado in bloque:
                firma = tuple(
                    pertenece.get(transiciones.get((estado, s)))
                    for s in sorted(alfabeto)
                )
                grupos.setdefault(firma, set()).add(estado)

            if len(grupos) > 1:
                cambio = True
            nueva.extend(frozenset(g) for g in grupos.values())

        particion = nueva

    return particion


def _limpiar(estados, transiciones, inicio, aceptacion, alfabeto):
    """Elimina estados inalcanzables y estados muertos."""
    # Alcanzables desde el inicio
    alcanzables = set()
    pila = [inicio]
    while pila:
        estado = pila.pop()
        if estado in alcanzables:
            continue
        alcanzables.add(estado)
        for simbolo in alfabeto:
            destino = transiciones.get((estado, simbolo))
            if destino is not None and destino not in alcanzables:
                pila.append(destino)

    # Estados vivos: desde los que se puede llegar a un estado de aceptacion
    inverso = {}
    for (origen, simbolo), destino in transiciones.items():
        inverso.setdefault(destino, set()).add(origen)

    vivos = set()
    pila = [e for e in aceptacion if e in alcanzables]
    while pila:
        estado = pila.pop()
        if estado in vivos:
            continue
        vivos.add(estado)
        for origen in inverso.get(estado, set()):
            if origen not in vivos:
                pila.append(origen)

    utiles = alcanzables & vivos
    if inicio in alcanzables:
        utiles.add(inicio)  # el inicial siempre se conserva

    nuevas_transiciones = {
        k: v for k, v in transiciones.items()
        if k[0] in utiles and v in utiles
    }

    return utiles, nuevas_transiciones


def minimizar(afd):
    """Retorna un AFD minimo equivalente al AFD recibido."""
    if not afd.alfabeto:
        return AFD(set(afd.estados), set(afd.alfabeto), dict(afd.transiciones),
                   afd.inicio, set(afd.aceptacion), {})

    estados, transiciones = _completar(afd)
    particion = _particion_inicial(estados, afd.aceptacion)
    particion = _refinar(particion, transiciones, afd.alfabeto)

    # Se numeran los bloques dejando como 0 el que contiene al estado inicial
    bloque_de = {}
    for i, bloque in enumerate(particion):
        for estado in bloque:
            bloque_de[estado] = i

    orden = [bloque_de[afd.inicio]]
    orden += [i for i in range(len(particion)) if i != bloque_de[afd.inicio]]
    renombre = {viejo: nuevo for nuevo, viejo in enumerate(orden)}

    nuevas_transiciones = {}
    for (origen, simbolo), destino in transiciones.items():
        nuevas_transiciones[(renombre[bloque_de[origen]], simbolo)] = \
            renombre[bloque_de[destino]]

    nuevo_inicio = renombre[bloque_de[afd.inicio]]
    nueva_aceptacion = {
        renombre[bloque_de[e]] for e in afd.aceptacion
    }
    nuevos_estados = set(renombre.values())

    nuevos_estados, nuevas_transiciones = _limpiar(
        nuevos_estados, nuevas_transiciones, nuevo_inicio,
        nueva_aceptacion, afd.alfabeto)
    nueva_aceptacion &= nuevos_estados

    # Etiquetas de trazabilidad: que estados del AFD original quedaron fusionados
    etiquetas = {}
    for viejo_idx, nuevo_idx in renombre.items():
        if nuevo_idx not in nuevos_estados:
            continue
        originales = sorted(e for e in particion[viejo_idx] if e != TRAMPA)
        if originales:
            etiquetas[nuevo_idx] = '{' + ', '.join(str(e) for e in originales) + '}'

    # Renumeracion final para que los estados queden consecutivos desde 0
    compacto = {viejo: i for i, viejo in enumerate(
        [nuevo_inicio] + sorted(e for e in nuevos_estados if e != nuevo_inicio))}

    return AFD(
        estados=set(compacto.values()),
        alfabeto=set(afd.alfabeto),
        transiciones={(compacto[o], s): compacto[d]
                      for (o, s), d in nuevas_transiciones.items()},
        inicio=compacto[nuevo_inicio],
        aceptacion={compacto[e] for e in nueva_aceptacion},
        etiquetas={compacto[e]: v for e, v in etiquetas.items()},
    )
