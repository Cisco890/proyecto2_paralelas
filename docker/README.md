# DES y OpenMPI en Docker

Para conectar los equipos Windows y Linux, seguir primero
[Conectar equipos Windows y Linux](CONEXION_LAN.md). El arranque con
`docker compose up -d --build` publica SSH en **2222**, conserva las claves y
mantiene el nodo activo. Esa guia distingue la prueba SSH de la red necesaria
para MPI y documenta el uso de `SSH_PORT=2222` con red host en Linux.

Esta preparación corresponde a la fase de virtualización y deja documentada la futura conexión por LAN. Se compilan los dos programas actuales con OpenSSL, conservando el algoritmo, el texto de prueba y los resultados originales. El benchmark y sus datos no se copian a la imagen.

## Construir y comprobar

Desde la raíz del repositorio, con Docker Engine activo y accesible:

```bash
docker build -t mpi-cluster-image .
docker run --rm mpi-cluster-image mpicc --version
docker run --rm mpi-cluster-image mpirun --version
docker run --rm mpi-cluster-image mpirun -np 2 echo "Proceso MPI ejecutado"
docker run --rm mpi-cluster-image ./bruteforce_serial --key 63 --limit 256
docker run --rm mpi-cluster-image mpirun -np 4 ./bruteforce_mpi --key 63 --limit 256
```

`mpicc --version` debe identificar GCC; la versión concreta se registra después de probar. El mensaje MPI debe aparecer dos veces. Ambos programas deben mostrar `LLAVE=63` y `VERIFICACION=CORRECTA`.

La imagen usa `ubuntu:22.04`, instala compiladores, OpenMPI, OpenSSH y `libssl-dev`, y ejecuta durante la construcción:

```bash
gcc -std=c11 -O2 bruteforce_.c -lcrypto -o bruteforce_serial
mpicc -std=c11 -O2 bruteforce_mpi.c -lcrypto -o bruteforce_mpi
```

`/app` contiene ambos ejecutables y `texto_plano.txt`. El comando se ejecuta desde allí. La lista de inclusión de `.dockerignore` evita enviar resultados, reportes, credenciales y ejecutables del anfitrión al contexto. Se agregan `procps` e `iproute2` para inspeccionar procesos e interfaces.

## SSH dentro de un contenedor temporal

```bash
docker run -it --rm --name mpi_node_test mpi-cluster-image /bin/bash
```

El entrypoint crea las claves de host que falten, valida la configuración, inicia `sshd` una sola vez y ejecuta el comando mediante `exec`. Sin comando abre `/bin/bash`. Las claves de host generadas por la instalación se eliminan durante la construcción para que cada contenedor genere su propia identidad. La imagen no contiene una clave de cliente ni una lista de claves autorizadas.

Dentro del contenedor:

```bash
pgrep -a sshd
/usr/sbin/sshd -T | grep -E '^(permitrootlogin|pubkeyauthentication|passwordauthentication|kbdinteractiveauthentication|authenticationmethods) '

if [ ! -e /root/.ssh/id_rsa ] && [ ! -e /root/.ssh/id_rsa.pub ]; then
    ssh-keygen -t rsa -b 3072 -N "" -f /root/.ssh/id_rsa
else
    echo "Ya existe una llave: se conserva; comprueba que su publica corresponda."
fi
test -f /root/.ssh/id_rsa.pub && cat /root/.ssh/id_rsa.pub >> /root/.ssh/authorized_keys
chmod 700 /root/.ssh
chmod 600 /root/.ssh/authorized_keys
ssh -o BatchMode=yes localhost echo "Conexion SSH sin contrasena exitosa"
```

`BatchMode=yes` hace fallar la prueba si necesita interacción. No imprimir ni copiar el archivo privado. Al salir con `exit`, `--rm` elimina el contenedor y sus llaves temporales.

Para el requisito académico de `service ssh start`: el entrypoint ya arrancó el servicio. `pgrep -a sshd` y la conexión anterior demuestran que está activo, por lo que no se debe iniciar una segunda copia. Para ensayar específicamente el arranque manual, usar **otro** contenedor que omita el entrypoint:

```bash
docker run -it --rm --entrypoint /bin/bash mpi-cluster-image
# Dentro de este segundo contenedor:
mkdir -p /run/sshd
ssh-keygen -A
service ssh start
pgrep -a sshd
```

El servidor permite root mediante clave pública y desactiva contraseña y autenticación interactiva. `StrictHostKeyChecking no` se aplica únicamente al cliente del contenedor de laboratorio, según el requisito académico. Usar esta configuración solo en una LAN privada de confianza; no es una configuración recomendada para producción. No se modifica el SSH del anfitrión.

## Estado de validación

Validación realizada el **21 de octubre de 2026**, en Linux **x86_64**, con Docker Engine **29.8.1**. Los comandos de la primera sección se ejecutaron realmente, sin montar ni modificar los resultados anteriores.

| Prueba ejecutada | Resultado observado |
|---|---|
| `docker build -t mpi-cluster-image .` | Correcta; ambos ejecutables compilados con `-lcrypto`. |
| `docker run --rm mpi-cluster-image mpicc --version` | `gcc (Ubuntu 11.4.0-1ubuntu1~22.04.3) 11.4.0`. |
| `docker run --rm mpi-cluster-image mpirun --version` | `mpirun (Open MPI) 4.1.2`. |
| MPI con `-np 2 echo "Proceso MPI ejecutado"` | Mensaje impreso exactamente dos veces; salida 0. |
| Secuencial con `--key 63 --limit 256` | `LLAVE=63`, `VERIFICACION=CORRECTA`; salida 0. |
| MPI con cuatro procesos y la misma llave/límite | Cuatro rangos `[0,64)`, `[64,128)`, `[128,192)`, `[192,256)`; `LLAVE=63`, `VERIFICACION=CORRECTA`; salida 0. |
| `pgrep -a sshd` y `sshd -T` | Servidor activo; root y pública habilitados; contraseña e interacción deshabilitadas; método `publickey`. |
| SSH con RSA de 3072 bits generada dentro de un contenedor temporal | `ssh -o BatchMode=yes -o ConnectTimeout=5 localhost echo "Conexion SSH sin contrasena exitosa"` imprimió el mensaje y salió con 0. |
| Segunda llamada a `/usr/local/bin/mpi-entrypoint true` en el mismo contenedor | Conservó el PID del servidor; no inició otra copia. |
| Arranque manual en contenedor sin entrypoint | `ssh-keygen -A`, `service ssh start` y `pgrep -a sshd` funcionaron; salida 0. |
| Inspección antes del arranque manual | No había archivos `ssh_host_*` ni `/root/.ssh/id_rsa` en la imagen. |
| Hostfile temporal `localhost slots=4 max_slots=4` | `mpirun --hostfile /tmp/mpi-hosts -np 2 hostname` aceptó la sintaxis e imprimió dos veces el nombre del mismo contenedor. No se contactaron las IP de ejemplo. |
| `ompi_info` y `ldd ./bruteforce_serial` | Existen `btl_tcp_if_include`, `oob_tcp_if_include`, OB1 y Vader; el ejecutable carga `libcrypto.so.3`. |

Para automatizar la prueba manual se usó, sin terminal interactiva:

```bash
docker run --rm --entrypoint /bin/sh mpi-cluster-image -ec \
  'test -z "$(find /etc/ssh -maxdepth 1 -name "ssh_host_*" -print -quit)"; test ! -e /root/.ssh/id_rsa; mkdir -p /run/sshd; ssh-keygen -A; service ssh start; pgrep -a sshd'
```

Incidencias reales y cambios:

- El acceso inicial a `docker.sock` desde el sandbox fue denegado. La construcción y los contenedores se ejecutaron con autorización fuera del entorno restringido; no se cambiaron permisos del socket.
- La primera ejecución detectó una carrera: el daemon SSH aún no había escrito su PID cuando el entrypoint lo comprobó. Se añadió una espera acotada de hasta dos segundos; se reconstruyó y las pruebas posteriores pasaron.
- OpenSSL 3 emitió advertencias de deprecación de las funciones DES actuales. No impidieron compilar y no se modificaron los fuentes C.

La prueba de SSH se ejecutó en un contenedor `--rm` mediante un shell no interactivo equivalente a los pasos anteriores. No se guardaron claves privadas. Estas comprobaciones son funcionales, no una nueva campaña de benchmarks.

**Pendiente:** conexión SSH entre equipos reales, ejecución MPI por LAN, configuración de interfaces/firewall para esa LAN, red host en el entorno final y validación de arquitecturas distintas de x86_64. La conexión entre computadoras queda pendiente hasta disponer del clúster físico. El PDF de fase 2 no está entre los archivos proporcionados: los comandos académicos se toman del Markdown de instrucciones, sin afirmar una revisión directa de sus páginas 3 y 4.

## Red bridge y red host

Los comandos locales anteriores usan la red bridge predeterminada: el contenedor tiene su propio espacio de red y SSH no se publica en el anfitrión. `EXPOSE 22` documenta el puerto, no lo publica. Esto permite probar `ssh localhost` desde el propio contenedor.

Para la siguiente fase, el comando solicitado es:

```bash
docker run -it --rm --network host --name mpi_node mpi-cluster-image /bin/bash
```

No se ha ejecutado como prueba del clúster. En Linux nativo comparte la red del equipo: SSH intenta escuchar en el puerto 22 del anfitrión y puede fallar si otro servicio lo ocupa. Comprobar antes `ss -ltnp 'sport = :22'` en el anfitrión; resolver el puerto antes de iniciar el nodo. Si se usa un puerto alternativo en el laboratorio, hay que configurar también el cliente SSH y el lanzamiento remoto MPI; no basta con cambiar el puerto del servidor. No detener automáticamente el SSH del equipo.

Docker Desktop para Windows/macOS requiere una versión compatible y activar la función de red host; su comportamiento no equivale completamente al Linux nativo. Publicar solo SSH con `-p` en bridge tampoco resuelve por sí solo las conexiones adicionales de MPI. Consultar la [documentación oficial de red host](https://docs.docker.com/engine/network/drivers/host/).

## Preparar el clúster físico (requiere configurar la LAN real)

1. Conectar los equipos a la misma LAN privada, comprobar sus IP reales y elegir el maestro. Mantener los contenedores en ejecución durante las pruebas.
2. Construir la imagen en cada nodo y comprobar las versiones de OpenMPI, las rutas `/app` y los archivos de entrada. Se requiere una instalación MPI compatible en todos los nodos.
3. Dentro del contenedor maestro, generar una llave de cliente solo si no existe, igual que en la prueba local. Añadir únicamente su archivo `.pub` a `/root/.ssh/authorized_keys` de cada worker, mediante un medio autorizado. Aplicar permisos 700 al directorio y 600 al archivo. Nunca distribuir la privada; no usar una llave común incrustada en imágenes. Para intercambio entre otros pares, autorizar sus públicas según la topología necesaria.
4. Desde el contenedor maestro, verificar `ssh -o BatchMode=yes root@IP_REAL_WORKER hostname` y comprobar que responde el contenedor esperado. Con red host un `hostname` puede diferir del nombre del anfitrión: registrar la correspondencia IP, equipo y contenedor. Verificar también el acceso a la IP LAN del maestro si aparece en el hostfile.
5. Copiar `cluster/cluster_hosts.example` a `cluster/cluster_hosts` en el anfitrión y reemplazar **todas** las IP ilustrativas. Ajustar `slots` y `max_slots` a los recursos efectivamente disponibles. No habilitar oversubscription por defecto.
6. Montar ese archivo al crear el contenedor maestro, agregando al `docker run` anterior `--mount type=bind,src="$(pwd)/cluster/cluster_hosts",dst=/app/cluster_hosts,readonly`. Si SELinux bloquea el acceso en Fedora, usar para ese archivo `-v "$(pwd)/cluster/cluster_hosts:/app/cluster_hosts:ro,Z"` en lugar de `--mount`; no deshabilitar SELinux globalmente.
7. En cada anfitrión revisar `ip -br address` e `ip route` para identificar la interfaz física y la subred del router. Dentro del contenedor host se pueden inspeccionar con los mismos comandos. No seleccionar `docker0`, `veth*`, puentes `br-*`, VPN ni adaptadores virtuales como red de comunicación del clúster. Conservar loopback para comunicaciones locales.

El nombre correcto de la opción de hostfile es **`max_slots`**, con guion bajo, según el [manual oficial de OpenMPI 4.1](https://www.open-mpi.org/doc/v4.1/man1/mpirun.1.php). Las direcciones de la plantilla son ejemplos y no representan equipos detectados.

### Arquitecturas y transporte

El Dockerfile no fija una ISA: construye para la plataforma del nodo o del builder. Una imagen multi-arquitectura selecciona una variante por plataforma; no hace que un mismo ejecutable amd64 funcione de forma nativa en arm64. Compilar los binarios para cada ISA y comprobar la compatibilidad del conjunto MPI antes de mezclar arquitecturas en un clúster. La validación local de una ISA no valida las demás.

Comprobar en cada contenedor la versión y los parámetros disponibles:

```bash
uname -m
mpirun --version
ompi_info --param pml all
ompi_info --param btl tcp --level 9
ompi_info --param oob tcp --level 9
```

Solo después de preparar IP, llaves, recursos y hostfile, el ejemplo académico es:

```bash
mpirun --hostfile cluster_hosts \
  --mca btl_tcp_if_include 192.168.1.0/24 \
  --mca oob_tcp_if_include 192.168.1.0/24 \
  -np 8 ./bruteforce_mpi --key 63 --limit 256
```

Reemplazar `192.168.1.0/24` por la subred real. Los nombres y componentes MCA dependen de la versión. Filtrar interfaces TCP no garantiza que otro transporte no haya sido seleccionado. Para OpenMPI 4.1, comprobar los componentes anteriores y seleccionar explícitamente OB1 y TCP entre nodos, conservando memoria compartida local y comunicación consigo mismo:

```bash
mpirun --hostfile cluster_hosts --wdir /app \
  --mca pml ob1 --mca btl self,vader,tcp \
  --mca btl_tcp_if_include 192.168.1.0/24 \
  --mca oob_tcp_if_include 192.168.1.0/24 \
  -x OMPI_ALLOW_RUN_AS_ROOT -x OMPI_ALLOW_RUN_AS_ROOT_CONFIRM \
  -np 8 ./bruteforce_mpi --key 63 --limit 256
```

La selección y los filtros se explican en la [documentación oficial TCP de OpenMPI 4.x](https://www.open-mpi.org/faq/?category=tcp). Ajustar recursos e interfaces reales antes de ejecutar. No desactivar globalmente el firewall: cuando se conozcan LAN y rangos de puertos MPI, permitir solo SSH y los puertos TCP de datos/control necesarios desde los nodos privados autorizados. Limitar únicamente el puerto 22 no basta para MPI.

### Evidencia de participación real

Desde el maestro preparado:

```bash
mpirun --hostfile cluster_hosts -np 4 hostname
mpirun --hostfile cluster_hosts --map-by node --tag-output -np 4 hostname
```

El primer comando reproduce la prueba solicitada. Si el primer nodo tiene cuatro slots, el reparto predeterminado puede colocar los cuatro procesos allí; la segunda prueba distribuye por nodo y etiqueta las salidas para observar varios equipos. Registrar nombres distintos y su relación con las IP reales. Esta prueba valida el lanzamiento remoto; para validar el intercambio MPI entre equipos también debe funcionar `bruteforce_mpi` con el transporte y los filtros elegidos.

Guardar evidencias reales de la construcción, `mpicc --version`, MPI local, SSH sin contraseña, hostfile definitivo, versiones, interfaces, nombres por proceso y ejecución distribuida. Mantenerlas separadas de `resultados/`, que contiene los 150 benchmarks previos. No guardar claves privadas ni presentar la prueba local como evidencia de clúster físico.

## Problemas frecuentes

| Síntoma | Comprobación y solución |
|---|---|
| Permiso denegado al acceder a `docker.sock` | Verificar el acceso autorizado al servicio Docker; en entornos restringidos se requiere ejecutar Docker fuera del sandbox. No cambiar globalmente los permisos del socket. |
| Falla la descarga de Ubuntu o `apt-get` | Revisar conexión, DNS y acceso del daemon a los repositorios; repetir la construcción cuando se resuelva. |
| Advertencias sobre funciones DES de OpenSSL | Las API usadas por el código están deprecadas en OpenSSL 3; distinguir advertencias de un error de compilación. Se conserva el algoritmo existente y se enlaza con `-lcrypto`. |
| `No se pudo leer texto_plano.txt` | Ejecutar desde `/app` y no ocultar su contenido montando encima un directorio incompleto. |
| `not enough slots` | Reducir `-np` o asignar recursos reales suficientes al contenedor/nodos; no agregar oversubscription como solución predeterminada. |
| `Address already in use` al iniciar SSH | Revisar el puerto 22, especialmente con `--network host`. El entrypoint muestra el error y aborta si el servidor no queda activo. |
| `Permission denied (publickey)` | Revisar la pública autorizada, permisos, usuario y que la IP corresponda al contenedor esperado. Usar `ssh -v` sin mostrar privadas. |
| SSH funciona pero MPI se bloquea | Revisar rutas, MPI compatible, transporte, subred, interfaces virtuales y reglas específicas del firewall para datos y control. |

Los contenedores de prueba usan `--rm`; no se modifica la configuración SSH del anfitrión. La adaptación a ciphertext externo queda fuera de esta preparación.
