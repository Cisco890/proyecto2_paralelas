#!/usr/bin/env python3
"""Mide la búsqueda secuencial y la MPI con varias llaves y cantidades de procesos.

El temporizador de ambos programas cubre solo el ciclo de prueba de llaves.
Cada combinación se repite y se guardan el tiempo, la verificación y el
proceso dueño de la llave según el reparto de bruteforce_mpi.c.
"""

import argparse
import csv
import os
import platform
import re
import statistics
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTADOS = ROOT / "resultados"
MEDICIONES = RESULTADOS / "mediciones.csv"
RESUMEN = RESULTADOS / "resumen.csv"
FIGURAS = RESULTADOS / "figuras"
CHUNK_SIZE = 4096
DEFAULT_LIMIT = 524288
DEFAULT_REPS = 5

# Posiciones elegidas para mostrar el efecto de la llave, no para maximizar el speedup.
LLAVES = [
    (4095, "temprana"),
    (65535, "primer_octavo"),
    (262144, "mitad"),
    (400000, "interior"),
    (524287, "final"),
]
PROCESOS = [1, 2, 4, 8, 16]

TIME_RE = re.compile(r"TIEMPO_TOTAL=([0-9]+(?:\.[0-9]+)?)")
KEY_RE = re.compile(r"^LLAVE=([0-9]+)$", re.M)
VER_RE = re.compile(r"^VERIFICACION=(\w+)$", re.M)


def rango(rank, limit, processes):
    base = limit // processes
    extra = limit % processes
    lower = rank * base + (rank if rank < extra else extra)
    upper = lower + base + (1 if rank < extra else 0)
    return lower, upper


def dueno(key, limit, processes):
    for rank in range(processes):
        lower, upper = rango(rank, limit, processes)
        if lower <= key < upper:
            return rank, lower, upper, key - lower
    raise ValueError(f"la llave {key} queda fuera del límite {limit}")


def llaves_muro(offset, span, processes):
    """Candidatas que recorre el proceso más lento antes de poder salir.

    Con un solo proceso la búsqueda se detiene en la llave. Con varios, quien
    no la posee completa el bloque de CHUNK_SIZE y el Allreduce lo espera.
    """
    if processes <= 1:
        return min(span, offset + 1)
    return min(span, (offset // CHUNK_SIZE + 1) * CHUNK_SIZE)


def entorno_mpi():
    env = os.environ.copy()
    env["PATH"] = "/usr/lib64/openmpi/bin:" + env.get("PATH", "")
    env["OMPI_MCA_btl_base_warn_component_unused"] = "0"
    env["OMPI_MCA_mpi_show_handle_leaks"] = "0"
    return env


def comando(modo, procesos, key, limit):
    if modo == "secuencial":
        binario = ROOT / "bruteforce_serial"
        prefijo = ["taskset", "-c", "0"] if shutil_which("taskset") else []
        return prefijo + [str(binario), "--key", str(key), "--limit", str(limit)]
    binario = ROOT / "bruteforce_mpi"
    if procesos <= 8:
        afinidad = ["--bind-to", "core", "--map-by", "core"]
    else:
        afinidad = ["--bind-to", "hwthread", "--map-by", "hwthread"]
    return [
        "mpirun", "--oversubscribe", "-np", str(procesos), *afinidad,
        str(binario), "--key", str(key), "--limit", str(limit),
    ]


def shutil_which(name):
    from shutil import which
    return which(name)


def ejecutar(cmd, env):
    completo = subprocess.run(
        cmd, cwd=ROOT, env=env, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180,
    )
    salida = completo.stdout + "\n" + completo.stderr
    if completo.returncode != 0:
        raise RuntimeError(
            f"código {completo.returncode} en {' '.join(cmd)}\n{salida[-2000:]}"
        )
    tiempo = TIME_RE.search(salida)
    llave = KEY_RE.search(salida)
    verificacion = VER_RE.search(salida)
    if not (tiempo and llave and verificacion):
        raise RuntimeError(f"salida incompleta de {' '.join(cmd)}\n{salida[-2000:]}")
    if verificacion.group(1) != "CORRECTA":
        raise RuntimeError(f"verificación {verificacion.group(1)} en {' '.join(cmd)}")
    return float(tiempo.group(1)), int(llave.group(1))


def ya_medido(ruta):
    hechos = set()
    if not ruta.exists():
        return hechos
    with ruta.open(newline="") as archivo:
        for fila in csv.DictReader(archivo):
            hechos.add((fila["modo"], int(fila["procesos"]), int(fila["llave"]), int(fila["repeticion"])))
    return hechos


def medir(limit, repeticiones):
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    nuevo = not MEDICIONES.exists()
    hechos = ya_medido(MEDICIONES)
    env = entorno_mpi()
    casos = [("secuencial", 1)] + [("mpi", n) for n in PROCESOS]
    llaves = [(k, nombre) for k, nombre in LLAVES if k < limit]
    total = len(casos) * len(llaves) * repeticiones
    pendientes = total - sum(
        1 for modo, n in casos for k, _ in llaves for r in range(1, repeticiones + 1)
        if (modo, n, k, r) in hechos
    )
    print(f"mediciones pendientes: {pendientes} de {total}", flush=True)
    with MEDICIONES.open("a", newline="") as archivo:
        columnas = [
            "modo", "procesos", "llave", "etiqueta", "repeticion",
            "tiempo_s", "verificacion", "rango_dueno", "inicio_rango",
            "fin_rango", "offset", "llaves_secuencial", "llaves_muro",
        ]
        writer = csv.DictWriter(archivo, fieldnames=columnas)
        if nuevo:
            writer.writeheader()
        for modo, procesos in casos:
            for llave, etiqueta in llaves:
                procesos_reparto = procesos if modo == "mpi" else 1
                rank, lower, upper, offset = dueno(llave, limit, procesos_reparto)
                for repeticion in range(1, repeticiones + 1):
                    if (modo, procesos, llave, repeticion) in hechos:
                        continue
                    tiempo, hallada = ejecutar(comando(modo, procesos, llave, limit), env)
                    if hallada != llave:
                        raise RuntimeError(f"se esperaba {llave} y se obtuvo {hallada}")
                    writer.writerow({
                        "modo": modo,
                        "procesos": procesos,
                        "llave": llave,
                        "etiqueta": etiqueta,
                        "repeticion": repeticion,
                        "tiempo_s": f"{tiempo:.6f}",
                        "verificacion": "CORRECTA",
                        "rango_dueno": rank,
                        "inicio_rango": lower,
                        "fin_rango": upper,
                        "offset": offset,
                        "llaves_secuencial": llave + 1,
                        "llaves_muro": llaves_muro(offset, upper - lower, procesos_reparto),
                    })
                    archivo.flush()
                    print(
                        f"{modo:11} p={procesos:<2} llave={llave:<7} "
                        f"rep={repeticion} {tiempo:.3f}s",
                        flush=True,
                    )


def cargar(ruta):
    with ruta.open(newline="") as archivo:
        return list(csv.DictReader(archivo))


def resumir():
    filas = cargar(MEDICIONES)
    grupos = {}
    for fila in filas:
        clave = (fila["modo"], int(fila["procesos"]), int(fila["llave"]), fila["etiqueta"])
        grupos.setdefault(clave, []).append(float(fila["tiempo_s"]))
    serial = {
        int(llave): statistics.fmean(tiempos)
        for (modo, _, llave, _), tiempos in grupos.items()
        if modo == "secuencial"
    }
    mpi1 = {
        int(llave): statistics.fmean(tiempos)
        for (modo, procesos, llave, _), tiempos in grupos.items()
        if modo == "mpi" and procesos == 1
    }
    resumen = []
    for (modo, procesos, llave, etiqueta), tiempos in sorted(grupos.items(), key=lambda item: (item[0][2], item[0][0], item[0][1])):
        media = statistics.fmean(tiempos)
        desv = statistics.stdev(tiempos) if len(tiempos) > 1 else 0.0
        base = serial[llave]
        speedup = base / media
        eficiencia = speedup / procesos
        resumen.append({
            "modo": modo,
            "procesos": procesos,
            "llave": llave,
            "etiqueta": etiqueta,
            "repeticiones": len(tiempos),
            "media_s": f"{media:.6f}",
            "desviacion_s": f"{desv:.6f}",
            "speedup_vs_secuencial": f"{speedup:.4f}",
            "eficiencia": f"{eficiencia:.4f}",
            "speedup_vs_mpi1": f"{(mpi1[llave] / media):.4f}",
        })
    with RESUMEN.open("w", newline="") as archivo:
        writer = csv.DictWriter(archivo, fieldnames=list(resumen[0].keys()))
        writer.writeheader()
        writer.writerows(resumen)
    return filas, resumen


def limite_de(filas):
    # fin_rango del secuencial es el límite, porque su único tramo es [0, limite).
    for fila in filas:
        if fila["modo"] == "secuencial":
            return int(fila["fin_rango"])
    raise RuntimeError("no hay mediciones secuenciales")


def graficar(filas):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    FIGURAS.mkdir(parents=True, exist_ok=True)
    limit = limite_de(filas)
    etiquetas = []
    for llave, nombre in LLAVES:
        if llave < limit and nombre not in etiquetas:
            etiquetas.append(nombre)
    colores = {
        "temprana": "#0072B2",
        "primer_octavo": "#E69F00",
        "mitad": "#009E73",
        "interior": "#D55E00",
        "final": "#CC79A7",
    }
    nombres = {
        "temprana": "4095 temprana",
        "primer_octavo": "65535 primer octavo",
        "mitad": "262144 mitad",
        "interior": "400000 interior",
        "final": "524287 final",
    }
    grupos = {}
    for fila in filas:
        clave = (fila["modo"], int(fila["procesos"]), fila["etiqueta"])
        grupos.setdefault(clave, []).append(float(fila["tiempo_s"]))

    def media(modo, procesos, etiqueta):
        return statistics.fmean(grupos[(modo, procesos, etiqueta)])

    plt.rcParams.update({"font.size": 11, "axes.grid": True, "grid.alpha": 0.35, "figure.facecolor": "white"})

    fig, ax = plt.subplots(figsize=(9.2, 5.4))
    for etiqueta in etiquetas:
        ys = [media("mpi", n, etiqueta) for n in PROCESOS]
        ax.plot(PROCESOS, ys, marker="o", color=colores[etiqueta], label=nombres[etiqueta])
        ax.axhline(media("secuencial", 1, etiqueta), color=colores[etiqueta], linestyle="--", linewidth=1, alpha=0.8)
    ax.set_xscale("log", base=2)
    ax.set_yscale("log")
    ax.set_xticks(PROCESOS)
    ax.set_xticklabels([str(n) for n in PROCESOS])
    ax.set_xlabel("Procesos MPI")
    ax.set_ylabel("Tiempo medio de búsqueda (s)")
    ax.set_title("Tiempo de búsqueda. La línea discontinua es el secuencial.")
    ax.legend(frameon=False, fontsize=9)
    fig.tight_layout()
    fig.savefig(FIGURAS / "tiempos.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9.2, 5.4))
    ax.plot(PROCESOS, PROCESOS, color="#444444", linestyle=":", label="speedup ideal S = p")
    for etiqueta in etiquetas:
        serial = media("secuencial", 1, etiqueta)
        ys = [serial / media("mpi", n, etiqueta) for n in PROCESOS]
        ax.plot(PROCESOS, ys, marker="o", color=colores[etiqueta], label=nombres[etiqueta])
    ax.set_xscale("log", base=2)
    ax.set_yscale("log")
    ax.set_xticks(PROCESOS)
    ax.set_xticklabels([str(n) for n in PROCESOS])
    ax.set_xlabel("Procesos MPI")
    ax.set_ylabel("Speedup frente al secuencial")
    ax.set_title("Speedup según la posición de la llave")
    ax.legend(frameon=False, fontsize=9)
    fig.tight_layout()
    fig.savefig(FIGURAS / "speedup.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9.2, 5.4))
    ax.axhline(1.0, color="#444444", linestyle=":", label="eficiencia ideal")
    for etiqueta in etiquetas:
        serial = media("secuencial", 1, etiqueta)
        ys = [(serial / media("mpi", n, etiqueta)) / n for n in PROCESOS]
        ax.plot(PROCESOS, ys, marker="o", color=colores[etiqueta], label=nombres[etiqueta])
    ax.set_xscale("log", base=2)
    ax.set_xticks(PROCESOS)
    ax.set_xticklabels([str(n) for n in PROCESOS])
    ax.set_xlabel("Procesos MPI")
    ax.set_ylabel("Eficiencia S / p")
    ax.set_title("Eficiencia paralela. Valores mayores que 1 vienen de una llave favorable.")
    ax.legend(frameon=False, fontsize=9)
    fig.tight_layout()
    fig.savefig(FIGURAS / "eficiencia.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9.2, 5.2))
    llaves = [llave for llave, nombre in LLAVES if nombre in etiquetas]
    nombres_barra = [nombres[nombre] for _, nombre in LLAVES if nombre in etiquetas]
    tiempos = [media("secuencial", 1, nombre) for _, nombre in LLAVES if nombre in etiquetas]
    barras = ax.bar(range(len(llaves)), tiempos, color=[colores[n] for _, n in LLAVES if n in etiquetas])
    ax.set_xticks(range(len(llaves)))
    ax.set_xticklabels(nombres_barra, rotation=15, ha="right")
    ax.set_ylabel("Tiempo secuencial medio (s)")
    ax.set_title(f"El secuencial prueba las llaves 0..k. Límite = {limit}.")
    for barra, tiempo in zip(barras, tiempos):
        ax.text(barra.get_x() + barra.get_width() / 2, barra.get_height(), f"{tiempo:.2f}", ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    fig.savefig(FIGURAS / "secuencial_por_llave.png", dpi=160)
    plt.close(fig)


def escribir_entorno(limit, repeticiones):
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    cpu = "desconocido"
    info = Path("/proc/cpuinfo").read_text(errors="replace")
    for linea in info.splitlines():
        if linea.startswith("model name"):
            cpu = linea.split(":", 1)[1].strip()
            break
    texto = "\n".join([
        f"sistema={platform.platform()}",
        f"cpu={cpu}",
        f"cpus_logicos={os.cpu_count()}",
        f"limite={limit}",
        f"repeticiones={repeticiones}",
        f"bloque={CHUNK_SIZE}",
        "secuencial=bruteforce_.c compilado con gcc -std=c11 -O2 -lcrypto",
        "paralelo=bruteforce_mpi.c compilado con mpicc -std=c11 -O2 -lcrypto",
        "tiempo=solo el ciclo de búsqueda (MPI_Wtime o timespec_get)",
        "",
    ])
    (RESULTADOS / "entorno.txt").write_text(texto)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limite", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--repeticiones", type=int, default=DEFAULT_REPS)
    parser.add_argument("--graficar", action="store_true", help="solo regenera tablas y figuras")
    args = parser.parse_args()
    if args.limite != DEFAULT_LIMIT and not args.graficar:
        print("este diseño usa llaves fijas pensadas para el límite 524288", file=sys.stderr)
        return 2
    os.chdir(ROOT)
    if not args.graficar:
        for nombre in ("bruteforce_serial", "bruteforce_mpi"):
            if not (ROOT / nombre).exists():
                print(f"falta ./{nombre}; compílalo antes de medir", file=sys.stderr)
                return 1
        escribir_entorno(args.limite, args.repeticiones)
        medir(args.limite, args.repeticiones)
    filas, _ = resumir()
    graficar(filas)
    print(f"resumen: {RESUMEN}")
    print(f"figuras: {FIGURAS}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)
