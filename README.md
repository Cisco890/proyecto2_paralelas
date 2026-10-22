# README — Proyecto MPI: Fuerza Bruta con DES

## Objetivo
Implementar y analizar un programa de búsqueda de llaves privadas mediante fuerza bruta utilizando DES y OpenMPI, evaluando los tiempos de ejecución, speedup y distribución del trabajo.

## Distribución del trabajo

### Ana — Investigación y documentación de DES
- Investigar el funcionamiento del algoritmo DES.
- Explicar los pasos necesarios para cifrar y descifrar un texto.
- Elaborar el diagrama de flujo de DES.
- Explicar detalladamente las funciones:
  - `encrypt(key, *ciph, len)`
  - `decrypt(key, *ciph, len)`
- Documentar el proceso de cifrado de un texto de entre 335 y 365 palabras.

### Sebastian — Implementación y análisis del código
- Compilar y ejecutar `bruteforce_.c`.
- Implementar la paralelización de la búsqueda de llaves mediante OpenMPI.
- Explicar detalladamente las funciones:
  - `tryKey(key, *ciph, len)`
  - `memcpy()`
  - `strstr()`
- Elaborar diagramas que expliquen el funcionamiento de las funciones y su interacción dentro del programa.
- Verificar que el programa encuentre correctamente las llaves utilizadas.

### Francisco — Pruebas de rendimiento y análisis
- Diseñar y ejecutar pruebas con diferentes llaves privadas.
- Realizar múltiples mediciones de tiempo para cada llave y calcular promedios.
- Comparar el rendimiento de la ejecución secuencial y paralela.
- Calcular y analizar:
  - Speedup.
  - Eficiencia paralela.
  - Tiempos de ejecución según la cantidad de procesos.
- Explicar cómo influye la elección de la llave en los tiempos de búsqueda y los speedups aparentes.
- Elaborar tablas y gráficas de resultados.

## Trabajo en conjunto
- Integrar las implementaciones y verificar su funcionamiento.
- Revisar los resultados y conclusiones.
- Unificar la documentación, los diagramas y las gráficas.
- Generar y revisar el PDF final.

## Entregables
1. Código fuente funcional utilizando OpenMPI.
2. Texto cifrado de entre 335 y 365 palabras.
3. Diagramas del algoritmo DES y de las funciones del programa.
4. Tablas y gráficas de rendimiento con diferentes llaves.
5. Análisis de tiempos, speedup y eficiencia.
6. Informe final en formato PDF.

## Descripción

El proyecto busca una llave DES por fuerza bruta. `texto_plano.txt` tiene 355 palabras y 2192 bytes, e incluye la frase `la busqueda distribuida termina cuando aparece la frase clave`. Cada programa lee ese archivo, lo cifra con la llave indicada y prueba candidatas hasta que el texto descifrado vuelve a contener la frase.

`bruteforce_.c` es la versión secuencial: recorre las llaves desde 0 hasta encontrar la correcta. `bruteforce_mpi.c` reparte el intervalo `[0, limite)` en rangos contiguos, uno por proceso. Cada 4096 candidatas los procesos se sincronizan con `MPI_Allreduce` y se detienen cuando alguno encuentra la llave. DES se usa en modo ECB mediante OpenSSL. Los dos programas aceptan `--key N` y `--limit N`; por defecto la llave es 900000 y el límite es 1000000. El análisis completo está en `informe.md`.

## Ejecución

Hacen falta un compilador C, OpenMPI y la biblioteca de OpenSSL (`libcrypto`). En este equipo `mpicc` está en `/usr/lib64/openmpi/bin`. Hay que correr los programas desde el directorio del proyecto, porque ambos abren `texto_plano.txt` en el directorio actual.

```bash
export PATH="/usr/lib64/openmpi/bin:$PATH"
gcc -std=c11 -O2 bruteforce_.c -lcrypto -o bruteforce_serial
mpicc -std=c11 -O2 bruteforce_mpi.c -lcrypto -o bruteforce_mpi

./bruteforce_serial --key 63 --limit 256
mpirun -np 4 ./bruteforce_mpi --key 63 --limit 256
```

Una corrida correcta imprime la llave recuperada y `VERIFICACION=CORRECTA`. Para repetir las 150 mediciones de rendimiento:

```bash
python3 benchmark/medir_rendimiento.py
```

Ese script usa límite 524288, cinco llaves, 1, 2, 4, 8 y 16 procesos, y cinco repeticiones. Escribe `resultados/mediciones.csv`, `resultados/resumen.csv` y las figuras de `resultados/figuras/`.

## Resultados importantes

Las mediciones se hicieron en un AMD Ryzen AI 7 350 (8 núcleos, 16 hilos). Cuatro núcleos llegan a 5.09 GHz y cuatro se quedan en 3.51 GHz. El tiempo medido cubre solo la búsqueda. Las 150 ejecuciones recuperaron la llave correcta.

En secuencial el tiempo sigue la posición de la llave: 0.125 s para la llave 4095 y 8.840 s para la 524287, cerca de 59300 llaves por segundo. MPI con un proceso repite esos tiempos largos (8.796 s en la llave final).

El speedup depende de dónde cae la llave dentro del reparto:

| Llave | 2 procesos | 4 procesos | 8 procesos | 16 procesos |
|---:|---:|---:|---:|---:|
| 65535, al final del primer rango | 0.57 | 0.58 | 0.57 | 0.97 |
| 262144, al inicio de un rango posterior | 38.07 | 23.89 | 23.74 | 28.55 |
| 524287, última llave del límite | 1.33 | 2.50 | 4.56 | 7.60 |

Con la llave 262144 el speedup de 38 supera por mucho a los dos procesos: el secuencial recorre 262145 candidatas y el paralelo la encuentra en el primer bloque de 4096. Con la llave final el reparto sí es exhaustivo. El speedup crece con los procesos y queda por debajo de la cantidad de procesos, porque cada bloque espera al núcleo más lento. El detalle, las tablas completas y las gráficas están en `informe.md`.

## Ejecución con Docker

Para compilar y ejecutar en Ubuntu 22.04 con OpenMPI, OpenSSL y SSH:

```bash
docker build -t mpi-cluster-image .
docker run --rm mpi-cluster-image ./bruteforce_serial --key 63 --limit 256
docker run --rm mpi-cluster-image mpirun -np 4 ./bruteforce_mpi --key 63 --limit 256
```

Ambas pruebas deben mostrar `LLAVE=63` y `VERIFICACION=CORRECTA`. La guía [docker/README.md](docker/README.md) documenta las pruebas de MPI y SSH, los resultados de validación local y la preparación para una LAN privada. El clúster físico requiere pruebas posteriores entre equipos.
