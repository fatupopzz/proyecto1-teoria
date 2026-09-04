"""
Shunting Yard: transforma una expresion regular de notacion infix a postfix.

Operadores soportados:
    |   union
    .   concatenacion (se inserta de forma implicita)
    *   cerradura de Kleene
    +   una o mas repeticiones
    ?   cero o una repeticion
    ()  agrupacion
    \\   caracter de escape (ej. \\* representa el simbolo literal '*')

El simbolo designado para epsilon es 'e' griega minuscula, U+03B5
(la constante EPSILON). Se eligio porque no es letra ni numero del
alfabeto de entrada, asi que no puede colisionar con un simbolo.
"""

EPSILON = 'ε'

# Precedencia de operadores (mayor numero = mayor precedencia)
PRECEDENCIA = {
    '|': 1,
    '.': 2,
    '*': 3,
    '+': 3,
    '?': 3,
}

UNARIOS = {'*', '+', '?'}
BINARIOS = {'|', '.'}


class Token:
    """Token de la expresion regular.

    tipo: 'simbolo' | 'op' | '(' | ')'
    valor: el caracter
    """

    def __init__(self, tipo, valor):
        self.tipo = tipo
        self.valor = valor

    def __repr__(self):
        return self.valor

    def __eq__(self, otro):
        if isinstance(otro, Token):
            return self.tipo == otro.tipo and self.valor == otro.valor
        return False


def tokenizar(regex):
    """Convierte el string de la regex en una lista de Tokens.

    Maneja el caracter de escape '\\' para permitir simbolos literales
    que coinciden con operadores.
    """
    tokens = []
    i = 0
    while i < len(regex):
        c = regex[i]

        if c == '\\':
            if i + 1 >= len(regex):
                raise ValueError("Escape '\\' al final de la expresion")
            tokens.append(Token('simbolo', regex[i + 1]))
            i += 2
            continue

        if c.isspace():
            i += 1
            continue

        if c == '(':
            tokens.append(Token('(', c))
        elif c == ')':
            tokens.append(Token(')', c))
        elif c in PRECEDENCIA:
            tokens.append(Token('op', c))
        else:
            tokens.append(Token('simbolo', c))
        i += 1

    return tokens


def insertar_concatenacion(tokens):
    """Inserta explicitamente el operador '.' donde hay concatenacion implicita.

    Se inserta '.' entre a y b cuando:
        a es simbolo, ')' o un operador unario (*, +, ?)
        b es simbolo o '('
    """
    if not tokens:
        return []

    resultado = []
    for i, actual in enumerate(tokens):
        resultado.append(actual)
        if i + 1 >= len(tokens):
            break
        siguiente = tokens[i + 1]

        izq_cierra = (actual.tipo == 'simbolo'
                      or actual.tipo == ')'
                      or (actual.tipo == 'op' and actual.valor in UNARIOS))
        der_abre = (siguiente.tipo == 'simbolo' or siguiente.tipo == '(')

        if izq_cierra and der_abre:
            resultado.append(Token('op', '.'))

    return resultado


def a_postfix(regex):
    """Aplica el algoritmo de Shunting Yard.

    Retorna (postfix_tokens, postfix_str).
    """
    tokens = insertar_concatenacion(tokenizar(regex))

    salida = []
    pila = []

    for token in tokens:
        if token.tipo == 'simbolo':
            salida.append(token)

        elif token.tipo == 'op':
            # Los unarios son postfix y asocian a la derecha, por lo que
            # solo desapilan operadores de precedencia estrictamente mayor.
            while pila and pila[-1].tipo == 'op':
                tope = pila[-1]
                if token.valor in UNARIOS:
                    if PRECEDENCIA[tope.valor] > PRECEDENCIA[token.valor]:
                        salida.append(pila.pop())
                    else:
                        break
                else:
                    if PRECEDENCIA[tope.valor] >= PRECEDENCIA[token.valor]:
                        salida.append(pila.pop())
                    else:
                        break
            pila.append(token)

        elif token.tipo == '(':
            pila.append(token)

        elif token.tipo == ')':
            while pila and pila[-1].tipo != '(':
                salida.append(pila.pop())
            if not pila:
                raise ValueError("Parentesis desbalanceados: falta '('")
            pila.pop()  # descarta el '('

    while pila:
        tope = pila.pop()
        if tope.tipo == '(':
            raise ValueError("Parentesis desbalanceados: falta ')'")
        salida.append(tope)

    postfix_str = ''.join(t.valor for t in salida)
    return salida, postfix_str


def validar(regex):
    """Verifica de forma basica que la expresion sea sintacticamente valida."""
    if not regex.strip():
        raise ValueError("La expresion regular esta vacia")
    tokens, _ = a_postfix(regex)

    # Simulacion de la evaluacion postfix para verificar aridad
    contador = 0
    for t in tokens:
        if t.tipo == 'simbolo':
            contador += 1
        elif t.valor in UNARIOS:
            if contador < 1:
                raise ValueError(f"Operador '{t.valor}' sin operando")
        elif t.valor in BINARIOS:
            if contador < 2:
                raise ValueError(f"Operador '{t.valor}' requiere dos operandos")
            contador -= 1
    if contador != 1:
        raise ValueError("Expresion regular mal formada")
    return True
