# Guía de estudio — Proyecto 1

Para defender el código, no para escribirlo. Todo lo que dice acá se puede
verificar corriendo el programa.

---

## Método

No leas el código de arriba a abajo. Hacé esto:

1. **Trazá a mano** una expresión chica (`ab*`, seis estados) en papel: postfix,
   AFN, AFD, mínimo.
2. **Verificá** con `python3 main.py` y compará contra lo que escribiste.
3. Donde no coincida, ahí está el hueco. Andá al módulo específico.

Trazar a mano es lo único que revela si entendiste o si estás reconociendo el
código de memoria. Al final de esta guía hay cinco ejercicios con las respuestas.

---

## El mapa en 30 segundos

```
regex (str)
  │  tokenizar()          → lista de Tokens
  │  insertar_concatenacion() → mete los '.' implícitos
  │  a_postfix()          → Shunting Yard
postfix (lista de Tokens)
  │  construir_afn()      → Thompson, pila de fragmentos
AFN (estados int, transiciones dict[(estado,símbolo)] → set)
  │  construir_afd()      → subconjuntos, e-closure + move
AFD (transiciones dict[(estado,símbolo)] → int)
  │  minimizar()          → refinamiento de particiones
AFD mínimo
  │  simular_afn / simular_afd
sí | no
```

Un dato para tener a mano: cada etapa **reduce**. AFN grande y ε-lleno → AFD sin
ε pero con estados redundantes → mínimo. Los tres reconocen el mismo lenguaje;
eso es lo que verifica `tests.py`.

---

## Módulo por módulo

### `shunting_yard.py`

**Qué hace.** Convierte `(b|b)*abb(a|b)*` en `bb|*a.b.b.ab|*.`

**Las tres funciones, en orden:**

| Función | Qué resuelve |
|---|---|
| `tokenizar` | separa caracteres y maneja el escape `\` |
| `insertar_concatenacion` | vuelve explícito el `.` que la regex omite |
| `a_postfix` | el algoritmo en sí (pila + salida) |

**La línea que importa** — el desapilado en `a_postfix`:

```python
if token.valor in UNARIOS:
    if PRECEDENCIA[tope.valor] > PRECEDENCIA[token.valor]:   # estricto
else:
    if PRECEDENCIA[tope.valor] >= PRECEDENCIA[token.valor]:  # o igual
```

`|` y `.` asocian a la izquierda → un operador de **igual** precedencia debe
desapilarse (`>=`). Los unarios asocian a la derecha → con igual precedencia
**no** deben desapilarse entre sí (`>`). Se ve en `a**`.

**Regla de `insertar_concatenacion`:** se mete un `.` entre un token que *cierra*
(símbolo, `)`, o unario) y uno que *abre* (símbolo o `(`). Memorizá esas dos
listas; es la pregunta más probable de este módulo.

**Si cambiás algo:** poner `>=` para unarios rompe `a**`. Sacar
`insertar_concatenacion` deja `abb` como tres símbolos sueltos y Thompson explota
con "expresión mal formada".

---

### `thompson.py`

**El invariante.** Cada `_Fragmento` tiene **un** inicio sin transiciones de
entrada y **un** final sin transiciones de salida. Por eso cualquier par de
fragmentos se pega sin ambigüedad. Si te preguntan "¿por qué Thompson funciona?",
la respuesta es esta frase.

**Las cinco operaciones:**

| Método | Estados nuevos | Cómo |
|---|---|---|
| `simbolo` | 2 | `i --c--> f` |
| `concatenacion` | **0** | ε de la aceptación de A al inicio de B |
| `union` | 2 | nuevo `i` con ε a ambos; ambos con ε al nuevo `f` |
| `kleene` | 2 | ε: i→frag, i→f, frag_acep→frag_inicio, frag_acep→f |
| `positiva` | 2 | igual que kleene **menos** el ε de i→f |
| `opcional` | 2 | ε: i→frag, i→f, frag_acep→f (sin el de regreso) |

**Contá estados con esto.** `(b|b)*abb(a|b)*`: 7 símbolos × 2 = 14, más 2 por cada
`|` y cada `*` (son 4) = **22**. La concatenación no aporta. Cota general: ≤ 2n.

**Los tres se distinguen por qué ε llevan:**

- `*` = el de salto (i→f) **y** el de regreso → cero o más
- `+` = solo el de regreso → una o más
- `?` = solo el de salto → cero o una

Si te preguntan por `+`, contestá con la cadena vacía: `a*` la acepta, `a+` no, y
la única diferencia en el código es ese ε de salto.

---

### `subconjuntos.py`

**La idea en una frase.** Un estado del AFD es el conjunto de estados donde el
AFN *podría* estar a la vez; se determiniza cargando la incertidumbre en el
nombre del estado.

**Las dos operaciones:**

- `cerradura_epsilon(afn, T)` — a dónde llego gratis desde `T`. Pila + set de
  visitados, o sea un DFS.
- `mover(afn, T, a)` — a dónde llego consumiendo `a`.

**La fórmula:** cada estado nuevo es `e-closure(move(T, a))`. **En ese orden.**
El inicial es la excepción: `e-closure({inicio})` sin consumir nada.

**Dos líneas para tener presentes:**

```python
if not destino:
    continue            # el estado muerto queda IMPLÍCITO, no se guarda
```

```python
aceptacion = {subconjuntos[sub] for sub in orden if sub & afn.aceptacion}
```

Esa intersección es la regla de aceptación: **basta con que el subconjunto
contenga al menos un estado de aceptación del AFN**. Como Thompson deja un solo
estado de aceptación, en la práctica es "¿está el último adentro?".

**El diccionario `etiquetas`** guarda a qué subconjunto corresponde cada estado.
No es parte del algoritmo — es trazabilidad, y es lo que hace demostrable que el
AFD sí salió del AFN.

---

### `minimizacion.py`

El módulo más largo y el que más preguntas aguanta.

**Hay dos métodos implementados, y calculan lo mismo.** Ambos computan la
equivalencia de Myhill-Nerode sobre los estados del AFD: *dos estados son
equivalentes si ninguna cadena los distingue*. Cambia cómo se calcula.

| Método | Cómo | Función |
|---|---|---|
| `agrupacion` | Refinamiento de particiones (Moore/Hopcroft): parte de dos bloques y los va separando | `_refinar` |
| `myhill` | Llenado de tabla de pares: marca los pares distinguibles y al final agrupa los que quedaron sin marcar | `_particion_por_myhill` |

**Van en direcciones opuestas.** La agrupación empieza suponiendo que todo lo
que está en un bloque es equivalente y va *separando*. La tabla empieza sin
suponer nada y va *marcando* lo que se demuestra distinguible. Llegan a la misma
partición desde lados contrarios.

**La tabla de pares, en dos reglas:**

```
base : {p, q} se marca si uno acepta y el otro no
       (los distingue la cadena vacía)
paso : {p, q} se marca si existe un símbolo a tal que {δ(p,a), δ(q,a)}
       ya está marcado
```

La segunda regla es la clave y conviene poder justificarla: si la cadena `w`
distingue a los destinos, entonces `a·w` distingue a `p` y `q`. Se itera hasta
que una pasada no marque nada nuevo. Los pares que sobrevivieron sin marcar son
equivalentes, y su cierre transitivo (el union-find con `raiz`) da las clases.

**Por qué dan el mismo resultado.** El teorema de Myhill-Nerode dice que el AFD
mínimo es único salvo renombrar estados. `verificar_equivalencia()` lo comprueba
sobre cada AFD concreto, y `tests.py` lo corre en los 30 casos. Para que la
comparación sea estructural y no solo de tamaño, los bloques se numeran por
**BFS desde el inicial en orden de alfabeto** — una numeración canónica que no
depende de cómo cada método armó la partición.

Después de calcular la partición, las dos fases restantes son comunes.

**`_completar` — el estado trampa.**

El refinamiento compara estados por su *firma*: a qué bloque van con **cada**
símbolo del alfabeto. Si una transición no existe, la firma queda incompleta y no
hay con qué comparar. El trampa (`TRAMPA = -1`) vuelve total la función de
transición. Es un requisito del algoritmo, no una decisión de diseño.

**`_particion_inicial`** (solo agrupación)**.**

Dos bloques: aceptación y no aceptación. Es la distinción más gruesa posible —
la que hace la cadena vacía. Todo lo demás sale de refinar esto.

**`_refinar` — el corazón de la agrupación.**

```python
firma = tuple(
    pertenece.get(transiciones.get((estado, s)))
    for s in sorted(alfabeto)
)
grupos.setdefault(firma, set()).add(estado)
```

Dos estados del mismo bloque que tengan firmas distintas **no eran
equivalentes** y se separan. Se repite hasta que ninguna pasada cambie nada
(punto fijo). El `sorted(alfabeto)` es para que la firma sea comparable entre
estados, no un detalle estético.

**Por qué termina:** cada pasada solo puede aumentar el número de bloques, y hay
a lo sumo un bloque por estado. O sea, converge.

**`_limpiar` — dos recorridos distintos (común a ambos métodos).**

- **Alcanzables:** DFS hacia adelante desde el inicial.
- **Vivos:** DFS **sobre el grafo inverso** desde los estados de aceptación —
  o sea, estados desde los que todavía se puede llegar a aceptar.

Se conserva la intersección. Por eso desaparece el trampa: es alcanzable pero no
está vivo. Si te preguntan por qué se construyen dos conjuntos y no uno, la
respuesta es que son propiedades distintas: un estado puede ser alcanzable y
estar muerto.

Al final, `renombre` numera los bloques dejando el inicial como 0, y `compacto`
los deja consecutivos.

---

### `simulacion.py` y `pasos.py`

`simular_afn` arrastra un **conjunto** de estados (por eso la traza sale entre
llaves); `simular_afd` arrastra uno solo. Es la misma idea de subconjuntos, pero
calculada al vuelo en vez de por adelantado.

`pasos.py` es lo mismo pero guardando cada paso para el visor web. No agrega
lógica nueva: si preguntan, es presentación, no algoritmo.

---

## Las ocho líneas peligrosas

Lo que un calificador puede señalar y preguntar "¿y esto?".

1. `>` vs `>=` en el desapilado → asociatividad.
2. `concatenacion` no llama a `nuevo_estado` → por eso Thompson es lineal.
3. El ε de salto que `positiva` **no** tiene → la cadena vacía.
4. `if not destino: continue` → el estado muerto es implícito.
5. `sub & afn.aceptacion` → basta un estado de aceptación.
6. `TRAMPA = -1` → la firma necesita función de transición total.
7. El grafo `inverso` en `_limpiar` → alcanzable ≠ vivo.
7b. `if dp == dq: continue` en la tabla de pares → un estado nunca es
    distinguible de sí mismo, así que ese símbolo no aporta nada.
8. `frozenset` como llave de `subconjuntos` → los sets normales no son
   hashables, y necesitamos el conjunto como identidad del estado.

---

## Ejercicios de trazado

Hacelos en papel **antes** de correr nada.

**1.** `ab*` → ¿postfix? ¿estados del AFN, AFD y mínimo?
**2.** `(a|b)a` → ¿cuál es la e-closure del estado inicial del AFN?
**3.** `(ab)*` → ¿cuántos estados tiene el AFN? ¿por qué no ocho?
**4.** `a?b` → el AFD tiene 3 estados y el mínimo también 3. ¿Por qué no se
reduce?
**5.** `(a|b)*abb` → ¿postfix? ¿cuántos estados en cada etapa?

<details>
<summary>Respuestas</summary>

1. `ab*.` — AFN 6, AFD 3, mínimo 2.
2. `{0, 2, 4}` — el 4 es el inicio de la unión, con ε a los dos ramales.
3. Seis: 2 símbolos × 2 = 4, más 2 del `*`. La concatenación no aporta estados.
4. Porque los tres estados son distinguibles: uno acepta, otro no, y llegan a
   bloques distintos. Que no se reduzca es la respuesta correcta, no un fallo.
5. `ab|*a.b.b.` — AFN 14, AFD 5, mínimo 4.

Verificá con `python3 main.py` en modo interactivo.
</details>

---

## Diez preguntas, diez respuestas de una frase

| Pregunta | Respuesta |
|---|---|
| ¿Por qué postfix? | Elimina paréntesis y precedencia; deja el orden de evaluación en la posición, y así Thompson es una pila. |
| ¿Por qué Thompson y no otra construcción? | Da un AFN lineal en el tamaño de la regex y sus fragmentos se componen sin ambigüedad. |
| ¿Por qué tantas ε? | Son el precio de que cada fragmento tenga un solo inicio y un solo final. |
| ¿Qué es un estado del AFD? | Un conjunto de estados del AFN: dónde podría estar la máquina a la vez. |
| ¿Cuándo acepta un estado del AFD? | Cuando su subconjunto contiene algún estado de aceptación del AFN. |
| ¿Por qué el AFD puede ser exponencial? | Hay 2ⁿ subconjuntos posibles; `(a\|b)*a(a\|b)(a\|b)` lo muestra. |
| ¿Qué significa que dos estados sean equivalentes? | Que ninguna cadena los distingue: desde ambos se acepta exactamente el mismo conjunto de cadenas. |
| ¿Por qué el estado trampa? | Los dos métodos necesitan una función de transición total: uno para comparar firmas, el otro para consultar δ(p,a) en cada par. |
| ¿Cuál es la diferencia entre los dos métodos? | La agrupación separa bloques que supone equivalentes; la tabla marca pares que demuestra distinguibles. Misma partición, direcciones opuestas. |
| ¿Por qué el AFD mínimo es único? | Myhill-Nerode: la relación de equivalencia es única, así que el cociente también, salvo renombrar estados. |
| ¿Cómo sabés que las tres construcciones preservan el lenguaje? | `tests.py`: 30 casos donde AFN, AFD y mínimo siempre coinciden. |

---

## Mostrar la minimización en vivo

La pestaña **minimización** del visor pone los dos métodos lado a lado sobre la
misma expresión, y el botón `llenar tabla` los avanza ronda por ronda.

Qué señalar, en este orden:

1. **Ronda 0** — solo se marcan los pares donde uno acepta y el otro no. Es la
   cadena vacía distinguiéndolos. Al mismo tiempo, la agrupación arranca con
   exactamente esos dos bloques. Mismo punto de partida.
2. **Rondas siguientes** — la tabla se llena hacia atrás (un par se marca porque
   sus destinos ya estaban marcados) mientras los bloques se van partiendo.
   Pasando el mouse por una celda sale el motivo exacto: qué símbolo y qué par
   ya marcado la causó.
3. **El final** — las celdas que quedaron en menta con `≡` son los pares
   equivalentes, y coinciden exactamente con los bloques que sobrevivieron en la
   columna de la derecha. En `(b|b)*abb(a|b)*` son `{0,2}` y `{4,5,6}`: los
   mismos que aparecen en la correspondencia del AFD mínimo.

Ese último punto es la demostración visual de que los dos algoritmos calculan la
misma relación de equivalencia, que es justo lo que dice Myhill-Nerode.

El estado `T` de la tabla es el trampa que agrega `_completar`. Conviene
anticiparlo antes de que pregunten: no es un estado del AFD original, se agrega
para que la función de transición sea total y desaparece al final.

---

## El día de la presentación

Corré esto antes de abrir la boca:

```bash
python3 tests.py                        # 30/30
python3 main.py pruebas.txt babbaaaa    # el pipeline completo
```

Después abrí el visor (`python3 app.py`) y usalo para las dos cosas que el PNG no
puede:

- Poner el AFN y el AFD en el mismo paso y señalar que el estado `4` del AFD
  **es** el conjunto `{13,14,16,18,20,21}` del AFN mientras ambos están
  resaltados. Eso demuestra la construcción de subconjuntos mejor que explicarla.
- Correr la pestaña de minimización ronda por ronda con los dos métodos en
  paralelo.
