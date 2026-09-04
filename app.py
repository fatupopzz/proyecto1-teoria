#!/usr/bin/env python3
"""
Visor en vivo del Proyecto 1.

Levanta un servidor local donde se escribe la expresion regular y la cadena,
y se ven los tres automatas redibujarse al instante, con la simulacion
avanzando simbolo por simbolo sobre el grafo.

Uso:
    python app.py
    -> abrir http://127.0.0.1:5000
"""

import os

from flask import Flask, jsonify, render_template, request

from src.shunting_yard import a_postfix, validar, EPSILON
from src.thompson import construir_afn
from src.subconjuntos import construir_afd
from src.minimizacion import minimizar, verificar_equivalencia
from src.pasos import pasos_afn, pasos_afd
from src.traza_min import traza_myhill, traza_agrupacion
from src.visualizacion import (grafo_afn, grafo_afd, a_svg, TEMA_WEB,
                               graficar_afn, graficar_afd)

CARPETA_SALIDA = 'output'

# Dibujar un automata grande con Graphviz es carisimo: el layout de un AFD de
# 257 estados toma casi un minuto, y el navegador se ahoga con la tabla de
# pares. Por encima de este tope se devuelven los datos sin la imagen.
# Ver HALLAZGOS.md #3.
TOPE_DIBUJO = 80
TOPE_TABLA = 40

app = Flask(__name__)


def _cuerpo():
    """Devuelve el JSON del pedido como diccionario.

    `get_json(silent=True) or {}` solo cubre el caso None: un JSON valido que
    sea lista o texto es truthy y despues revienta en el `.get()`.
    Ver HALLAZGOS.md A1.
    """
    datos = request.get_json(silent=True)
    return datos if isinstance(datos, dict) else {}


def _svg_seguro(constructor, n_estados):
    """Devuelve (svg, aviso). No dibuja si el automata es demasiado grande."""
    if n_estados > TOPE_DIBUJO:
        return None, (f'{n_estados} estados: demasiados para dibujar. '
                      f'El automata se construyo bien, solo se omite la imagen.')
    try:
        return a_svg(constructor()), None
    except RuntimeError as e:
        return None, str(e)


def _empaquetar_afn(afn, cadena):
    pasos, aceptada = pasos_afn(afn, cadena)
    svg, aviso = _svg_seguro(lambda: grafo_afn(afn, tema=TEMA_WEB),
                             len(afn.estados))
    return {
        'svg': svg,
        'aviso': aviso,
        'n_estados': len(afn.estados),
        'inicio': afn.inicio,
        'aceptacion': sorted(afn.aceptacion),
        'alfabeto': sorted(afn.alfabeto),
        'pasos': pasos,
        'aceptada': aceptada,
        'etiquetas': {},
    }


def _empaquetar_afd(afd, cadena, etiquetas_en_nodo=False):
    pasos, aceptada = pasos_afd(afd, cadena)
    svg, aviso = _svg_seguro(
        lambda: grafo_afd(afd, mostrar_etiquetas=etiquetas_en_nodo,
                          tema=TEMA_WEB),
        len(afd.estados))
    return {
        'svg': svg,
        'aviso': aviso,
        'n_estados': len(afd.estados),
        'inicio': afd.inicio,
        'aceptacion': sorted(afd.aceptacion),
        'alfabeto': sorted(afd.alfabeto),
        'pasos': pasos,
        'aceptada': aceptada,
        'etiquetas': {str(k): v for k, v in afd.etiquetas.items()},
    }


@app.route('/')
def inicio():
    return render_template('index.html', epsilon=EPSILON)


@app.route('/api/procesar', methods=['POST'])
def procesar():
    datos = _cuerpo()
    # los campos pueden venir de un cliente hecho a mano: se fuerzan a texto
    regex = str(datos.get('regex') or '').strip()
    cadena = str(datos.get('cadena') or '')

    if not regex:
        return jsonify({'ok': False, 'error': 'Escribí una expresión regular.'})

    try:
        validar(regex)
        tokens, postfix = a_postfix(regex)
        afn = construir_afn(tokens)
        afd = construir_afd(afn)
        coinciden, afd_min, _ = verificar_equivalencia(afd)
    except ValueError as e:
        return jsonify({'ok': False, 'error': str(e)})
    except Exception as e:  # noqa: BLE001
        return jsonify({'ok': False, 'error': f'No se pudo construir: {e}'})

    ajenos = sorted(set(cadena) - afn.alfabeto)

    try:
        automatas = {
            'afn': _empaquetar_afn(afn, cadena),
            'afd': _empaquetar_afd(afd, cadena, etiquetas_en_nodo=True),
            'min': _empaquetar_afd(afd_min, cadena),
        }
    except Exception as e:  # noqa: BLE001
        return jsonify({'ok': False, 'error': f'No se pudo dibujar: {e}'})

    # La tabla de pares crece con el cuadrado de los estados: por encima del
    # tope el navegador no puede con la cantidad de celdas.
    if len(afd.estados) <= TOPE_TABLA:
        minimizacion = {
            'myhill': traza_myhill(afd),
            'agrupacion': traza_agrupacion(afd),
            'coinciden': coinciden,
            'aviso': None,
        }
    else:
        minimizacion = {
            'myhill': None, 'agrupacion': None, 'coinciden': coinciden,
            'aviso': f'El AFD tiene {len(afd.estados)} estados: la tabla '
                     f'tendria {len(afd.estados) * (len(afd.estados) - 1) // 2} '
                     f'pares, demasiados para mostrar.',
        }

    return jsonify({
        'ok': True,
        'postfix': postfix,
        'cadena': cadena,
        'simbolos_ajenos': ajenos,
        'automatas': automatas,
        'minimizacion': minimizacion,
    })


@app.route('/api/lote', methods=['POST'])
def lote():
    """Evalua una lista de expresiones contra la misma cadena.

    Devuelve solo el veredicto y los tamanos: sin SVG, para que sea rapido
    aunque el archivo traiga muchas lineas.
    """
    datos = _cuerpo()
    expresiones = datos.get('expresiones') or []
    cadena = datos.get('cadena') or ''

    resultados = []
    for i, regex in enumerate(expresiones, start=1):
        fila = {'n': i, 'regex': regex}
        try:
            validar(regex)
            tokens, postfix = a_postfix(regex)
            afn = construir_afn(tokens)
            afd = construir_afd(afn)
            afd_min = minimizar(afd)

            _, ac_afn = pasos_afn(afn, cadena)
            _, ac_afd = pasos_afd(afd, cadena)
            _, ac_min = pasos_afd(afd_min, cadena)

            fila.update({
                'ok': True,
                'postfix': postfix,
                'tamanos': [len(afn.estados), len(afd.estados), len(afd_min.estados)],
                'aceptada': ac_afn,
                'coinciden': ac_afn == ac_afd == ac_min,
            })
        except Exception as e:  # noqa: BLE001
            fila.update({'ok': False, 'error': str(e)})
        resultados.append(fila)

    return jsonify({'ok': True, 'resultados': resultados})


@app.route('/api/imagenes', methods=['POST'])
def imagenes():
    """Genera los PNG de todas las expresiones en la carpeta output/."""
    datos = _cuerpo()
    expresiones = datos.get('expresiones') or []

    carpeta = os.path.abspath(CARPETA_SALIDA)
    os.makedirs(carpeta, exist_ok=True)
    generados, fallidas = 0, []

    for i, regex in enumerate(expresiones, start=1):
        try:
            validar(regex)
            tokens, _ = a_postfix(regex)
            afn = construir_afn(tokens)
            afd = construir_afd(afn)
            afd_min = minimizar(afd)

            graficar_afn(afn, os.path.join(carpeta, f'{i:02d}_afn'),
                         f'AFN (Thompson) - r = {regex}')
            graficar_afd(afd, os.path.join(carpeta, f'{i:02d}_afd'),
                         f'AFD (Subconjuntos) - r = {regex}',
                         mostrar_etiquetas=True)
            graficar_afd(afd_min, os.path.join(carpeta, f'{i:02d}_afd_min'),
                         f'AFD minimizado - r = {regex}')
            generados += 3
        except Exception:  # noqa: BLE001
            fallidas.append(i)

    return jsonify({'ok': True, 'generados': generados,
                    'fallidas': fallidas, 'carpeta': carpeta})


if __name__ == '__main__':
    print('\n  Visor en vivo — Proyecto 1')
    print('  http://127.0.0.1:5000\n')
    app.run(debug=True, port=5000)
