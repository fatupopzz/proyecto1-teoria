"""
Construccion de Thompson: genera un AFN a partir de una expresion regular
en notacion postfix.

Cada fragmento generado cumple la propiedad de Thompson:
    - un unico estado inicial sin transiciones de entrada
    - un unico estado de aceptacion sin transiciones de salida
"""

from .automata import AFN
from .shunting_yard import EPSILON, UNARIOS, BINARIOS


class _Fragmento:
    """Fragmento de AFN con un estado inicial y uno de aceptacion."""

    def __init__(self, inicio, aceptacion):
        self.inicio = inicio
        self.aceptacion = aceptacion


class _Constructor:
    def __init__(self):
        self.contador = 0
        self.transiciones = {}
        self.estados = set()
        self.alfabeto = set()

    def nuevo_estado(self):
        estado = self.contador
        self.contador += 1
        self.estados.add(estado)
        return estado

    def agregar(self, origen, simbolo, destino):
        self.transiciones.setdefault((origen, simbolo), set()).add(destino)
        if simbolo != EPSILON:
            self.alfabeto.add(simbolo)

    # --- Casos base y operaciones ------------------------------------

    def simbolo(self, c):
        """Caso base: un unico simbolo (o epsilon)."""
        i = self.nuevo_estado()
        f = self.nuevo_estado()
        self.agregar(i, c, f)
        return _Fragmento(i, f)

    def concatenacion(self, frag_a, frag_b):
        """a.b : se une la aceptacion de A con el inicio de B por epsilon."""
        self.agregar(frag_a.aceptacion, EPSILON, frag_b.inicio)
        return _Fragmento(frag_a.inicio, frag_b.aceptacion)

    def union(self, frag_a, frag_b):
        """a|b : nuevo inicio con epsilon a ambos, ambos a un nuevo final."""
        i = self.nuevo_estado()
        f = self.nuevo_estado()
        self.agregar(i, EPSILON, frag_a.inicio)
        self.agregar(i, EPSILON, frag_b.inicio)
        self.agregar(frag_a.aceptacion, EPSILON, f)
        self.agregar(frag_b.aceptacion, EPSILON, f)
        return _Fragmento(i, f)

    def kleene(self, frag):
        """a* : cero o mas repeticiones."""
        i = self.nuevo_estado()
        f = self.nuevo_estado()
        self.agregar(i, EPSILON, frag.inicio)
        self.agregar(i, EPSILON, f)
        self.agregar(frag.aceptacion, EPSILON, frag.inicio)
        self.agregar(frag.aceptacion, EPSILON, f)
        return _Fragmento(i, f)

    def positiva(self, frag):
        """a+ : una o mas repeticiones (equivale a a.a*)."""
        i = self.nuevo_estado()
        f = self.nuevo_estado()
        self.agregar(i, EPSILON, frag.inicio)
        self.agregar(frag.aceptacion, EPSILON, frag.inicio)
        self.agregar(frag.aceptacion, EPSILON, f)
        return _Fragmento(i, f)

    def opcional(self, frag):
        """a? : cero o una repeticion (equivale a a|epsilon)."""
        i = self.nuevo_estado()
        f = self.nuevo_estado()
        self.agregar(i, EPSILON, frag.inicio)
        self.agregar(i, EPSILON, f)
        self.agregar(frag.aceptacion, EPSILON, f)
        return _Fragmento(i, f)


def construir_afn(postfix_tokens):
    """Recibe la lista de Tokens en postfix y retorna el AFN de Thompson."""
    c = _Constructor()
    pila = []

    for token in postfix_tokens:
        if token.tipo == 'simbolo':
            pila.append(c.simbolo(token.valor))

        elif token.valor in UNARIOS:
            if not pila:
                raise ValueError(f"Operador '{token.valor}' sin operando")
            frag = pila.pop()
            if token.valor == '*':
                pila.append(c.kleene(frag))
            elif token.valor == '+':
                pila.append(c.positiva(frag))
            else:
                pila.append(c.opcional(frag))

        elif token.valor in BINARIOS:
            if len(pila) < 2:
                raise ValueError(f"Operador '{token.valor}' requiere dos operandos")
            frag_b = pila.pop()
            frag_a = pila.pop()
            if token.valor == '.':
                pila.append(c.concatenacion(frag_a, frag_b))
            else:
                pila.append(c.union(frag_a, frag_b))

        else:
            raise ValueError(f"Token no reconocido: {token.valor}")

    if len(pila) != 1:
        raise ValueError("Expresion regular mal formada")

    final = pila.pop()
    return AFN(
        estados=c.estados,
        alfabeto=c.alfabeto,
        transiciones=c.transiciones,
        inicio=final.inicio,
        aceptacion={final.aceptacion},
    )
