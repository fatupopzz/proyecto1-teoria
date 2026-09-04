"""
Minimizacion de AFD.

Ambos metodos implementados calculan la misma relacion: la equivalencia de
Myhill-Nerode sobre los estados del AFD (dos estados son equivalentes si
ninguna cadena los distingue). Cambia como se calcula.

    'agrupacion'  Refinamiento de particiones (Moore / Hopcroft).
                  Se parte del bloque {aceptacion} vs {no aceptacion} y se
                  refina agrupando por firma hasta el punto fijo.

    'myhill'      Llenado de tabla de pares (Myhill-Nerode clasico).
                  Se marca cada par de estados distinguibles y al final los
                  pares que quedaron sin marcar forman las clases de
                  equivalencia.

El teorema de Myhill-Nerode garantiza que el AFD minimo es unico salvo
renombrar estados, asi que ambos metodos producen el mismo resultado.
`verificar_equivalencia()` lo comprueba sobre un AFD concreto.

En los dos casos:
    1. Se completa el AFD con un estado trampa (los algoritmos requieren una
       funcion de transicion total).
    2. Se calcula la particion en clases de equivalencia.
    3. Se construye el AFD cociente.
    4. Se eliminan los estados inalcanzables y los muertos.
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


def _particion_por_myhill(estados, transiciones, aceptacion, alfabeto):
    """Llenado de tabla de pares (Myhill-Nerode).

    Se marca un par {p, q} cuando se demuestra que ALGUNA cadena los
    distingue:

        base    : uno acepta y el otro no (los distingue la cadena vacia)
        paso    : existe un simbolo a tal que {d(p,a), d(q,a)} ya esta marcado
                  (si w distingue a los destinos, entonces a·w distingue p y q)

    Se repite hasta que una pasada no marque nada nuevo. Los pares que
    quedaron sin marcar son equivalentes, y su cierre transitivo da las
    clases de equivalencia.
    """
    lista = sorted(estados)
    pares = [(p, q) for i, p in enumerate(lista) for q in lista[i + 1:]]

    # base: un estado de aceptacion nunca es equivalente a uno que no lo es
    marcados = {
        (p, q) for (p, q) in pares
        if (p in aceptacion) != (q in aceptacion)
    }

    def par(a, b):
        return (a, b) if a <= b else (b, a)

    # paso inductivo, hasta punto fijo
    cambio = True
    while cambio:
        cambio = False
        for (p, q) in pares:
            if (p, q) in marcados:
                continue
            for simbolo in alfabeto:
                dp = transiciones.get((p, simbolo))
                dq = transiciones.get((q, simbolo))
                if dp == dq:
                    continue
                if par(dp, dq) in marcados:
                    marcados.add((p, q))
                    cambio = True
                    break

    # los pares sin marcar son equivalentes: se unen en clases
    clase = {e: e for e in lista}

    def raiz(e):
        while clase[e] != e:
            clase[e] = clase[clase[e]]
            e = clase[e]
        return e

    for (p, q) in pares:
        if (p, q) not in marcados:
            rp, rq = raiz(p), raiz(q)
            if rp != rq:
                clase[max(rp, rq)] = min(rp, rq)

    bloques = {}
    for e in lista:
        bloques.setdefault(raiz(e), set()).add(e)

    return [frozenset(b) for b in bloques.values()]


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


def minimizar(afd, metodo='agrupacion'):
    """Retorna un AFD minimo equivalente al AFD recibido.

    metodo: 'agrupacion' (refinamiento de particiones) o 'myhill'
            (llenado de tabla de pares). Ambos dan el mismo resultado.
    """
    if metodo not in ('agrupacion', 'myhill'):
        raise ValueError(f"Metodo desconocido: {metodo}")

    if not afd.alfabeto:
        return AFD(set(afd.estados), set(afd.alfabeto), dict(afd.transiciones),
                   afd.inicio, set(afd.aceptacion), {})

    estados, transiciones = _completar(afd)

    if metodo == 'agrupacion':
        particion = _particion_inicial(estados, afd.aceptacion)
        particion = _refinar(particion, transiciones, afd.alfabeto)
    else:
        particion = _particion_por_myhill(
            estados, transiciones, afd.aceptacion, afd.alfabeto)

    # Se numeran los bloques recorriendolos por BFS desde el que contiene al
    # estado inicial, en orden de alfabeto. Esa numeracion es canonica: no
    # depende de como cada metodo haya construido la particion, asi que
    # 'agrupacion' y 'myhill' producen tablas identicas y comparables.
    bloque_de = {}
    for i, bloque in enumerate(particion):
        for estado in bloque:
            bloque_de[estado] = i

    raiz = bloque_de[afd.inicio]
    orden = [raiz]
    vistos = {raiz}
    cola = [raiz]
    while cola:
        actual = cola.pop(0)
        representante = next(iter(sorted(particion[actual])))
        for simbolo in sorted(afd.alfabeto):
            destino = transiciones.get((representante, simbolo))
            if destino is None:
                continue
            bloque = bloque_de[destino]
            if bloque not in vistos:
                vistos.add(bloque)
                orden.append(bloque)
                cola.append(bloque)

    # los bloques no alcanzables van al final (los quita _limpiar de todos modos)
    orden += [i for i in range(len(particion)) if i not in vistos]
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


def verificar_equivalencia(afd):
    """Comprueba que los dos metodos produzcan el mismo AFD minimo.

    Retorna (coinciden, minimo_agrupacion, minimo_myhill). La comparacion es
    estructural: como ambos numeran los bloques dejando el inicial como 0 y
    despues compactan, un AFD minimo unico produce tablas identicas.
    """
    a = minimizar(afd, 'agrupacion')
    m = minimizar(afd, 'myhill')

    coinciden = (
        a.estados == m.estados
        and a.inicio == m.inicio
        and a.aceptacion == m.aceptacion
        and a.transiciones == m.transiciones
    )
    return coinciden, a, m
