"""Estructuras de datos para los automatas finitos."""

from .shunting_yard import EPSILON


class AFN:
    """Automata Finito No Determinista.

    estados:      set de ids (int)
    alfabeto:     set de simbolos (sin epsilon)
    transiciones: dict[(estado, simbolo)] -> set(estados)
    inicio:       id del estado inicial
    aceptacion:   set de estados de aceptacion
    """

    def __init__(self, estados, alfabeto, transiciones, inicio, aceptacion):
        self.estados = estados
        self.alfabeto = alfabeto
        self.transiciones = transiciones
        self.inicio = inicio
        self.aceptacion = aceptacion

    def mover(self, estado, simbolo):
        return self.transiciones.get((estado, simbolo), set())

    def __str__(self):
        lineas = [
            "AFN",
            f"  Estados      : {sorted(self.estados)}",
            f"  Alfabeto     : {sorted(self.alfabeto)}",
            f"  Inicial      : {self.inicio}",
            f"  Aceptacion   : {sorted(self.aceptacion)}",
            "  Transiciones :",
        ]
        for (origen, simbolo), destinos in sorted(
                self.transiciones.items(), key=lambda x: (x[0][0], str(x[0][1]))):
            s = EPSILON if simbolo == EPSILON else simbolo
            lineas.append(f"    {origen} --{s}--> {sorted(destinos)}")
        return '\n'.join(lineas)


class AFD:
    """Automata Finito Determinista.

    estados:      set de ids (int)
    alfabeto:     set de simbolos
    transiciones: dict[(estado, simbolo)] -> estado
    inicio:       id del estado inicial
    aceptacion:   set de estados de aceptacion
    etiquetas:    dict[estado] -> str  (informacion de trazabilidad, opcional)
    """

    def __init__(self, estados, alfabeto, transiciones, inicio, aceptacion,
                 etiquetas=None):
        self.estados = estados
        self.alfabeto = alfabeto
        self.transiciones = transiciones
        self.inicio = inicio
        self.aceptacion = aceptacion
        self.etiquetas = etiquetas or {}

    def mover(self, estado, simbolo):
        return self.transiciones.get((estado, simbolo))

    def __str__(self):
        lineas = [
            "AFD",
            f"  Estados      : {sorted(self.estados)}",
            f"  Alfabeto     : {sorted(self.alfabeto)}",
            f"  Inicial      : {self.inicio}",
            f"  Aceptacion   : {sorted(self.aceptacion)}",
            "  Transiciones :",
        ]
        for (origen, simbolo), destino in sorted(
                self.transiciones.items(), key=lambda x: (x[0][0], str(x[0][1]))):
            lineas.append(f"    {origen} --{simbolo}--> {destino}")
        if self.etiquetas:
            lineas.append("  Correspondencia con subconjuntos del AFN:")
            for estado in sorted(self.etiquetas):
                lineas.append(f"    {estado} = {self.etiquetas[estado]}")
        return '\n'.join(lineas)
