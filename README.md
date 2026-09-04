# Proyecto 1 — Teoría de la Computación

Implementación de los algoritmos básicos para la construcción de autómatas finitos
a partir de expresiones regulares. El programa recibe una expresión regular `r` y
una cadena `w`, construye el AFN, el AFD y el AFD minimizado, genera sus imágenes
y determina si `w ∈ L(r)`.

**Universidad del Valle de Guatemala** — Agosto 2025

---

## Pipeline

| # | Etapa | Módulo | Puntos |
|---|-------|--------|--------|
| 1 | Shunting Yard (infix → postfix) | `src/shunting_yard.py` | 3 |
| 2 | Construcción de Thompson (postfix → AFN) | `src/thompson.py` | 3 |
| 3 | Construcción de subconjuntos (AFN → AFD) | `src/subconjuntos.py` | 3 |
| 4 | Minimización del AFD (dos métodos) | `src/minimizacion.py` | 3 |
| 5 | Simulación del AFN y los AFDs | `src/simulacion.py` | 3 |

Las imágenes se generan con Graphviz desde `src/visualizacion.py`.

---

## Instalación

```bash
pip install -r requirements.txt
```

Además se necesita el binario de Graphviz:

```bash
sudo dnf install graphviz      # Fedora
sudo apt install graphviz      # Debian / Ubuntu
brew install graphviz          # macOS
```

## Uso

```bash
# Procesar un archivo con una regex por línea (lo pide la cadena w)
python main.py expresiones.txt

# Pasando la cadena directamente
python main.py expresiones.txt babbaaaa

# Modo interactivo (una sola expresión)
python main.py
```

Las imágenes quedan en `output/` con el formato `NN_afn.png`, `NN_afd.png`
y `NN_afd_min.png`, donde `NN` es el número de línea de la expresión.

## Visor en vivo

Además del CLI hay un visor web que redibuja los tres autómatas mientras se
escribe y anima la simulación símbolo por símbolo sobre el grafo.

```bash
python app.py
# abrir http://127.0.0.1:5000
```

- La **cinta** muestra la cadena `w`; la cabeza de lectura avanza con `◀ ▶`,
  con las flechas del teclado, con la barra espaciadora, o haciendo clic en
  cualquier celda para saltar a ese paso.
- Los estados activos se resaltan en menta, los de aceptación en ámbar, y si
  la máquina se queda sin transición la celda se marca en coral.
- En el AFN se resalta el **conjunto** de estados activos; en los AFDs, uno solo.
  Poner los dos lado a lado deja ver el no determinismo.
- Rueda del mouse para zoom, arrastrar para mover, `encajar` para reencuadrar.

### El archivo del calificador

`cargar .txt` lee el archivo y evalúa todas sus líneas contra la cadena `w` de
una sola vez. La lista muestra, por expresión: el postfix (al pasar el mouse),
los tamaños `AFN → AFD → mínimo`, y si acepta `w`. Un clic en cualquier línea la
abre en el grafo. Al cambiar `w` se re-evalúa la lista completa.

Las líneas con error de sintaxis se marcan sin cortar el resto, y si por algún
motivo los tres autómatas no coincidieran en su respuesta la línea se marca con
`!`.

`generar PNGs` corre el pipeline completo sobre todas las líneas y deja las
imágenes en `output/`, igual que el CLI.

### La pestaña de minimización

Muestra los dos métodos en paralelo sobre la misma expresión:

- A la izquierda, la **tabla de pares de Myhill-Nerode**. Cada celda marcada
  lleva el número de la ronda en que se marcó, y al pasar el mouse aparece el
  motivo (qué símbolo y qué par ya marcado la causó). Las celdas que quedan en
  menta con `≡` son pares equivalentes.
- A la derecha, el **refinamiento de particiones**, ronda por ronda, desde la
  partición inicial hasta el punto fijo.

El botón `llenar tabla` avanza las rondas de los dos a la vez. Al final, los
pares equivalentes de la tabla coinciden con los bloques que sobrevivieron al
refinamiento: la misma relación de equivalencia calculada de dos maneras.

El estado `T` que aparece en la tabla es el trampa que se agrega para completar
la función de transición; desaparece al final del proceso.

El visor reutiliza exactamente los mismos módulos de `src/` que el CLI, así que
lo que se ve en pantalla es el mismo cálculo que genera los PNG del entregable.

## Pruebas

```bash
python tests.py
```

Verifica 30 casos comprobando que el AFN, el AFD y el AFD minimizado
siempre coincidan en la respuesta y que ésta sea la esperada.

---

## Sintaxis de las expresiones regulares

| Símbolo | Significado |
|---------|-------------|
| `\|` | unión |
| (implícito) | concatenación |
| `*` | cerradura de Kleene (cero o más) |
| `+` | una o más repeticiones |
| `?` | cero o una repetición |
| `()` | agrupación |
| `ε` | epsilon (cadena vacía) |
| `\` | escape, p. ej. `\*` es el símbolo literal `*` |

**Símbolo designado para ε:** `ε` (U+03B5). Se eligió porque no es una letra ni
un número del alfabeto de entrada, así que no hay riesgo de que colisione con un
símbolo del lenguaje. Cualquier otro carácter que no sea operador se trata como
símbolo del alfabeto.

### Formato del archivo de entrada

Una expresión regular por línea. Las líneas vacías y las que empiezan con `#`
se ignoran.

```
(b|b)*abb(a|b)*
(a*|b*)c
0?(1?)?0*
```

Opcionalmente una línea puede traer su propia cadena `w`, separada por un
tabulador. Las líneas sin cadena usan la que se pasó por la línea de comandos.

```
(a|b)*abb	babb
(a|b)*abb	baba
```

---

## Estructura

```
.
├── main.py                 # programa principal / CLI
├── app.py                  # servidor del visor en vivo
├── tests.py                # suite de pruebas
├── expresiones.txt         # archivo de entrada de ejemplo
├── requirements.txt
├── output/                 # imágenes generadas
└── src/
    ├── automata.py         # estructuras AFN y AFD
    ├── shunting_yard.py    # tokenizador + infix a postfix
    ├── thompson.py         # postfix a AFN
    ├── subconjuntos.py     # AFN a AFD (e-closure, move)
    ├── minimizacion.py     # refinamiento de particiones
    ├── simulacion.py       # simulación de AFN y AFD
    ├── pasos.py            # simulación paso a paso (para el visor)
    └── visualizacion.py    # Graphviz (PNG y SVG)
```

Y para el visor:

```
├── templates/index.html
└── static/
    ├── estilo.css
    └── visor.js
```

---

## Notas de implementación

- **Thompson:** cada fragmento mantiene un único estado inicial sin transiciones
  de entrada y un único estado de aceptación sin transiciones de salida, por lo
  que los fragmentos se componen sin ambigüedad.
- **Subconjuntos:** las transiciones hacia el conjunto vacío no se guardan; el
  estado muerto queda implícito y la simulación lo reporta como rechazo.
- **Minimización:** están implementados los dos métodos, y ambos calculan la
  misma relación de equivalencia de Myhill-Nerode:
  - `minimizar(afd, 'agrupacion')` — refinamiento de particiones (Moore /
    Hopcroft): se parte del bloque de aceptación contra el de no aceptación y se
    refina agrupando por firma hasta el punto fijo.
  - `minimizar(afd, 'myhill')` — llenado de tabla de pares: se marca cada par de
    estados distinguibles (base: uno acepta y el otro no; paso: existe un
    símbolo cuyos destinos ya están marcados) y los pares sin marcar forman las
    clases de equivalencia.

  `verificar_equivalencia(afd)` corre los dos y comprueba que produzcan el mismo
  AFD mínimo; el CLI lo reporta en cada expresión y `tests.py` lo verifica en los
  30 casos. Antes de minimizar se completa el AFD con un estado trampa (ambos
  algoritmos requieren una función de transición total). Al terminar se eliminan
  los estados inalcanzables y los muertos, y los bloques se numeran por BFS desde
  el inicial: una numeración canónica que hace comparables las salidas de los dos
  métodos.
- **Trazabilidad:** el AFD por subconjuntos guarda a qué conjunto de estados del
  AFN corresponde cada estado, y el AFD minimizado guarda qué estados del AFD
  original quedaron fusionados en cada bloque. Ambos se imprimen y el primero se
  muestra dentro de los nodos de la imagen.

## Convenciones de los grafos

- El estado inicial se marca con una flecha que entra desde un punto.
- Los estados de aceptación se dibujan con doble círculo.
- Las transiciones ε se dibujan en gris para distinguirlas.
- Las aristas paralelas se agrupan en una sola con las etiquetas separadas por coma.
