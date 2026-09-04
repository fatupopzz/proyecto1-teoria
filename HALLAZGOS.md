# HALLAZGOS

Reporte de las pruebas adversarias sobre el Proyecto 1 (regex → AFN → AFD →
AFD mínimo → simulación).

Todo lo de aquí se reproduce con:

```bash
python pruebas_adversarias.py --semilla 20250904
```

La corrida completa tarda unos 40 segundos y reporta 19 fallas, que son los 9
hallazgos numerados más abajo (varios se detectan en más de un caso). Cada bloque
se puede correr suelto con `--solo <bloque>` y escalar con `--iteraciones N`;
la semilla siempre se imprime, y pasarla de vuelta reproduce exactamente la misma
corrida.

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

## Resumen ejecutivo

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
