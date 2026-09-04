"""
Trazas paso a paso de la minimizacion, para el visor.

Reproduce los dos metodos de src/minimizacion.py pero guardando el estado
intermedio en cada ronda, de modo que se pueda mostrar como se llena la tabla
de pares y como se van separando los bloques.

El calculo es el mismo; lo unico que se agrega es el registro.
"""

from .minimizacion import (_completar, _particion_inicial, TRAMPA)


def _nombre(estado):
    return 'T' if estado == TRAMPA else str(estado)


def traza_myhill(afd):
    """Registra el llenado de la tabla de pares (Myhill-Nerode).

    Devuelve, por cada par de estados, en que ronda se marco y por que:
        ronda 0 : uno acepta y el otro no (los distingue la cadena vacia)
        ronda k : existe un simbolo cuyos destinos ya estaban marcados
    Los pares que nunca se marcan son equivalentes.
    """
    if not afd.alfabeto:
        return None

    estados, transiciones = _completar(afd)
    lista = sorted(estados)
    alfabeto = sorted(afd.alfabeto)
    pares = [(p, q) for i, p in enumerate(lista) for q in lista[i + 1:]]

    info = {}

    # Ronda 0: la cadena vacia distingue aceptacion de no aceptacion
    for (p, q) in pares:
        if (p in afd.aceptacion) != (q in afd.aceptacion):
            info[(p, q)] = {
                'ronda': 0,
                'motivo': f'{_nombre(p)} acepta y {_nombre(q)} no'
                          if p in afd.aceptacion else
                          f'{_nombre(q)} acepta y {_nombre(p)} no',
            }

    def par(a, b):
        return (a, b) if a <= b else (b, a)

    # Rondas siguientes: propagacion hacia atras
    ronda = 0
    while True:
        ronda += 1
        nuevos = []
        for (p, q) in pares:
            if (p, q) in info:
                continue
            for simbolo in alfabeto:
                dp = transiciones.get((p, simbolo))
                dq = transiciones.get((q, simbolo))
                if dp == dq:
                    continue
                destino = par(dp, dq)
                if destino in info:
                    nuevos.append(((p, q), {
                        'ronda': ronda,
                        'motivo': f"con '{simbolo}' van a "
                                  f"{{{_nombre(dp)}, {_nombre(dq)}}}, "
                                  f"ya marcado en la ronda {info[destino]['ronda']}",
                    }))
                    break
        if not nuevos:
            break
        info.update(nuevos)

    equivalentes = [(p, q) for (p, q) in pares if (p, q) not in info]

    return {
        'estados': [_nombre(e) for e in lista],
        'aceptacion': [_nombre(e) for e in lista if e in afd.aceptacion],
        'trampa': _nombre(TRAMPA) if TRAMPA in estados else None,
        'rondas': ronda - 1,
        'celdas': [
            {'p': _nombre(p), 'q': _nombre(q),
             'ronda': info[(p, q)]['ronda'], 'motivo': info[(p, q)]['motivo']}
            for (p, q) in pares if (p, q) in info
        ],
        'equivalentes': [
            {'p': _nombre(p), 'q': _nombre(q)} for (p, q) in equivalentes
        ],
        'n_pares': len(pares),
    }


def traza_agrupacion(afd):
    """Registra el refinamiento de particiones, ronda por ronda.

    Devuelve la lista de particiones: la inicial (aceptacion vs no
    aceptacion) y el resultado de cada pasada de refinamiento, hasta el
    punto fijo.
    """
    if not afd.alfabeto:
        return None

    estados, transiciones = _completar(afd)
    alfabeto = sorted(afd.alfabeto)
    particion = _particion_inicial(estados, afd.aceptacion)

    historial = [{
        'titulo': 'Partición inicial: aceptación contra no aceptación',
        'bloques': [sorted(_nombre(e) for e in b) for b in particion],
    }]

    ronda = 0
    while True:
        ronda += 1
        pertenece = {}
        for i, bloque in enumerate(particion):
            for estado in bloque:
                pertenece[estado] = i

        nueva = []
        separo = False
        for bloque in particion:
            grupos = {}
            for estado in bloque:
                firma = tuple(
                    pertenece.get(transiciones.get((estado, s)))
                    for s in alfabeto
                )
                grupos.setdefault(firma, set()).add(estado)
            if len(grupos) > 1:
                separo = True
            nueva.extend(frozenset(g) for g in grupos.values())

        particion = nueva
        historial.append({
            'titulo': f'Ronda {ronda}: '
                      + ('se separaron bloques' if separo
                         else 'ningún bloque se separó, punto fijo'),
            'bloques': [sorted(_nombre(e) for e in b) for b in particion],
        })

        if not separo:
            break

    return {'historial': historial, 'rondas': ronda}
