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
y `NN_afd_min.png`, donde `NN` es la posición de la expresión entre las líneas
válidas del archivo (las líneas vacías y los comentarios no cuentan). La carpeta
se limpia al inicio de cada corrida, así que nunca quedan imágenes de una
corrida anterior mezcladas con las nuevas.

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
python tests.py                  # 30 casos escritos a mano, corre en un instante
python pruebas_exhaustivas.py    # suite completa, ~6600 verificaciones
python pruebas_exhaustivas.py --rapido
python pruebas_exhaustivas.py --semilla 42   # reproducir una corrida
```

`tests.py` verifica 30 casos fijos comprobando que el AFN, el AFD y el AFD
minimizado (por los dos métodos) coincidan y que la respuesta sea la esperada.

`pruebas_exhaustivas.py` genera los casos en lugar de escribirlos, y se apoya
en un **oráculo independiente**: el módulo `re` de Python. Siete bloques:

| # | Bloque | Qué comprueba |
|---|---|---|
| 1 | Oráculo | ~38 000 comparaciones contra `re.fullmatch` sobre expresiones generadas al azar y todas las cadenas hasta longitud 6 |
| 2 | Invariantes | El AFN de Thompson tiene un solo estado de aceptación y sin salidas; ≤ 2n estados; epsilon fuera del alfabeto; el AFD arranca en 0 y no tiene inalcanzables; los dos métodos de minimización coinciden; minimizar es idempotente |
| 3 | Minimalidad | Por fuerza bruta: ningún par de estados del AFD mínimo es equivalente, y ninguno está muerto |
| 4 | Casos límite | 20 expresiones válidas (escapes, mayúsculas, símbolos no alfanuméricos, `(a*)*`, `(a\|b)**`, epsilon anidado) y 17 inválidas que deben lanzar `ValueError` |
| 5 | Estrés | Anidamiento de 25 niveles, unión de 12 ramas, explosión del AFD verificada contra el mínimo teórico 2ⁿ para n=1..7, y una cadena de 40 003 símbolos |
| 6 | Coherencia | La cadena vacía, la e-closure del inicial, las etiquetas de trazabilidad, y los símbolos fuera del alfabeto |
| 7 | Robustez | 40 000 cadenas de basura como expresión: ninguna debe lanzar nada distinto de `ValueError` |

Cada corrida usa una semilla nueva y la imprime, así que si alguna vez falla se
puede reproducir exactamente con `--semilla N`.

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

Los espacios en blanco se ignoran dentro de la expresión, así que `a b` es lo
mismo que `ab`. Para usar un espacio como símbolo del alfabeto hay que
escaparlo: `a\ b`.

**Símbolo designado para ε:** `ε` (U+03B5). Se eligió porque no es una letra ni
un número del alfabeto de entrada, así que no hay riesgo de que colisione con un
símbolo del lenguaje. Cualquier otro carácter que no sea operador se trata como
símbolo del alfabeto.

### Formato del archivo de entrada

Una expresión regular por línea. Las líneas vacías y las que empiezan con `#`
se ignoran; el programa avisa en pantalla de cada línea que salta, con su
número, para que nada pase en silencio si el archivo lo trae el calificador.

```
(b|b)*abb(a|b)*
(a*|b*)c
0?(1?)?0*
```

Opcionalmente una línea puede traer su propia cadena `w`, separada por un
tabulador. Las líneas sin cadena usan la que se pasó por la línea de comandos.
También aquí el programa avisa de cada línea que parte por un tabulador.

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
    clases de equivalencia. La propagación va hacia atrás, con una cola: cada
    par recién marcado avisa a los pares que llegan a él por algún símbolo, en
    vez de recorrer los C(n,2) pares en cada ronda. Es el mismo resultado en
    O(n²·|Σ|) en lugar de O(rondas·n²·|Σ|).

  Los dos métodos no tardan lo mismo, y no pueden: la tabla de pares tiene
  C(n,2) celdas por definición, así que Myhill-Nerode es cuadrático, mientras
  que el refinamiento de particiones es O(n log n) porque nunca construye la
  tabla.

  `verificar_equivalencia(afd)` corre los dos y comprueba que produzcan el mismo
  AFD mínimo; el CLI lo reporta en cada expresión y `tests.py` lo verifica en los
  30 casos. El visor lo hace por debajo de 600 estados, y por encima minimiza
  solo por agrupación y lo dice, para seguir respondiendo al instante. Antes de minimizar se completa el AFD con un estado trampa (ambos
  algoritmos requieren una función de transición total). Al terminar se eliminan
  los estados inalcanzables y los muertos, y los bloques se numeran por BFS desde
  el inicial: una numeración canónica que hace comparables las salidas de los dos
  métodos.
- **Dibujo:** las etiquetas de las aristas se escapan antes de pasarlas a
  Graphviz, porque el módulo de Python entrecomilla pero no escapa la barra
  invertida, y un símbolo `\` del alfabeto dejaba una cadena sin cerrar en el
  DOT. Si aun así el render falla, se guarda el `.dot` y se imprime un aviso
  explícito en vez de devolver la ruta en silencio.
- **Topes del visor:** por encima de 80 estados no se dibuja el autómata y por
  encima de 40 no se muestra la tabla de pares. El layout de Graphviz para un
  AFD de 257 estados tarda casi un minuto, y la tabla tendría más de 32 000
  celdas. Los autómatas se construyen igual; solo se omite la imagen.
- **Trazabilidad:** el AFD por subconjuntos guarda a qué conjunto de estados del
  AFN corresponde cada estado, y el AFD minimizado guarda qué estados del AFD
  original quedaron fusionados en cada bloque. Ambos se imprimen y el primero se
  muestra dentro de los nodos de la imagen.

## Convenciones de los grafos

- El estado inicial se marca con una flecha que entra desde un punto.
- Los estados de aceptación se dibujan con doble círculo.
- Las transiciones ε se dibujan en gris para distinguirlas.
- Las aristas paralelas se agrupan en una sola con las etiquetas separadas por coma.
