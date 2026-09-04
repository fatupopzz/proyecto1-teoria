/* Visor de autómatas — Proyecto 1
   Pide al servidor los tres autómatas ya construidos (SVG + pasos de la
   simulación) y resalta sobre el grafo qué estados están activos en cada
   paso. El resaltado se hace buscando el <title> que Graphviz pone dentro
   de cada <g class="node"> y <g class="edge">. */

const $ = (id) => document.getElementById(id);

const el = {
  regex: $('regex'), cadena: $('cadena'),
  postfix: $('postfix'), veredictos: $('veredictos'), aviso: $('aviso'),
  cinta: $('cinta'), contador: $('contador'), lecturaEstado: $('lecturaEstado'),
  anterior: $('anterior'), siguiente: $('siguiente'), reproducir: $('reproducir'),
  pestanas: $('pestanas'), lienzo: $('lienzo'), capa: $('capa'),
  vacio: $('vacio'), encajar: $('encajar'),
  archivo: $('archivo'), nombreArchivo: $('nombreArchivo'),
  lista: $('lista'), listaZona: $('listaZona'),
  generarPng: $('generarPng'), quitarArchivo: $('quitarArchivo'),
  panelMin: $('panelMin'), minTabla: $('minTabla'), minBloques: $('minBloques'),
  minMotivo: $('minMotivo'), minLeyenda: $('minLeyenda'),
  rondaMenos: $('rondaMenos'), rondaMas: $('rondaMas'),
  rondaPlay: $('rondaPlay'), rondaContador: $('rondaContador'),
};

const NOMBRES = { afn: 'AFN', afd: 'AFD', min: 'AFD mín' };

/* tonos por ronda: la ronda 0 es la más oscura y aclara hacia afuera */
const TONOS = ['#8c3d55', '#b04d6a', '#d4607f', '#e8859c', '#f0a8b8', '#f5c6d1'];
function tono(r) { return TONOS[Math.min(r, TONOS.length - 1)]; }

let datos = null;       // respuesta del servidor
let clave = 'afn';      // pestaña activa
let paso = 0;
let tocando = null;     // id del setInterval de reproducción
let indice = { nodos: new Map(), aristas: new Map() };
let vista = { escala: 1, x: 0, y: 0 };

/* ---------- comunicación con el servidor ---------- */

let temporizador = null;
let temporizadorLote = null;
function pedirConRetraso() {
  clearTimeout(temporizador);
  temporizador = setTimeout(pedir, 300);
}

async function pedir() {
  detener();
  const cuerpo = { regex: el.regex.value, cadena: el.cadena.value };

  let respuesta;
  try {
    const r = await fetch('/api/procesar', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(cuerpo),
    });
    respuesta = await r.json();
  } catch {
    mostrarAviso('Se perdió la conexión con el servidor. Revisá que app.py siga corriendo.');
    return;
  }

  if (!respuesta.ok) {
    mostrarAviso(respuesta.error);
    el.postfix.textContent = '—';
    el.veredictos.innerHTML = '';
    return;
  }

  datos = respuesta;
  paso = 0;
  ocultarAviso();

  if (datos.simbolos_ajenos.length) {
    mostrarAviso(
      `w usa símbolos que no están en el alfabeto de r: ${datos.simbolos_ajenos.join(' ')}. ` +
      `La simulación se corta ahí.`, true);
  }

  el.postfix.textContent = datos.postfix;
  dibujarVeredictos();
  actualizarConteos();
  dibujarCinta();

  if (clave === 'tabla') {
    ronda = maxRonda();
    pintarMinimizacion();
  } else {
    cargarGrafo();
    aplicarPaso();
  }
}

function mostrarAviso(texto, esNota = false) {
  el.aviso.textContent = texto;
  el.aviso.classList.remove('oculto');
  el.aviso.classList.toggle('nota', esNota);
}
function ocultarAviso() { el.aviso.classList.add('oculto'); }

/* ---------- veredictos ---------- */

function dibujarVeredictos() {
  el.veredictos.innerHTML = '';
  for (const k of ['afn', 'afd', 'min']) {
    const acepta = datos.automatas[k].aceptada;
    const chip = document.createElement('span');
    chip.className = `chip ${acepta ? 'si' : 'no'}`;
    chip.textContent = `${NOMBRES[k]} · ${acepta ? 'sí' : 'no'}`;
    el.veredictos.appendChild(chip);
  }
}

function actualizarConteos() {
  for (const k of ['afn', 'afd', 'min']) {
    $(`n-${k}`).textContent = `${datos.automatas[k].n_estados}`;
  }
}

/* ---------- la cinta ---------- */

function pasosActuales() { return datos ? datos.automatas[clave].pasos : []; }

function dibujarCinta() {
  el.cinta.innerHTML = '';
  const cadena = datos.cadena;

  const marca = document.createElement('div');
  marca.className = 'celda celda-inicio';
  marca.textContent = '▸';
  marca.title = 'antes de leer nada';
  marca.onclick = () => irA(0);
  el.cinta.appendChild(marca);

  if (!cadena.length) {
    const nota = document.createElement('span');
    nota.className = 'cinta-vacia';
    nota.textContent = 'w es la cadena vacía — solo se evalúa el estado inicial.';
    el.cinta.appendChild(nota);
    return;
  }

  [...cadena].forEach((simbolo, i) => {
    const celda = document.createElement('div');
    celda.className = 'celda';
    celda.textContent = simbolo;
    celda.onclick = () => irA(i + 1);
    el.cinta.appendChild(celda);
  });
}

function pintarCinta() {
  const celdas = [...el.cinta.querySelectorAll('.celda')];
  const pasos = pasosActuales();
  const muerto = pasos[paso] && pasos[paso].muerto;

  celdas.forEach((celda, i) => {
    celda.classList.toggle('leida', i > 0 && i < paso);
    celda.classList.toggle('cabeza', i === paso);
    celda.classList.toggle('rechazo', i === paso && muerto);
  });
}

/* ---------- grafo ---------- */

function cargarGrafo() {
  el.capa.innerHTML = datos.automatas[clave].svg;
  el.vacio.classList.add('oculto');
  indexarSvg();
  marcarAceptacion();
  encajar();
}

function indexarSvg() {
  indice = { nodos: new Map(), aristas: new Map() };
  for (const g of el.capa.querySelectorAll('g.node')) {
    const t = g.querySelector('title');
    if (t) indice.nodos.set(t.textContent.trim(), g);
  }
  for (const g of el.capa.querySelectorAll('g.edge')) {
    const t = g.querySelector('title');
    if (t) indice.aristas.set(t.textContent.trim().replace(/\s/g, ''), g);
  }
}

function marcarAceptacion() {
  for (const estado of datos.automatas[clave].aceptacion) {
    indice.nodos.get(String(estado))?.classList.add('aceptacion');
  }
}

function aplicarPaso() {
  const pasos = pasosActuales();
  if (!pasos.length) return;
  paso = Math.max(0, Math.min(paso, pasos.length - 1));
  const actual = pasos[paso];

  for (const g of indice.nodos.values()) g.classList.remove('activo');
  for (const g of indice.aristas.values()) g.classList.remove('recorrida');

  for (const estado of actual.estados) {
    indice.nodos.get(String(estado))?.classList.add('activo');
  }
  for (const [origen, destino] of actual.aristas) {
    indice.aristas.get(`${origen}->${destino}`)?.classList.add('recorrida');
  }

  pintarCinta();
  el.contador.textContent = `paso ${paso} / ${pasos.length - 1}`;
  el.anterior.disabled = paso === 0;
  el.siguiente.disabled = paso >= pasos.length - 1;

  if (actual.muerto) {
    el.lecturaEstado.textContent =
      `sin transición para '${actual.simbolo}' — la máquina se detiene`;
    el.lecturaEstado.style.color = 'var(--muerto)';
  } else {
    const conjunto = actual.estados.join(', ');
    const prefijo = clave === 'afn' ? 'estados activos' : 'estado actual';
    el.lecturaEstado.textContent = `${prefijo}: {${conjunto}}`;
    el.lecturaEstado.style.color = 'var(--vivo)';
  }
}

/* ---------- panel de minimización ---------- */

let ronda = 0;
let rondaTocando = null;

function maxRonda() {
  if (!datos || !datos.minimizacion.myhill) return 0;
  return Math.max(datos.minimizacion.myhill.rondas,
                  datos.minimizacion.agrupacion.rondas);
}

function dibujarTabla() {
  const m = datos.minimizacion.myhill;
  el.minTabla.innerHTML = '';
  if (!m) {
    el.minTabla.innerHTML = '<p class="min-nota">El alfabeto está vacío: ' +
                            'no hay pares que comparar.</p>';
    return;
  }

  // índice rápido de cada par
  const celdas = new Map();
  for (const c of m.celdas) celdas.set(`${c.p}|${c.q}`, c);
  const equivalentes = new Set(m.equivalentes.map((e) => `${e.p}|${e.q}`));

  const filas = m.estados.slice(1);        // se omite el primero como fila
  const columnas = m.estados.slice(0, -1); // y el último como columna
  const acepta = new Set(m.aceptacion);

  const tabla = document.createElement('table');

  const encabezado = document.createElement('tr');
  encabezado.appendChild(document.createElement('th'));
  for (const c of columnas) {
    const th = document.createElement('th');
    th.textContent = c;
    if (acepta.has(c)) th.classList.add('acepta');
    encabezado.appendChild(th);
  }
  tabla.appendChild(encabezado);

  for (const f of filas) {
    const tr = document.createElement('tr');
    const th = document.createElement('th');
    th.textContent = f;
    if (acepta.has(f)) th.classList.add('acepta');
    tr.appendChild(th);

    for (const c of columnas) {
      const td = document.createElement('td');
      const iF = m.estados.indexOf(f), iC = m.estados.indexOf(c);

      if (iC >= iF) {
        td.className = 'hueco';           // solo el triángulo inferior
      } else {
        const llave = `${c}|${f}`;
        const celda = celdas.get(llave);
        if (celda) {
          if (celda.ronda <= ronda) {
            td.className = 'marcado';
            td.textContent = celda.ronda;
            td.style.backgroundColor = tono(celda.ronda);
            td.title = `{${c}, ${f}}: ${celda.motivo}`;
            td.onmouseenter = () => {
              el.minMotivo.textContent = `{${c}, ${f}} se marcó en la ronda ` +
                                         `${celda.ronda}: ${celda.motivo}`;
            };
          } else {
            td.className = 'pendiente';
          }
        } else if (equivalentes.has(llave)) {
          td.className = ronda >= m.rondas ? 'equivalente' : 'pendiente';
          if (ronda >= m.rondas) {
            td.textContent = '≡';
            td.onmouseenter = () => {
              el.minMotivo.textContent =
                `{${c}, ${f}} nunca se marcó: son equivalentes, ` +
                `ninguna cadena los distingue.`;
            };
          }
        } else {
          td.className = 'pendiente';
        }
      }
      tr.appendChild(td);
    }
    tabla.appendChild(tr);
  }

  el.minTabla.appendChild(tabla);
}

function dibujarBloques() {
  const a = datos.minimizacion.agrupacion;
  el.minBloques.innerHTML = '';
  if (!a) return;

  a.historial.forEach((paso, i) => {
    const caja = document.createElement('div');
    caja.className = 'min-ronda';
    if (i <= ronda) caja.classList.add('visible');
    if (i === ronda) caja.classList.add('actual');

    const titulo = document.createElement('div');
    titulo.className = 'min-ronda-titulo';
    titulo.textContent = paso.titulo;
    caja.appendChild(titulo);

    for (const bloque of paso.bloques) {
      const span = document.createElement('span');
      span.className = 'bloque';
      span.textContent = '{' + bloque.join(', ') + '}';
      caja.appendChild(span);
    }
    el.minBloques.appendChild(caja);
  });
}

function pintarMinimizacion() {
  if (!datos) return;
  const tope = maxRonda();
  ronda = Math.max(0, Math.min(ronda, tope));

  dibujarTabla();
  dibujarBloques();

  el.rondaContador.textContent = `ronda ${ronda} / ${tope}`;
  el.rondaMenos.disabled = ronda === 0;
  el.rondaMas.disabled = ronda >= tope;

  const m = datos.minimizacion.myhill;
  if (m) {
    const eq = m.equivalentes.length;
    el.minLeyenda.textContent =
      `${m.n_pares} pares · ${m.celdas.length} distinguibles · ` +
      `${eq} equivalentes` +
      (datos.minimizacion.coinciden
        ? ' · los dos métodos coinciden'
        : ' · ¡los métodos NO coinciden!');
  }
}

function irARonda(n) {
  pararRondas();
  ronda = n;
  pintarMinimizacion();
}

function pararRondas() {
  if (rondaTocando) { clearInterval(rondaTocando); rondaTocando = null; }
  el.rondaPlay.textContent = '▶ llenar tabla';
}

function alternarRondas() {
  if (rondaTocando) { pararRondas(); return; }
  if (ronda >= maxRonda()) { ronda = 0; pintarMinimizacion(); }
  el.rondaPlay.textContent = '❚❚ pausa';
  rondaTocando = setInterval(() => {
    if (ronda >= maxRonda()) { pararRondas(); return; }
    ronda += 1;
    pintarMinimizacion();
  }, 1100);
}

el.rondaMenos.onclick = () => irARonda(ronda - 1);
el.rondaMas.onclick = () => irARonda(ronda + 1);
el.rondaPlay.onclick = alternarRondas;

/* ---------- transporte ---------- */

function irA(n) {
  detener();
  paso = n;
  aplicarPaso();
}

function avanzar(delta) { irA(paso + delta); }

function detener() {
  if (tocando) { clearInterval(tocando); tocando = null; }
  el.reproducir.textContent = '▶ correr';
}

function alternarPlay() {
  if (tocando) { detener(); return; }
  const total = pasosActuales().length - 1;
  if (total < 1) return;
  if (paso >= total) { paso = 0; aplicarPaso(); }

  el.reproducir.textContent = '❚❚ pausa';
  tocando = setInterval(() => {
    if (paso >= pasosActuales().length - 1) { detener(); return; }
    paso += 1;
    aplicarPaso();
  }, 650);
}

/* ---------- zoom y desplazamiento ---------- */

function aplicarVista() {
  el.capa.style.transform =
    `translate(${vista.x}px, ${vista.y}px) scale(${vista.escala})`;
}

function encajar() {
  const svg = el.capa.querySelector('svg');
  if (!svg) return;

  // se mide sin transformar para obtener el tamaño real en px
  el.capa.style.transform = 'none';
  const caja_svg = svg.getBoundingClientRect();
  const ancho = caja_svg.width, alto = caja_svg.height;
  if (!ancho || !alto) return;

  const caja = el.lienzo.getBoundingClientRect();
  const margen = 28;

  vista.escala = Math.min(
    (caja.width - margen) / ancho,
    (caja.height - margen) / alto,
    1.4);
  vista.x = (caja.width - ancho * vista.escala) / 2;
  vista.y = (caja.height - alto * vista.escala) / 2;
  aplicarVista();
}

el.lienzo.addEventListener('wheel', (e) => {
  if (!el.capa.querySelector('svg')) return;
  e.preventDefault();
  const caja = el.lienzo.getBoundingClientRect();
  const px = e.clientX - caja.left, py = e.clientY - caja.top;
  const factor = e.deltaY < 0 ? 1.12 : 1 / 1.12;
  const nueva = Math.max(.15, Math.min(6, vista.escala * factor));
  // se mantiene fijo el punto bajo el cursor
  vista.x = px - (px - vista.x) * (nueva / vista.escala);
  vista.y = py - (py - vista.y) * (nueva / vista.escala);
  vista.escala = nueva;
  aplicarVista();
}, { passive: false });

let arrastre = null;
el.lienzo.addEventListener('pointerdown', (e) => {
  arrastre = { px: e.clientX, py: e.clientY, x: vista.x, y: vista.y };
  el.lienzo.setPointerCapture(e.pointerId);
  el.lienzo.classList.add('arrastrando');
});
el.lienzo.addEventListener('pointermove', (e) => {
  if (!arrastre) return;
  vista.x = arrastre.x + (e.clientX - arrastre.px);
  vista.y = arrastre.y + (e.clientY - arrastre.py);
  aplicarVista();
});
for (const evento of ['pointerup', 'pointercancel']) {
  el.lienzo.addEventListener(evento, () => {
    arrastre = null;
    el.lienzo.classList.remove('arrastrando');
  });
}

/* ---------- archivo del calificador ---------- */

let expresiones = [];   // líneas útiles del .txt cargado
let elegida = -1;

function lineasUtiles(texto) {
  return texto.split(/\r?\n/)
    .map((l) => l.trim())
    .filter((l) => l && !l.startsWith('#'));
}

el.archivo.addEventListener('change', async (e) => {
  const archivo = e.target.files[0];
  if (!archivo) return;

  const texto = await archivo.text();
  expresiones = lineasUtiles(texto);

  if (!expresiones.length) {
    mostrarAviso(`${archivo.name} no tiene ninguna expresión. ` +
                 `Se esperaba una por línea.`);
    return;
  }

  el.nombreArchivo.innerHTML =
    `<strong>${archivo.name}</strong> — ${expresiones.length} expresiones`;
  el.generarPng.classList.remove('oculto');
  el.quitarArchivo.classList.remove('oculto');
  el.listaZona.classList.remove('oculto');

  elegida = 0;
  el.regex.value = expresiones[0];
  await Promise.all([evaluarLote(), pedir()]);
});

async function evaluarLote() {
  if (!expresiones.length) return;
  el.lista.innerHTML = '<div class="fila"><span class="n">…</span>' +
                       '<code>evaluando</code></div>';

  let datos_lote;
  try {
    const r = await fetch('/api/lote', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ expresiones, cadena: el.cadena.value }),
    });
    datos_lote = await r.json();
  } catch {
    mostrarAviso('Se perdió la conexión con el servidor.');
    return;
  }

  el.lista.innerHTML = '';
  datos_lote.resultados.forEach((fila, i) => {
    const boton = document.createElement('button');
    boton.className = 'fila' + (i === elegida ? ' elegida' : '');

    const n = document.createElement('span');
    n.className = 'n';
    n.textContent = String(fila.n).padStart(2, '0');

    const codigo = document.createElement('code');
    codigo.textContent = fila.regex;

    const tam = document.createElement('span');
    tam.className = 'tamanos';

    const marca = document.createElement('span');
    marca.className = 'marca';

    if (fila.ok) {
      tam.textContent = fila.tamanos.join(' → ');
      marca.classList.add(fila.aceptada ? 'si' : 'no');
      marca.textContent = fila.aceptada ? 'sí' : 'no';
      boton.title = `postfix: ${fila.postfix}`;
      if (!fila.coinciden) {
        marca.classList.add('mal');
        marca.textContent = '!';
        boton.title = 'Los tres autómatas no coinciden.';
      }
    } else {
      tam.textContent = fila.error;
      marca.classList.add('mal');
      marca.textContent = 'error';
    }

    boton.append(n, codigo, tam, marca);
    boton.onclick = () => {
      elegida = i;
      for (const f of el.lista.querySelectorAll('.fila')) {
        f.classList.remove('elegida');
      }
      boton.classList.add('elegida');
      el.regex.value = fila.regex;
      pedir();
    };
    el.lista.appendChild(boton);
  });
}

el.quitarArchivo.onclick = () => {
  expresiones = [];
  elegida = -1;
  el.archivo.value = '';
  el.lista.innerHTML = '';
  el.listaZona.classList.add('oculto');
  el.generarPng.classList.add('oculto');
  el.quitarArchivo.classList.add('oculto');
  el.nombreArchivo.textContent = 'sin archivo — se evalúa la expresión escrita arriba';
};

el.generarPng.onclick = async () => {
  el.generarPng.disabled = true;
  el.generarPng.textContent = 'generando…';
  try {
    const r = await fetch('/api/imagenes', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ expresiones }),
    });
    const d = await r.json();
    const falla = d.fallidas.length
      ? ` No se pudo con las líneas ${d.fallidas.join(', ')}.`
      : '';
    mostrarAviso(`${d.generados} imágenes en ${d.carpeta}.${falla}`, !falla);
  } catch {
    mostrarAviso('No se pudieron generar las imágenes.');
  }
  el.generarPng.disabled = false;
  el.generarPng.textContent = 'generar PNGs';
};

/* ---------- eventos ---------- */

el.regex.addEventListener('input', pedirConRetraso);
el.cadena.addEventListener('input', () => {
  pedirConRetraso();
  clearTimeout(temporizadorLote);
  temporizadorLote = setTimeout(evaluarLote, 320);
});
el.anterior.onclick = () => avanzar(-1);
el.siguiente.onclick = () => avanzar(1);
el.reproducir.onclick = alternarPlay;
el.encajar.onclick = encajar;

el.pestanas.addEventListener('click', (e) => {
  const boton = e.target.closest('.pestana');
  if (!boton || !datos) return;
  for (const p of el.pestanas.querySelectorAll('.pestana')) {
    p.classList.toggle('activa', p === boton);
  }
  clave = boton.dataset.clave;
  detener();
  pararRondas();

  if (clave === 'tabla') {
    el.lienzo.classList.add('oculto');
    el.panelMin.classList.remove('oculto');
    ronda = maxRonda();          // se abre con la tabla ya completa
    pintarMinimizacion();
    return;
  }

  el.panelMin.classList.add('oculto');
  el.lienzo.classList.remove('oculto');
  paso = Math.min(paso, pasosActuales().length - 1);
  cargarGrafo();
  aplicarPaso();
});

document.addEventListener('keydown', (e) => {
  if (e.target.tagName === 'INPUT') return;
  if (e.key === 'ArrowRight') { e.preventDefault(); avanzar(1); }
  if (e.key === 'ArrowLeft') { e.preventDefault(); avanzar(-1); }
  if (e.key === ' ') { e.preventDefault(); alternarPlay(); }
});

window.addEventListener('resize', () => { if (datos) encajar(); });

pedir();
