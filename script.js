// ---- CONFIG ----
const NUMERO_WHATSAPP = "593999999999"; // <-- tu número con código de país, sin '+' ni espacios

async function cargarProductos() {
  const grid = document.getElementById("grid");
  const vacio = document.getElementById("vacio");
  try {
    const res = await fetch("productos.json", { cache: "no-store" });
    const productos = await res.json();

    if (!productos.length) {
      vacio.hidden = false;
      return;
    }

    grid.innerHTML = productos.map(tarjeta).join("");
  } catch (e) {
    vacio.hidden = false;
    vacio.textContent = "No se pudo cargar el catálogo.";
  }
}

function tarjeta(p) {
  const msg = encodeURIComponent(
    `Hola! Me interesa: ${p.nombre} - $${p.precio.toFixed(2)}`
  );
  const link = `https://wa.me/${+593980054249}?text=${msg}`;

  return `
    <article class="card">
      <img src="${p.imagen}" alt="${p.nombre}" loading="lazy" onerror="this.src='img/placeholder.jpg'">
      <div class="card-body">
        <div class="nombre">${p.nombre}</div>
        <div class="desc">${p.descripcion}</div>
        <div class="precio">$${p.precio.toFixed(2)}</div>
        <a class="btn-wa" href="${link}" target="_blank" rel="noopener">Hacer mi pedido</a>
      </div>
    </article>
  `;
}

cargarProductos();
