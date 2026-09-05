# HALLAZGOS

Reporte de las pruebas adversarias sobre el Proyecto 1 (regex → AFN → AFD →
AFD mínimo → simulación).

Todo lo de aquí se reproduce con:

```bash
python pruebas_adversarias.py --semilla 20250904
```

La corrida completa tarda unos 17 segundos y **reporta 0 hallazgos**. Cada
bloque se puede correr suelto con `--solo <bloque>` y escalar con
`--iteraciones N`; la semilla siempre se imprime, y pasarla de vuelta reproduce
exactamente la misma corrida.

**Cifras del barrido grande** (`--solo oraculo --iteraciones 6000` con cuatro
semillas distintas, más los otros bloques a escala):

| bloque | volumen | hallazgos |
|---|---|---|
| oráculo contra `re.fullmatch` | 24 000 expresiones, **13 023 212 comparaciones** | 0 |
| invariantes estructurales | 2 000 expresiones | 0 |
| minimalidad por fuerza bruta | 1 957 AFDs mínimos | 0 |
| álgebra (mínimo único) | 12 familias fijas + 4 860 pares generados | 0 |
| basura | 300 000 cadenas al azar + 32 degeneradas | 0 |

---

## Estado tras los arreglos (verificado sobre `f34e83a`)

**Los 9 hallazgos, los 6 menores y los dos huecos A1 y A2 estan arreglados y
verificados.** La suite paso de 19 fallas a 0.

| # | Estado | Comprobacion |
|---|---|---|
| 1 | Arreglado | `_escapar()` duplica la barra invertida. Probado con 14 combinaciones (`\\`, `a\\`, `\\\\`, `\\|a`, `\\+\\`, `\"` mezclado con `\\`): PNG y SVG validos en todas, tambien en el titulo |
| 2 | Arreglado | `a_svg()` lanza `RuntimeError`, `_svg_seguro()` lo atrapa y el visor muestra el aviso en vez de un 500 |
| 3 | Arreglado | `TOPE_DIBUJO=80` y `TOPE_TABLA=40`. El JS maneja `svg: null` y `minimizacion.aviso`; los 10 IDs que toca la rama nueva existen en `index.html`. Medido: la peticion que tardaba 111 s ahora tarda 0.13 s |
| 4 | Arreglado | `utf-8-sig`. Probado con BOM solo y con BOM+CRLF+comentarios: alfabeto `['a','b']`, 6 estados |
| 5 | Arreglado | `_particion_por_myhill` propaga las marcas hacia atras con una cola. `'a'*2000` paso de 740 s a 1.3 s; en el visor, la peticion de 113 s paso a 0.34 s. Ver abajo |
| 6 | Arreglado | `regex<TAB>cadena` respeta la cadena propia; `regex<TAB>` vuelve a usar la `w` del CLI |
| 7 | Arreglado | `limpiar_salida()`. El patron borra `01_afn.png`, `01_afd_min.png`, `25_afn` (sin extension) y `.dot`, y conserva `mio.png`, `01_afd_minimo.png`, `grafico_afn.png`, `.DS_Store` |
| 8 | Arreglado | El docstring de `shunting_yard.py` ahora dice `'e' griega minuscula, U+03B5` |
| 9 | Arreglado | Directorio y binario dan mensaje y `exit 1` |
| A1 | Arreglado | `_cuerpo()` con `isinstance(datos, dict)`. 16 cuerpos hostiles (`[1,2]`, `"hola"`, `5`, `null`, `true`, JSON roto, sin content-type) en los tres endpoints: todos HTTP 200 |
| A2 | Arreglado | `traducir()` emite `(?:)`. `aε*b`, `ε*`, `ε?`, `ε+` compilan y coinciden con el AFD minimo. Ademas el generador ahora emite unarios sin parentesis, asi que las formas `ε*`, `ε+`, `ε?` de verdad se ejercitan en vez de quedar tapadas |

De paso se arreglo algo que no estaba en el reporte: en `grafo_afn` el color de
las aristas epsilon se decidia con `etiqueta == EPSILON`, que fallaba cuando la
arista agrupaba varios simbolos; ahora usa `unicos == [EPSILON]`.

**Nada de teoria se rompio.** Barrido sobre `f34e83a`: 24 000 expresiones y
**13 023 816 comparaciones** contra `re.fullmatch`, mas 2 000 de invariantes,
1 957 AFDs minimos por fuerza bruta, 4 860 pares algebraicos y 300 000 cadenas
de basura. Cero hallazgos. `tests.py` sigue en 30/30 y `pruebas_exhaustivas.py`
pasa con ocho semillas distintas (~6 600 verificaciones cada una).

### El hallazgo 5: que se hizo y hasta donde llega

El punto fijo de `_particion_por_myhill` recorria los C(n,2) pares en cada
ronda preguntando si los destinos de cada par ya estaban marcados. Ahora la
propagacion va **hacia atras**: se guardan los predecesores de cada estado y
cada par recien marcado avisa una sola vez a los pares que llegan a el, con una
cola. Es la misma relacion de Myhill-Nerode y el mismo resultado, sin repetir
trabajo: el costo baja de O(rondas · n² · |alfabeto|) a O(n² · |alfabeto|).

Comprobado sobre 3 000 AFDs generados al azar: la particion que devuelve el
metodo nuevo es identica, bloque por bloque, a la del metodo anterior y a la de
`agrupacion`.

| caso | AFD | antes | ahora |
|---|---|---|---|
| `'a'*300` | 301 | 1.45 s | 0.02 s |
| `'a'*2000` | 2 001 | 740.53 s | 1.27 s |
| `(a\|b)*a` + `(a\|b)`×12 | 8 193 | 108.03 s | 43.12 s |

**Hasta donde llega, y por que.** El metodo de tabla de pares es cuadratico por
definicion: la tabla tiene C(n,2) celdas, y en un AFD de 8 193 estados donde
casi ningun par es equivalente hay que marcar 33 millones de pares. Ningun
arreglo de implementacion cambia eso; el refinamiento de particiones es
O(n log n) porque no construye la tabla. La mejora de 740 s a 1.3 s es el caso
de muchas rondas, que era el defecto real. La de 108 s a 43 s es solo la
constante, porque ahi el cuadratico es intrinseco.

Por eso `app.py` ahora compara los dos metodos solo por debajo de
`TOPE_COMPARAR = 600` estados (0.1 s), y por encima minimiza solo por
agrupacion y lo dice en la respuesta. El campo `coinciden` viaja como `null`
cuando no se comparo, que **no** es lo mismo que `false`; el visor distingue
los tres casos y muestra "no se compararon los dos metodos" en vez de una
alarma falsa. `main.py` los sigue comparando siempre: en la linea de comandos
la espera se tolera y es donde se demuestra que los dos metodos coinciden.

| expresion | AFD | `/api/procesar` antes | ahora |
|---|---|---|---|
| `(a\|b)*a` + `(a\|b)`×8 | 513 | 0.29 s | 0.20 s (compara los dos metodos) |
| `(a\|b)*a` + `(a\|b)`×10 | 2 049 | 3.99 s | 0.16 s |
| `(a\|b)*a` + `(a\|b)`×11 | 4 097 | 19.29 s | 0.25 s |
| `(a\|b)*a` + `(a\|b)`×12 | 8 193 | 113.51 s | **0.34 s** |

La prueba de escalabilidad de `pruebas_adversarias.py` cambio en consecuencia.
Antes exigia que los dos metodos tardaran parecido, que es una expectativa
equivocada: nunca van a hacerlo, y esa prueba habria seguido en rojo para
siempre. Ahora mide lo que si es exigible, que myhill crezca como n² y no como
n³: con `'a'*n` para n = 100, 200, 400, al duplicar n el tiempo se multiplica
por 3.9 (cuadratico). Inyectando el algoritmo anterior da 8.1 y la prueba
falla, asi que detecta la regresion en vez de limitarse a estar verde.

---

## Cumplimiento del enunciado (`Proyecto_1-1.pdf`)

Verificado corriendo el programa contra un archivo con una expresion regular por
linea, como lo dara el calificador.

| Lo que pide el enunciado | Estado | Evidencia |
|---|---|---|
| Repositorio de GitHub | Cumple | `origin` apunta a `github.com/fatupopzz/proyecto1-teoria` |
| Entrada: una expresion regular `r` y una cadena `w` | Cumple | Modo interactivo pide las dos; modo archivo pide `w` una vez y la aplica a todas las lineas |
| Simbolo para epsilon designado por el programador, razonable, que no sea letra ni numero | Cumple | `EPSILON = 'ε'` (U+03B5) en `src/shunting_yard.py:18`. El programa lo anuncia al arrancar: `Simbolo designado para epsilon: 'ε'` |
| 1. Infix a postfix | Cumple, 3 pts | `[1] Postfix (Shunting Yard): bb\|*a.b.b.ab\|*.` para `(b\|b)*abb(a\|b)*` |
| 2. AFN con Thompson desde postfix | Cumple, 3 pts | `[2] AFN construido con Thompson: 22 estados` |
| 3. AFN a AFD por subconjuntos | Cumple, 3 pts | `[3] AFD por construccion de subconjuntos: 7 estados`, con la correspondencia a los subconjuntos del AFN |
| 4. Minimizacion del AFD | Cumple, 3 pts | `[4] AFD minimizado: 7 -> 4 estados`. Implementa **dos** metodos y comprueba que dan el mismo resultado |
| 5. Verificar `w ∈ L(r)` con el AFN y los AFDs | Cumple, 3 pts | Simula los tres y los tres coinciden |
| Salida: una imagen del grafo para el AFN y para los dos AFDs | Cumple | 3 PNG por expresion (`NN_afn.png`, `NN_afd.png`, `NN_afd_min.png`). Con 5 expresiones salen 15 archivos |
| La imagen muestra estado inicial, los demas estados, el de aceptacion y las transiciones con sus simbolos | Cumple | Flecha desde la nada al inicial, doble circulo en los de aceptacion, cada arista rotulada con su simbolo, epsilon en gris |
| Respuesta con "si" en caso de aceptacion y "no" en caso contrario | Cumple | `main.py:41` devuelve literalmente `"sí"` / `"no"` |
| Leer un archivo de texto y procesar cada linea | Cumple, con una salvedad | Ver abajo |

El ejemplo exacto del enunciado (`r = (b|b)*abb(a|b)*`, `w = babbaaaa`) da `sí`
en los tres automatas.

### La salvedad: dos convenciones que el enunciado no pide

El enunciado dice que **cada linea del archivo contiene una expresion regular**,
y que el archivo lo trae el calificador. `main.py:173-184` agrega dos
convenciones propias:

| Linea en el archivo | Lo que hace el programa |
|---|---|
| `#\|a` | La **ignora en silencio**: cree que es un comentario |
| `a<TAB>b` | La parte en dos: procesa la expresion `a` con la cadena `b` |

Las dos son expresiones regulares validas para este mismo tokenizador (`#` y el
tabulador se aceptan como simbolos del alfabeto en cualquier otra posicion:
`a#b` se procesa bien, con `#` en el alfabeto). O sea que el programa acepta `#`
como simbolo en medio de una expresion pero no al principio de una linea, lo
cual es inconsistente.

Probado con un archivo de 4 lineas (`#|a`, `a#b`, `a<TAB>b`, `(a|b)*`): el
programa anuncia "Procesando 3 expresiones" y evalua `a#b`, `a` con `w=b`, y
`(a|b)*`.

**Riesgo real: bajo.** Nadie escribe una expresion regular que empiece con `#` o
que lleve un tabulador adentro. Y las dos convenciones estan documentadas en el
README. Pero si el calificador pregunta "que pasa si mi archivo trae esto",
conviene tener la respuesta lista en vez de descubrirlo en vivo.

**Cerrado.** `main.py` ahora avisa de cada linea afectada, con su numero:

```
Procesando 3 expresiones de 'raro.txt'
  [AVISO] linea 1 ignorada por empezar con '#': #|a
  [AVISO] linea 5 ignorada por empezar con '#': # solo un comentario
  [AVISO] linea 3 trae un tabulador: se toma r = a  con su propia w = b
```

Las convenciones se quedan, porque estan documentadas en el README y son utiles
para el archivo de pruebas propio. Lo que cambia es que ya nada pasa en
silencio, que era lo unico que de verdad hacia dano. Un archivo con el formato
del enunciado (una expresion por linea, sin comentarios ni tabuladores) no
imprime ningun aviso.

---

## Resumen ejecutivo (auditoria original)

**El núcleo algorítmico está limpio.** No encontré ni un solo caso en el que el
AFN, el AFD o cualquiera de los dos AFDs mínimos discrepen de `re.fullmatch` de
Python. Tampoco encontré violaciones de los invariantes de Thompson, ni AFDs
mínimos con estados redundantes, ni expresiones equivalentes que produzcan
mínimos distintos. Los cinco puntos del enunciado (Shunting Yard, Thompson,
subconjuntos, minimización por dos métodos, simulación) resistieron todo lo que
les tiré.

**Lo que sí falla está en la periferia**: generación de imágenes, lectura del
archivo de entrada, los endpoints del visor web y la escalabilidad del método de
Myhill-Nerode. Nueve hallazgos, ninguno de ellos un error de teoría.

| # | Hallazgo | Dónde | Gravedad en defensa oral |
|---|----------|-------|--------------------------|
| 1 | Un símbolo `\` literal rompe la generación de PNG en silencio | `src/visualizacion.py` | **Alta** |
| 2 | Ese mismo símbolo tumba el visor con HTTP 500 | `app.py` | **Alta** |
| 3 | El visor se cuelga minutos con AFDs de más de ~100 estados | `app.py` | **Alta** |
| 4 | BOM UTF-8 entra al alfabeto como símbolo | `main.py:135` | **Media-alta** |
| 5 | `myhill` es ~1200× más lento que `agrupacion` y siempre se corren los dos | `src/minimizacion.py` | **Media** |
| 6 | Un tabulador al final de la línea cambia `w` a la cadena vacía | `main.py:145` | **Media** |
| 7 | `output/` no se limpia: quedan PNG de corridas anteriores | `main.py:111` | **Media** |
| 8 | El docstring dice que epsilon es `'e'`; es `'ε'` | `src/shunting_yard.py:13` | **Media** |
| 9 | Archivo binario o directorio como entrada: traceback crudo | `main.py:131-136` | Baja |

Más abajo hay una lista de detalles menores y, al final, el inventario completo
de lo que ataqué y lo que quedó sin atacar.

---

## 1. Un símbolo `\` literal rompe la generación de PNG, en silencio

**Entrada mínima**

```
\\
```

Es decir, la expresión regular que denota el lenguaje `{ \ }`: un único símbolo
que es la barra invertida, escapada. **Esto ya está pasando en tu repositorio**:
la expresión número 25 de `pruebas.txt` es `a\\b`, y en `output/` hay `25_afn.dot`,
`25_afd.dot` y `25_afd_min.dot` en vez de los `.png`, más tres archivos sin
extensión (`25_afn`, `25_afd`, `25_afd_min`) que Graphviz dejó a medias.

**Qué se esperaba**: `output/25_afn.png` etc., archivos PNG válidos.

**Qué pasó**: el DOT generado sale con una cadena entre comillas sin cerrar:

```dot
2 -> 3 [label="\" color=black fontcolor=black]
```

`dot` falla con `syntax error in line 16 scanning a quoted string
(missing endquote?)`. `_renderizar()` atrapa la excepción, escribe el `.dot` y
lo devuelve como si fuera el archivo bueno. `main.py` lo imprime tal cual bajo
el encabezado `[6] Imagenes generadas:`.

**Causa**: `src/visualizacion.py:74` (aristas del AFN), `:100` (aristas del AFD)
y `:88` (etiquetas de nodo) meten el símbolo crudo en `label=` sin duplicar la
barra invertida. El módulo `graphviz` entrecomilla pero no escapa `\`. El
enmascaramiento lo hace `src/visualizacion.py:133`, el `except Exception:` que
convierte un fallo de render en un `.dot` silencioso.

**Gravedad: alta.** El calificador puede pedir "generá los autómatas de este
archivo" y todo se ve verde en consola mientras tres imágenes no existen. Peor:
el caso ya está en tu propio `pruebas.txt`, así que si él corre lo que vos le
entregaste, lo encuentra sin buscarlo.

---

## 2. El mismo símbolo tumba el visor web con HTTP 500

**Entrada mínima**: escribir `\\` en la caja de expresión regular del visor.

**Qué se esperaba**: un mensaje de error en la interfaz, o el grafo dibujado.

**Qué pasó**: excepción no capturada, HTTP 500.

```
CalledProcessError: Command '[PosixPath('dot'), '-Kdot', '-Tsvg']'
returned non-zero exit status 1
```

**Causa**: `app.py:88-97`. El `try/except` de `/api/procesar` cubre las líneas
76-80 (validación y construcción de autómatas) pero el renderizado a SVG ocurre
después, dentro del `jsonify(...)`, vía `_empaquetar_afn` / `_empaquetar_afd`.
`src/visualizacion.py:121` (`a_svg`) no atrapa nada, a diferencia de
`_renderizar`.

**Gravedad: alta.** Es el modo demo. Un 500 en vivo, con el stack trace de Flask
en pantalla porque `app.run(debug=True)`, es lo peor que puede pasar en una
defensa.

---

## 3. El visor se cuelga varios minutos con AFDs medianos

**Entrada mínima**

```
(a|b)*a(a|b)(a|b)(a|b)(a|b)(a|b)(a|b)(a|b)
```

42 caracteres. Es el ejemplo de libro de texto "el k-ésimo símbolo desde el
final es una `a`", y su AFD tiene 2^k estados por construcción.

**Qué se esperaba**: respuesta interactiva, o un aviso de que el autómata es
demasiado grande para dibujarlo.

**Qué pasó**, medido sobre `/api/procesar`:

| expresión | caracteres | estados AFD | tiempo | JSON |
|---|---|---|---|---|
| `(a\|b)*a` + `(a\|b)`×4 | 27 | 33 | 0.4 s | 182 KB |
| `(a\|b)*a` + `(a\|b)`×6 | 37 | 129 | 4.6 s | 1.2 MB |
| `(a\|b)*a` + `(a\|b)`×7 | 42 | 257 | **111 s** | 3.7 MB |
| `(a\|b)*a` + `(a\|b)`×8 | 47 | 513 | > 120 s | (sin medir) |

El costo dominante no son los algoritmos (la construcción de subconjuntos tarda
0.03 s para 257 estados) sino el **layout de Graphviz**: un solo SVG del AFD de
257 estados toma 58.7 s, y `/api/procesar` renderiza tres.

Encima, `traza_myhill` devuelve la tabla de pares completa: 32 896 pares y
32 895 celdas marcadas para ese AFD, y `static/visor.js:270-310` crea un `<td>`
del DOM por cada una, con un `m.estados.indexOf()` adentro del doble bucle
(O(n³)). El navegador también se congela.

**Causa**: no hay ninguna guardia de tamaño. `app.py:88-103` renderiza siempre
los tres autómatas y siempre manda la tabla de pares completa.

**Gravedad: alta.** No es un bug de teoría, pero es exactamente el tipo de
expresión que un calificador escribe para "ver si aguanta". El resultado visible
es una página congelada.

---

## 4. El BOM de UTF-8 se convierte en un símbolo del alfabeto

**Entrada mínima**: un archivo `.txt` guardado en UTF-8 **con BOM** (lo que hace
el Bloc de notas de Windows por defecto) cuya primera línea es `a|b`.

**Qué se esperaba**: `alfabeto = ['a', 'b']`, AFN de 6 estados.

**Qué pasó**:

```
EXPRESION 1: ﻿a|b
[1] Postfix (Shunting Yard): ﻿a.b|
[2] AFN construido con Thompson: 8 estados, alfabeto = ['a', 'b', '﻿']
```

El BOM entra como un símbolo más. La expresión pasa de ser `a|b` a ser
`(BOM·a)|b`: la cadena `a` deja de pertenecer al lenguaje. **No hay ningún
mensaje de error**, y solo afecta a la primera línea del archivo.

**Causa**: `main.py:135`, `open(ruta, encoding='utf-8')`. El códec `utf-8` no
consume el BOM; `utf-8-sig` sí.

**Gravedad: media-alta.** Si el calificador te pasa su propio archivo de
prueba hecho en Windows, la primera expresión da un resultado incorrecto y no
tenés cómo darte cuenta en el momento. Es un fallo silencioso, que es la peor
clase.

---

## 5. El método de Myhill-Nerode no escala, y siempre se corren los dos

**Entrada mínima**: cualquier expresión cuyo AFD tenga unos cientos de estados.

**Qué se esperaba**: los dos métodos calculan la misma partición, así que
deberían tardar tiempos del mismo orden.

**Qué pasó** (medido con `--solo escalabilidad`):

| expresión | estados AFD | `agrupacion` | `myhill` | factor |
|---|---|---|---|---|
| `a`×300 | 301 | 0.06 s | 1.45 s | 24× |
| `(a\|b)*a(a\|b)`×10 | 2049 | 0.02 s | 3.57 s | 178× |
| `(a\|b)*a(a\|b)`×12 | 8193 | 0.09 s | 110.6 s | **1229×** |
| `a`×2000 | 2001 | 2.37 s | 740.5 s | 312× |

**Causa**: `src/minimizacion.py:119-134`. El punto fijo rehace la pasada completa
sobre los C(n,2) pares en cada ronda; con una cadena larga hay O(n) rondas, así
que el costo es O(n³·|Σ|). `_refinar` (líneas 60-90) hace agrupamiento por firma
y termina en pocas rondas.

Esto se hereda hacia arriba porque `verificar_equivalencia()`
(`src/minimizacion.py:300-301`) corre **los dos** métodos, y tanto `main.py:71`
como `app.py:80` la llaman siempre, incluso cuando solo se necesita un AFD
mínimo.

**Gravedad: media.** No es incorrecto, es lento. Pero explica por qué el visor
se vuelve inusable antes de lo que debería, y es una pregunta fácil de hacer:
"¿por qué implementaste dos métodos si siempre corrés los dos?".

---

## 6. Un tabulador al final de la línea cambia `w` a la cadena vacía

**Entrada mínima**: un archivo con dos líneas idénticas, salvo que la segunda
termina en un tabulador invisible:

```
a*
a*<TAB>
```

Corriendo `python main.py archivo.txt aaa`:

```
EXPRESION 1: a*    CADENA w : aaa    >>> 'aaa' SÍ pertenece
EXPRESION 2: a*    CADENA w : (vacia)  >>> '' SÍ pertenece
```

**Qué se esperaba**: las dos líneas evaluadas con `w = "aaa"`. El README dice:
"Las líneas sin cadena usan la que se pasó por la línea de comandos", y una
línea que termina en tabulador no trae cadena.

**Qué pasó**: `main.py:145-147` decide por `if '\t' in linea`, y luego
`propia = ''`. Como `'' is not None`, `main.py:160` usa la cadena vacía.

**Gravedad: media.** Un tabulador al final es invisible en cualquier editor y
lo introduce cualquier copiar-pegar. El síntoma es una fila de la tabla que dice
"no" cuando todas las demás dicen "sí", sin explicación visible.

**Comentario relacionado**: la misma línea 143 numera las expresiones por su
posición entre las líneas válidas, no por su número de línea en el archivo. El
README línea 54 afirma lo contrario ("`NN` es el número de línea de la
expresión"). Con `expresiones.txt`, `01_afn.png` corresponde a la línea 2.

---

## 7. `output/` no se limpia entre corridas

**Reproducción**: correr `main.py` con un archivo de 5 expresiones y después con
uno de 1. Quedan en `output/` los doce PNG de la corrida anterior
(`02_*` a `05_*`) mezclados con el único de la corrida actual.

**Causa**: `main.py:111` hace `os.makedirs(carpeta, exist_ok=True)` pero nunca
borra. Los nombres solo dependen del índice.

**Gravedad: media.** En una defensa, mostrar `output/` con imágenes de una
corrida vieja como si fueran del ejemplo que se acaba de correr es un problema
de credibilidad, no de código.

---

## 8. El docstring de `shunting_yard.py` dice que epsilon es `'e'`

**Entrada mínima**: leer `src/shunting_yard.py:13`.

```python
El simbolo designado para epsilon es 'e' (EPSILON).
```

Dos líneas más abajo, `EPSILON = 'ε'`. El README (línea 134) está bien y dice
`ε` (U+03B5); es solo el docstring del módulo el que miente.

**Qué pasa si alguien le cree**: escribe `(a|e)b` esperando `a?b`, y obtiene el
lenguaje `{ab, eb}` sin ningún error.

**Gravedad: media.** El calificador abre primero el módulo del punto 1 del
enunciado y lo primero que lee es una afirmación falsa sobre el símbolo
designado, que es justo lo que el enunciado pide declarar explícitamente.

---

## 9. Archivo binario o directorio como argumento: traceback crudo

**Entradas mínimas**

```bash
python main.py /bin/ls abc      # archivo binario
python main.py src abc          # un directorio
```

**Qué se esperaba**: el mismo trato que un archivo inexistente, que sí está
manejado (`main.py:131-133`, mensaje y `exit 1`).

**Qué pasó**:

```
UnicodeDecodeError: 'utf-8' codec can't decode byte 0xca in position 0
IsADirectoryError: [Errno 21] Is a directory: 'src'
```

**Causa**: `main.py:135-136`. `os.path.exists()` devuelve `True` para un
directorio, y no hay `try` alrededor del `open`.

**Gravedad: baja.** Poco probable que alguien lo haga a propósito, pero un
traceback de Python es feo en vivo.

---

## Hallazgos menores

**M1. Los endpoints devuelven 500 con JSON no textual.**
`POST /api/procesar` con `{"regex": 123}` → `AttributeError: 'int' object has no
attribute 'strip'`; con `{"cadena": 5}` → `TypeError: 'int' object is not
iterable`. Causa: `app.py:69-70`, que asume que los campos son strings. Solo se
alcanza con un cliente hecho a mano, no desde el visor. `/api/lote` sí lo maneja
porque tiene un `except Exception` por fila (`app.py:138`).

**M2. Los espacios en blanco se descartan silenciosamente dentro de la regex.**
`src/shunting_yard.py:69-71` ignora todo `isspace()`, así que `a b` es
exactamente `ab`. El README línea 136 dice "Cualquier otro carácter que no sea
operador se trata como símbolo del alfabeto", lo cual contradice esto. Un
espacio solo se puede usar como símbolo escapándolo: `a\ b`.

**M3. El carácter `ε` no se puede usar como símbolo del alfabeto.**
`\ε` sigue produciendo epsilon, porque `tokenizar` (`src/shunting_yard.py:65`)
guarda el carácter escapado sin marcarlo como literal, y Thompson compara por
valor. Consecuencia aceptable de la decisión de diseño, pero conviene saberla
antes de que la pregunten.

**M4. El postfix impreso pierde la información de escape.**
`a\**` (una `a` seguida de cero o más asteriscos literales) se imprime como
`a**.`, que leído como postfix es otra cosa. El vector de tokens interno es
correcto; solo la representación en texto es ambigua (`src/shunting_yard.py:161`).

**M5. Doble encabezado al fallar una línea del archivo.**
Cuando una expresión es inválida, `procesar()` ya imprimió `EXPRESION n:` antes
de que `validar()` lance, y el `except` de `main.py:162-163` lo imprime otra vez.

**M6. `maxRonda()` en el visor mira `myhill` pero lee `agrupacion`.**
`static/visor.js:232-234`. Hoy no rompe porque las dos trazas devuelven `None`
en el mismo caso (alfabeto vacío), pero la guardia no cubre lo que usa.

---

## Qué ataqué y qué encontré (o no)

### 1. Oráculo independiente contra `re.fullmatch`: sin hallazgos

Generé expresiones al azar como árboles y las rendericé dos veces: una con la
sintaxis del proyecto y otra con la de `re` (la única diferencia real es epsilon,
que en `re` se emite como `(?:)` para que siga siendo un átomo). Al venir del
mismo árbol, las dos denotan el mismo lenguaje por construcción.

- Alfabetos de 2 a 5 símbolos, profundidad de árbol hasta 5.
- Una de cada cuatro expresiones usa alfabetos formados por operadores
  (`*`, `|`, `(`, `)`, `?`, `+`, `.`, `\`) para forzar el camino del escape.
- Cadenas de prueba: todas las de largo ≤ 4 sobre el alfabeto, más 40 aleatorias
  de largo 5 a 14 por expresión.
- Se comparan los cuatro autómatas contra `re`: AFN, AFD, mínimo por
  `agrupacion` y mínimo por `myhill`.

**13 023 212 comparaciones sobre 24 000 expresiones, cero discrepancias.** Ni una.

Un detalle del método: en 8 de esas 24 000 expresiones hubo que acortar las
cadenas de prueba porque el que se ahogaba era `re`, no el proyecto. El motor de
Python es de backtracking y un patrón como `(?:(?:(?:)|c)*)+` dentro de otra
estrella tarda tiempo exponencial en decidir que una cadena **no** empareja
(`((((ε|c)*)+)+)*` contra `ccb` toma 1.1 s). El proyecto, que simula autómatas,
contesta en microsegundos. `pruebas_adversarias.py` lo maneja con un corte por
tiempo que nunca puede tapar un hallazgo, porque salta dentro de
`re.fullmatch()`, antes de comparar nada, y reporta cuántas expresiones acortó.

### 2. Invariantes estructurales: sin hallazgos

Verificado sobre cada expresión generada:

- El AFN de Thompson tiene **exactamente un** estado de aceptación.
- Ese estado **no tiene ninguna transición saliente**.
- El conteo de estados es exactamente `2 × (símbolos + unarios + uniones)`, y
  eso está siempre `≤ 2n` con `n` el largo de la expresión.
- `ε` nunca aparece en el alfabeto del AFN, del AFD ni de los dos mínimos.
- El AFD de subconjuntos **no tiene estados inalcanzables**; el mínimo tampoco.
- `agrupacion` y `myhill` producen AFDs **idénticos carácter por carácter**
  (mismos estados, mismo inicial, misma aceptación, mismas transiciones).
- Minimizar dos veces no cambia nada, incluso **cruzando los métodos**:
  `myhill(agrupacion(A)) == agrupacion(A)`.
- Parentizar toda la expresión de forma explícita da el mismo AFD mínimo que la
  versión con precedencia implícita, lo que prueba que el Shunting Yard agrupa
  bien.
- La tabla de pares que dibuja el visor (`src/traza_min.py`, que es código
  aparte) coincide par por par con la partición que calcula
  `src/minimizacion.py`.

### 3. Minimalidad real por fuerza bruta: sin hallazgos

Sobre 1 957 AFDs mínimos de hasta 6 estados: para **cada par** de estados se buscó
una cadena testigo que los distinga, probando todas las cadenas de largo hasta
`2 × |estados|`. Nunca quedó un par sin distinguir. Y desde cada estado se
verificó que exista camino a un estado de aceptación: no hay estados muertos.

### 4. Propiedades algebraicas: sin hallazgos

Doce familias fijas de expresiones equivalentes, incluidas las que pediste:

- `(a|b)*` ≡ `(a*b*)*` ≡ `(b|a)*` ≡ `((a|b)*)*` ≡ `(a*|b*)*`
- `a(ba)*` ≡ `(ab)*a`
- `(a|ε)` ≡ `a?` ≡ `ε|a`
- `a+` ≡ `aa*` ≡ `a*a`
- `a*` ≡ `(a*)*` ≡ `(a+)?` ≡ `(a?)*` ≡ `ε|a+` ≡ `a*a*`
- `(a|b)(a|b)` ≡ `aa|ab|ba|bb`
- `(ab)+` ≡ `ab(ab)*` ≡ `a(ba)*b`

Más 4 860 pares generados automáticamente aplicando identidades del álgebra
de expresiones regulares (conmutatividad de `|`, `(x*)* = x*`, `x+ = xx*`,
`x? = x|ε`, absorción de `ε` en la concatenación) en un punto al azar del árbol.
Antes de comparar los AFDs, cada par se confirma con `re.fullmatch` para
descartar que la reescritura haya cambiado el lenguaje.

**Todos los pares equivalentes produjeron el mismo AFD mínimo, transición por
transición.** Esto es el resultado más fuerte del reporte: la numeración canónica
por BFS de `src/minimizacion.py:223-251` funciona, y el mínimo es efectivamente
único e independiente de cómo se escribió la expresión. Era, como dijiste, el
ataque con más probabilidad de encontrar un bug real, y no lo encontró.

### 5. Basura: sin hallazgos

300 000 cadenas al azar sobre un alfabeto que incluye operadores,
paréntesis, barras invertidas, espacios, saltos de línea, `#`, comillas, llaves,
ángulos y caracteres de puntuación, de largo 0 a 14, más 32 entradas degeneradas
escritas a mano (`''`, `'('`, `'*'`, `'a\\'`, `'((a)'`, `'a||b'`, `'()*'`,
`'\\\\'`, `'a?*+'`, …).

**Ninguna lanzó nada distinto de `ValueError`.** Ni `TypeError`, ni `KeyError`,
ni `IndexError`, ni `RecursionError`. `validar()` (`src/shunting_yard.py:165-185`)
simula exactamente la aritmética de pila que después hace `construir_afn`, así
que los dos aceptan y rechazan el mismo conjunto de expresiones. Es la parte
mejor blindada del proyecto.

### 6. Lo que NO ataqué

Para que sepas dónde no tenés cobertura:

- **`static/visor.js` en un navegador real.** Lo leí, pero no lo ejecuté. Los
  hallazgos 3 y M6 salen de leerlo, no de correrlo. No probé el zoom, el
  arrastre, la cinta, ni el reproductor de rondas.
- **`templates/index.html` y `static/estilo.css`.** Sin tocar.
- **Concurrencia.** No probé dos peticiones simultáneas al visor. `app.py` no
  tiene estado global mutable, así que no espero problemas, pero no está
  verificado.
- **Contenido visual de los PNG.** Verifiqué que el archivo sea un PNG válido
  (bytes mágicos), no que el dibujo sea correcto. Un grafo con una arista mal
  puesta pasaría esta prueba.
- **`ESTUDIO.md`.** No verifiqué línea por línea sus afirmaciones; revisé las
  que tocan invariantes (la cota `2n`, la unicidad del mínimo) y son correctas.
- **Expresiones de 10 000 caracteres.** No las corrí hasta el final. Por la
  medición de `a`×2000 (740 s en `myhill`) y el crecimiento cúbico, `a`×10000
  tardaría del orden de horas. El endpoint `/api/procesar` simplemente nunca
  contestaría. Esto es una extrapolación, no una medición.
- **Fallos de entorno**: falta del binario `dot`, `output/` sin permiso de
  escritura, disco lleno.

---

## Recomendación de prioridad

Si solo vas a arreglar tres cosas antes de la defensa:

1. **Hallazgo 1 y 2** (el símbolo `\`): son el mismo arreglo, escapar la barra
   invertida en las etiquetas de `src/visualizacion.py`, más mover la llamada a
   `a_svg` dentro del `try` de `app.py`. El caso ya está en tu `pruebas.txt`.
2. **Hallazgo 4** (BOM): cambiar `encoding='utf-8'` por `encoding='utf-8-sig'`
   en `main.py:135`. Una palabra.
3. **Hallazgo 3** (el visor colgado): un tope de estados antes de renderizar,
   con un mensaje del tipo "el AFD tiene 257 estados, demasiados para dibujar".

Los tres son de periferia. Ninguno toca los algoritmos, y por eso ninguno te
cuesta puntos de teoría si te preguntan por ellos con honestidad.

**No cambié ninguna línea del código del proyecto.** `pruebas_adversarias.py` y
este archivo son lo único nuevo.
