#!/usr/bin/env python3
"""
Proyecto 1 - Teoria de la Computacion
Universidad del Valle de Guatemala

Lee un archivo de texto con una expresion regular por linea y, para cada una:
    1. Convierte de infix a postfix (Shunting Yard)
    2. Construye el AFN (Thompson)
    3. Construye el AFD (Subconjuntos)
    4. Minimiza el AFD
    5. Simula el AFN y ambos AFDs con la cadena w

Uso:
    python main.py                          -> modo interactivo
    python main.py expresiones.txt          -> pide la cadena w y procesa el archivo
    python main.py expresiones.txt babbaaaa -> procesa el archivo con esa cadena
"""

import os
import re
import sys

from src.shunting_yard import a_postfix, validar, EPSILON
from src.thompson import construir_afn
from src.subconjuntos import construir_afd
from src.minimizacion import minimizar, verificar_equivalencia
from src.simulacion import (simular_afn, simular_afd,
                            formato_traza_afn, formato_traza_afd)
from src.visualizacion import graficar_afn, graficar_afd, GRAPHVIZ_DISPONIBLE

CARPETA_SALIDA = 'output'
ANCHO = 72


def separador(caracter='='):
    print(caracter * ANCHO)


def respuesta(aceptada):
    """El enunciado pide un "si" en caso de aceptacion y un "no" si no."""
    return "sí" if aceptada else "no"


def procesar(regex, cadena, indice=1, carpeta=CARPETA_SALIDA, verbose=True):
    """Ejecuta el pipeline completo para una expresion regular y una cadena."""
    separador()
    print(f"EXPRESION {indice}: {regex}")
    print(f"CADENA w  : {cadena if cadena else '(vacia)'}")
    separador()

    validar(regex)

    # 1. Shunting Yard
    tokens, postfix = a_postfix(regex)
    print(f"\n[1] Postfix (Shunting Yard): {postfix}")

    # 2. Thompson
    afn = construir_afn(tokens)
    print(f"\n[2] AFN construido con Thompson: "
          f"{len(afn.estados)} estados, alfabeto = {sorted(afn.alfabeto)}")
    if verbose:
        print(afn)

    # 3. Subconjuntos
    afd = construir_afd(afn)
    print(f"\n[3] AFD por construccion de subconjuntos: "
          f"{len(afd.estados)} estados")
    if verbose:
        print(afd)

    # 4. Minimizacion (los dos metodos deben dar el mismo AFD minimo)
    coinciden, afd_min, afd_min_myhill = verificar_equivalencia(afd)
    print(f"\n[4] AFD minimizado: {len(afd.estados)} -> "
          f"{len(afd_min.estados)} estados")
    print(f"    Agrupacion (refinamiento de particiones): "
          f"{len(afd_min.estados)} estados")
    print(f"    Myhill-Nerode (tabla de pares)          : "
          f"{len(afd_min_myhill.estados)} estados")
    if coinciden:
        print("    Los dos metodos producen el mismo AFD minimo. [OK]")
    else:
        print("    [ADVERTENCIA] Los dos metodos NO coinciden.")
    if verbose:
        print(afd_min)

    # 5. Simulacion
    print("\n[5] Simulacion de la cadena w:")
    ac_afn, traza_afn = simular_afn(afn, cadena)
    ac_afd, traza_afd = simular_afd(afd, cadena)
    ac_min, traza_min = simular_afd(afd_min, cadena)

    print(f"    AFN            : {respuesta(ac_afn)}")
    if verbose:
        print(f"      traza: {formato_traza_afn(traza_afn)}")
    print(f"    AFD            : {respuesta(ac_afd)}")
    if verbose:
        print(f"      traza: {formato_traza_afd(traza_afd)}")
    print(f"    AFD minimizado : {respuesta(ac_min)}")
    if verbose:
        print(f"      traza: {formato_traza_afd(traza_min)}")

    if not (ac_afn == ac_afd == ac_min):
        print("\n    [ADVERTENCIA] Los automatas no coinciden en el resultado.")

    print(f"\n    >>> w = '{cadena}' {'SÍ' if ac_afn else 'NO'} pertenece a L(r)")

    # Imagenes
    if not GRAPHVIZ_DISPONIBLE:
        print("\n[!] graphviz no esta instalado: no se generaron imagenes.")
        print("    Instalalo con: pip install graphviz && sudo dnf install graphviz")
    else:
        os.makedirs(carpeta, exist_ok=True)
        archivos = [
            graficar_afn(afn, os.path.join(carpeta, f'{indice:02d}_afn'),
                         f'AFN (Thompson) - r = {regex}'),
            graficar_afd(afd, os.path.join(carpeta, f'{indice:02d}_afd'),
                         f'AFD (Subconjuntos) - r = {regex}',
                         mostrar_etiquetas=True),
            graficar_afd(afd_min, os.path.join(carpeta, f'{indice:02d}_afd_min'),
                         f'AFD minimizado - r = {regex}'),
        ]
        print("\n[6] Imagenes generadas:")
        for archivo in archivos:
            if archivo:
                print(f"    {archivo}")

    print()
    return ac_afn, ac_afd, ac_min


def limpiar_salida(carpeta=CARPETA_SALIDA):
    """Borra las imagenes de corridas anteriores.

    Los nombres solo dependen del indice de la expresion, asi que una corrida
    con menos lineas dejaria mezcladas las imagenes de la anterior y pareceria
    que se generaron ahora. Ver HALLAZGOS.md #7.
    """
    if not os.path.isdir(carpeta):
        return 0
    borrados = 0
    for nombre in os.listdir(carpeta):
        if re.fullmatch(r'\d+_(afn|afd|afd_min)(\.png|\.svg|\.dot)?', nombre):
            os.remove(os.path.join(carpeta, nombre))
            borrados += 1
    return borrados


def procesar_archivo(ruta, cadena):
    if not os.path.exists(ruta):
        print(f"Error: no se encontro el archivo '{ruta}'")
        sys.exit(1)

    if os.path.isdir(ruta):
        print(f"Error: '{ruta}' es un directorio, no un archivo")
        sys.exit(1)

    try:
        # utf-8-sig consume el BOM que agregan los editores de Windows.
        # Con utf-8 a secas, el BOM entra al alfabeto como un simbolo mas
        # y altera la primera expresion sin avisar. Ver HALLAZGOS.md #4.
        with open(ruta, encoding='utf-8-sig') as f:
            lineas = [ln.rstrip('\n').rstrip('\r') for ln in f]
    except UnicodeDecodeError:
        print(f"Error: '{ruta}' no es un archivo de texto legible (UTF-8)")
        sys.exit(1)
    except OSError as e:
        print(f"Error: no se pudo leer '{ruta}': {e}")
        sys.exit(1)

    # Cada linea trae una expresion regular. Opcionalmente puede traer tambien
    # su propia cadena w, separada por un tabulador: "regex<TAB>cadena".
    expresiones = []
    for linea in lineas:
        limpia = linea.strip()
        if not limpia or limpia.startswith('#'):
            continue
        if '\t' in linea:
            regex, _, propia = linea.partition('\t')
            propia = propia.strip()
            # Un tabulador al final de la linea no significa "cadena vacia":
            # significa que la linea no trae cadena. Ver HALLAZGOS.md #6.
            expresiones.append((regex.strip(), propia if propia else None))
        else:
            expresiones.append((limpia, None))

    if not expresiones:
        print(f"El archivo '{ruta}' no contiene expresiones regulares.")
        return

    borrados = limpiar_salida()
    print(f"\nProcesando {len(expresiones)} expresiones de '{ruta}'")
    print(f"Simbolo designado para epsilon: '{EPSILON}'")
    if borrados:
        print(f"Se borraron {borrados} imagenes de la corrida anterior")
    print()

    for i, (regex, propia) in enumerate(expresiones, start=1):
        try:
            procesar(regex, propia if propia is not None else cadena, indice=i)
        except ValueError as e:
            # procesar() ya imprimio el encabezado antes de que validar()
            # lanzara, asi que aqui solo va el error. Ver HALLAZGOS.md M5.
            print(f"  [ERROR] {e}\n")


def modo_interactivo():
    print("\nProyecto 1 - Teoria de la Computacion")
    print(f"Simbolo designado para epsilon: '{EPSILON}'")
    print("Operadores: | (union), * (kleene), + (una o mas), "
          "? (opcional), () y \\ para escapar\n")

    regex = input("Expresion regular r: ").strip()
    cadena = input("Cadena w            : ").strip()

    try:
        procesar(regex, cadena)
    except ValueError as e:
        print(f"\n[ERROR] {e}")


def main():
    if len(sys.argv) == 1:
        modo_interactivo()
    elif len(sys.argv) == 2:
        cadena = input("Cadena w a evaluar: ").strip()
        procesar_archivo(sys.argv[1], cadena)
    else:
        procesar_archivo(sys.argv[1], sys.argv[2])


if __name__ == '__main__':
    main()
