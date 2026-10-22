# Bitacora 


# Elaboración del Docker
Se elaboro el dockerfile durante el periodo de la clase y se realizaron algunas pruebas con el docker

### Ejecución con Docker
Para compilar y ejecutar en Ubuntu 22.04 con OpenMPI, OpenSSL y SSH:

docker build -t mpi-cluster-image .
docker run --rm mpi-cluster-image ./bruteforce_serial --key 63 --limit 256
docker run --rm mpi-cluster-image mpirun -np 4 ./bruteforce_mpi --key 63 --limit 256
Ambas pruebas deben mostrar LLAVE=63 y VERIFICACION=CORRECTA. La guía docker/README.md documenta las pruebas de MPI y SSH, los resultados de validación local y la preparación para una LAN privada. El clúster físico requiere pruebas posteriores entre equipos

# Actualización de el archivo ```bruteforce_mpi.c```
Ahora se acepta:
--ciphertext ARCHIVO
--plaintext ARCHIVO
--search FRASE
--limit N
--key N
Se realizo una prueba local y fue exitosa. Estos fueron los resultados:
Llave recuperada: 20000
Procesos MPI: 2
Validación: OK
Tiempos reales: 0.746939 s y 0.688045 s
Promedio preliminar: 0.717492 s