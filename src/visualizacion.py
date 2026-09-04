"""
Generacion de las imagenes de los automatas usando Graphviz.

Convenciones del grafo:
    - El estado inicial se marca con una flecha que viene de la nada.
    - Los estados de aceptacion se dibujan con doble circulo.
    - Cada arista se etiqueta con el simbolo (o epsilon) que la produce.
"""

import os
from collections import defaultdict

try:
    from graphviz import Digraph
    GRAPHVIZ_DISPONIBLE = True
except ImportError:
    GRAPHVIZ_DISPONIBLE = False

from .shunting_yard import EPSILON

# Tema para las imagenes PNG del entregable (fondo blanco, tinta negra)
TEMA_IMPRESO = {
    'fondo': 'white', 'tinta': 'black', 'texto': 'black',
    'epsilon': 'gray50', 'titulo': True,
}

# Tema para el visor web (fondo transparente, trazo claro)
TEMA_WEB = {
    'fondo': 'transparent', 'tinta': '#4a6683', 'texto': '#cfe0ee',
    'epsilon': '#3d5a78', 'titulo': False,
}


def _escapar(texto):
    """Duplica las barras invertidas de una etiqueta.

    El modulo graphviz entrecomilla las etiquetas pero NO escapa la barra
    invertida, asi que un simbolo '\\' del alfabeto genera una cadena sin
    cerrar y `dot` falla con un error de sintaxis. Ver HALLAZGOS.md #1.
    """
    return texto.replace('\\', '\\\\')


def _base(titulo, tema=None):
    tema = tema or TEMA_IMPRESO
    g = Digraph(comment=titulo, format='png')
    atributos = dict(rankdir='LR', bgcolor=tema['fondo'],
                     fontname='Helvetica', fontsize='16')
    if tema['titulo']:
        atributos.update(label=titulo, labelloc='t')
    g.attr(**atributos)
    g.attr('node', fontname='Helvetica', fontsize='11',
           color=tema['tinta'], fontcolor=tema['texto'])
    g.attr('edge', fontname='Helvetica', fontsize='10',
           color=tema['tinta'], fontcolor=tema['texto'])
    return g


def _nodo_inicial(g, inicio):
    g.node('__inicio__', shape='point', width='0.08')
    g.edge('__inicio__', str(inicio))


def grafo_afn(afn, titulo='AFN (Thompson)', tema=None):
    """Construye el Digraph del AFN (sin renderizar)."""
    tema = tema or TEMA_IMPRESO
    g = _base(titulo, tema)

    for estado in sorted(afn.estados):
        forma = 'doublecircle' if estado in afn.aceptacion else 'circle'
        g.node(str(estado), shape=forma)

    _nodo_inicial(g, afn.inicio)

    # Se agrupan las etiquetas de aristas paralelas
    agrupadas = defaultdict(list)
    for (origen, simbolo), destinos in afn.transiciones.items():
        for destino in destinos:
            agrupadas[(origen, destino)].append(simbolo)

    for (origen, destino), simbolos in sorted(agrupadas.items()):
        unicos = sorted(set(simbolos))
        color = tema['epsilon'] if unicos == [EPSILON] else tema['tinta']
        etiqueta = ', '.join(_escapar(s) for s in unicos)
        g.edge(str(origen), str(destino), label=etiqueta, color=color,
               fontcolor=color)

    return g


def grafo_afd(afd, titulo='AFD', mostrar_etiquetas=False, tema=None):
    """Construye el Digraph del AFD (sin renderizar)."""
    tema = tema or TEMA_IMPRESO
    g = _base(titulo, tema)

    for estado in sorted(afd.estados):
        forma = 'doublecircle' if estado in afd.aceptacion else 'circle'
        if mostrar_etiquetas and estado in afd.etiquetas:
            texto = f"{estado}\\n{afd.etiquetas[estado]}"
            g.node(str(estado), label=texto, shape=forma)
        else:
            g.node(str(estado), shape=forma)

    _nodo_inicial(g, afd.inicio)

    agrupadas = defaultdict(list)
    for (origen, simbolo), destino in afd.transiciones.items():
        agrupadas[(origen, destino)].append(simbolo)

    for (origen, destino), simbolos in sorted(agrupadas.items()):
        etiqueta = ', '.join(_escapar(s) for s in sorted(simbolos))
        g.edge(str(origen), str(destino), label=etiqueta)

    return g


def graficar_afn(afn, ruta, titulo='AFN (Thompson)'):
    """Dibuja el AFN. Retorna la ruta del archivo generado (o None)."""
    if not GRAPHVIZ_DISPONIBLE:
        return None
    return _renderizar(grafo_afn(afn, titulo), ruta)


def graficar_afd(afd, ruta, titulo='AFD', mostrar_etiquetas=False):
    """Dibuja el AFD. Retorna la ruta del archivo generado (o None)."""
    if not GRAPHVIZ_DISPONIBLE:
        return None
    return _renderizar(grafo_afd(afd, titulo, mostrar_etiquetas), ruta)


def a_svg(grafo):
    """Renderiza un Digraph a una cadena SVG (para el visor web).

    Lanza RuntimeError si falla, para que quien llame pueda avisar en la
    interfaz en vez de devolver un 500.
    """
    try:
        return grafo.pipe(format='svg').decode('utf-8')
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f'Graphviz no pudo dibujar el automata: {e}') from e


def _renderizar(g, ruta):
    """Guarda el grafo. Si falta el binario 'dot', deja el archivo .dot."""
    carpeta = os.path.dirname(ruta) or '.'
    os.makedirs(carpeta, exist_ok=True)
    nombre = os.path.basename(ruta)

    try:
        return g.render(filename=nombre, directory=carpeta, cleanup=True)
    except Exception as e:  # noqa: BLE001
        # No se pudo generar la imagen (falta el binario `dot`, o el grafo
        # tiene un problema). Se guarda el .dot como respaldo, pero se avisa:
        # devolver la ruta en silencio hacia creer que el PNG existe.
        destino = os.path.join(carpeta, nombre + '.dot')
        with open(destino, 'w', encoding='utf-8') as f:
            f.write(g.source)
        print(f"    [AVISO] no se pudo generar {nombre}.png ({e}). "
              f"Se guardo {nombre}.dot en su lugar.")
        return destino
