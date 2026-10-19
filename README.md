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
