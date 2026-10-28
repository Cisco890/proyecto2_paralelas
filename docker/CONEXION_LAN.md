# Conectar equipos Windows y Linux

Primero comprobar SSH entre los contenedores y luego ejecutar MPI con direcciones
alcanzables en ambos sentidos. Un test TCP exitoso no verifica las claves ni el
intercambio de mensajes MPI.

## 1. Arrancar SSH en cada equipo

Desde la raiz del proyecto, con Docker Engine o Docker Desktop usando contenedores
Linux y Docker Compose v2:

```bash
docker compose up -d --build
docker compose ps
docker compose logs nodo
docker compose exec nodo check-ssh.sh localhost
docker compose port nodo 22
```

Estos comandos funcionan en Bash y PowerShell. Compose publica **2222 del equipo
hacia 22 del contenedor**, mantiene el nodo activo y genera sus claves al iniciar.
El volumen conserva las claves al recrear el contenedor. El estado `healthy`
verifica SSH local con clave, no la conectividad hacia otro equipo.
Se conservan la clave de cliente y las publicas autorizadas; las claves de host
del servidor se generan para cada contenedor nuevo.

No hace falta activar host networking para esta prueba. `EXPOSE 22` por si solo
no publica puertos. Tampoco debe probarse el puerto 22 del equipo: en este modo
el puerto externo es **2222**. Un SSH del sistema operativo puede ocupar 22 sin
afectar esta configuracion.

Si 2222 esta ocupado, elegir otro puerto externo, por ejemplo 2223:

```bash
# Bash
SSH_HOST_PORT=2223 docker compose up -d
```

```powershell
# PowerShell; mantener esta variable al usar los comandos posteriores de Compose.
$env:SSH_HOST_PORT = "2223"
docker compose up -d
```

Usar ese puerto en las pruebas siguientes. Por defecto se escucha en todas las
interfaces; `SSH_BIND_IP` permite seleccionar la IP LAN del equipo si hace falta.
No usar `127.0.0.1` como direccion de publicacion para conexiones entre equipos.

## 2. Comprobar IP, escucha y acceso por LAN

Obtener la IPv4 de Wi-Fi o Ethernet con `ipconfig` en Windows y `ip -br address`
en Linux. Usar las direcciones reales de los equipos, no localhost ni las IP
internas de Docker/WSL. Los equipos deben tener una ruta entre si; para el
laboratorio, usar la misma LAN sin aislamiento de clientes o red de invitados.

Desde PowerShell, reemplazando `IP_DEL_OTRO_EQUIPO`:

```powershell
Test-NetConnection 127.0.0.1 -Port 2222
Test-NetConnection IP_DEL_OTRO_EQUIPO -Port 2222
```

Desde Linux, si esta instalado el cliente OpenSSH:

```bash
ssh-keyscan -T 5 -p 2222 127.0.0.1
ssh-keyscan -T 5 -p 2222 IP_DEL_OTRO_EQUIPO
```

`ssh-keyscan` debe devolver claves publicas de host; prueba la respuesta del
servidor sin necesitar una clave de usuario. Aun no prueba autenticacion.

| Resultado | Revisar |
|---|---|
| `docker compose exec nodo check-ssh.sh localhost` falla | Logs, arranque de SSH y claves dentro del contenedor. |
| SSH dentro funciona, pero el puerto local 2222 falla | `docker compose port nodo 22`, puerto ocupado o direccion de publicacion. |
| El puerto local funciona, pero desde otro equipo falla | IP LAN, firewall del destino, VPN, rutas y aislamiento del router. |
| SSH remoto responde `Permission denied (publickey)` | La red y el servidor responden; completar el intercambio de publicas. |
| Compose marca `healthy`, pero falla la LAN | El healthcheck es local; revisar publicacion, ruta y firewall. |

En el firewall de cada equipo permitir TCP 2222 entrante desde las IP de los
otros nodos del laboratorio. En Windows revisar tambien el perfil activo de la
red y las reglas que afectan a Docker Desktop. No desactivar el firewall completo.

## 3. Autorizar las claves entre los nodos

En cada equipo obtener **solo la publica**:

```bash
docker compose exec nodo cat /root/.ssh/id_rsa.pub
```

Copiar la linea completa. En el equipo destino, pegarla en lugar del ejemplo:

```bash
docker compose exec -e 'SSH_PUBLIC_KEY=ssh-rsa AAAA_REEMPLAZAR_PUBLICA_COMPLETA nodo-origen' nodo init-ssh.sh
```

Este comando funciona en Bash y PowerShell, agrega la publica sin borrar las
existentes y conserva permisos adecuados. Repetir para cada par que necesite
acceso; para el laboratorio de MPI autorizar las publicas entre todos los nodos.
Nunca copiar `id_rsa`, que es la privada.

Desde cada origen, comprobar el destino:

```bash
docker compose exec nodo check-ssh.sh IP_DEL_OTRO_EQUIPO 2222
```

Debe imprimir el hostname del contenedor destino y terminar con salida 0. Si el
destino usa otro puerto externo, indicarlo como segundo argumento. El puerto de
la prueba local sigue siendo 22 dentro del contenedor.

Para detener y volver a iniciar:

```bash
docker compose stop
docker compose start
```

`docker compose down` conserva el volumen; `docker compose down -v` elimina las
claves del volumen y obliga a intercambiar las nuevas publicas.

## 4. Preparar la red de MPI

La configuracion Compose anterior publica SSH. OpenMPI 4.1 tambien anuncia las
direcciones de sus interfaces y abre conexiones TCP de control y datos entre
nodos. Publicar SSH no hace alcanzables automaticamente esas direcciones.

Para este proyecto, la ruta de despliegue por LAN es **Docker Engine en Linux
nativo con `--network host` en cada nodo**. Si un equipo usa Windows, se puede
ejecutar Docker Engine dentro de una VM Linux cuya tarjeta este en modo puente
(bridge), con IP propia alcanzable en la LAN. Comprobar primero esa conectividad;
algunas redes Wi-Fi no permiten el puente de una VM.

Docker Desktop 4.34 o posterior admite host networking si se habilita y se crea
el contenedor con `--network host`. Sin embargo, no da acceso directo a las
interfaces fisicas de Windows. Por ello no se debe asumir que el filtro de la
subred LAN funcionara dentro de ese contenedor. Si las direcciones que MPI ve y
anuncia no son alcanzables entre los nodos, usar Linux nativo o una VM con red
puente; cambiar solamente la opcion de Docker no corrige esa topologia.

### Arranque en Linux nativo o dentro de la VM con puente

En cada nodo Linux, construir desde este repositorio y comprobar que 2222 esta
libre en el anfitrion Linux:

```bash
docker build -t mpi-cluster-image .
ss -ltn 'sport = :2222'
docker run -d --name mpi_lan --network host -e SSH_PORT=2222 \
  --mount type=volume,src=mpi-lan-ssh,dst=/root/.ssh \
  mpi-cluster-image /bin/sh -ec 'init-ssh.sh; exec sleep infinity'
docker logs mpi_lan
docker exec mpi_lan check-ssh.sh localhost 2222
docker exec mpi_lan ip -br address
```

Se usa 2222 tambien dentro del contenedor para evitar competir con el SSH del
anfitrion en 22. En modo host no se agrega `-p`. Esta configuracion usa otro
volumen y otras claves que Compose: obtener e intercambiar las publicas de estos
nodos antes de continuar:

```bash
docker exec mpi_lan cat /root/.ssh/id_rsa.pub
# En el destino, sustituir por la publica real del origen:
docker exec -e 'SSH_PUBLIC_KEY=ssh-rsa AAAA_REEMPLAZAR_PUBLICA_COMPLETA nodo-origen' mpi_lan init-ssh.sh
# En el origen:
docker exec mpi_lan check-ssh.sh IP_DEL_DESTINO 2222
```

Confirmar en cada contenedor la misma version compatible de OpenMPI (`mpirun
--version`), los ejecutables en `/app` y las IP de la LAN en `ip -br address`.
No filtrar por una subred que no aparezca dentro de los contenedores.

### Hostfile y ejecucion desde el maestro

Copiar `cluster/cluster_hosts.example` a `cluster/cluster_hosts`, sustituir todas
las IP y ajustar los slots. Para una prueba con dos equipos basta un slot por
nodo. Las direcciones corresponden a los anfitriones Linux o a las VM con puente.

```bash
docker cp cluster/cluster_hosts mpi_lan:/app/cluster_hosts
docker exec -it mpi_lan /bin/bash
```

Dentro del maestro, primero comprobar el lanzamiento remoto usando la **subred
real** en lugar del ejemplo:

```bash
mpirun --hostfile /app/cluster_hosts --wdir /app --map-by node --tag-output \
  --mca plm_rsh_args '-p 2222 -o BatchMode=yes -o ConnectTimeout=8' \
  --mca oob_tcp_if_include 192.168.1.0/24 \
  --mca oob_tcp_dynamic_ipv4_ports 30100-30199 \
  -np 2 hostname
```

Luego comprobar el intercambio de mensajes y el programa:

```bash
mpirun --hostfile /app/cluster_hosts --wdir /app --map-by node --tag-output \
  --mca plm_rsh_args '-p 2222 -o BatchMode=yes -o ConnectTimeout=8' \
  --mca pml ob1 --mca btl self,vader,tcp \
  --mca btl_tcp_if_include 192.168.1.0/24 \
  --mca oob_tcp_if_include 192.168.1.0/24 \
  --mca btl_tcp_port_min_v4 30000 --mca btl_tcp_port_range_v4 100 \
  --mca oob_tcp_dynamic_ipv4_ports 30100-30199 \
  -x OMPI_ALLOW_RUN_AS_ROOT -x OMPI_ALLOW_RUN_AS_ROOT_CONFIRM \
  -np 2 ./bruteforce_mpi --key 63 --limit 256
```

Para estos comandos con IPv4 y OpenMPI 4.1, permitir TCP **2222**, **30000-30099**
(datos) y **30100-30199** (control) entrantes en cada nodo desde las IP de los
demas nodos. Los rangos deben estar libres; la cantidad de puertos se puede
ampliar si crece el cluster. Verificar los parametros disponibles con
`ompi_info --param btl tcp --level 9` y
`ompi_info --param oob tcp --level 9` al cambiar la version de MPI.

La primera prueba debe mostrar dos hostnames diferentes. La segunda debe mostrar
procesos en ambos nodos, `LLAVE=63` y `VERIFICACION=CORRECTA`. Solo una prueba real
entre equipos permite afirmar que el cluster fisico funciona.

## Validacion local del 27 de octubre de 2026

Se construyo la imagen corregida en Linux y se probaron dos contenedores en una
red Docker aislada. Pasaron: Compose con estado saludable, acceso al puerto
publicado desde el anfitrion, persistencia de la clave de cliente al recrear el
nodo, autorizacion sin duplicados y SSH sin contrasena en ambos sentidos con
puertos 22 y 2222. MPI lanzo un proceso por contenedor y el programa recupero
`LLAVE=63` con `VERIFICACION=CORRECTA` usando los filtros y rangos de puertos de
esta guia, con la subred de la prueba. Se retiraron los recursos temporales.

Esta validacion no incluye computadoras fisicas separadas ni Docker Desktop en
Windows; el firewall, las rutas y la LAN de los equipos reales quedan por probar.

## Referencias

- [Publicar puertos en Docker](https://docs.docker.com/engine/network/port-publishing/).
- [Red host y limites de Docker Desktop](https://docs.docker.com/engine/network/drivers/host/).
- [Red y firewall de Docker Desktop](https://docs.docker.com/desktop/features/networking/).
- [Interfaces y transporte TCP en OpenMPI 4.x](https://www.open-mpi.org/faq/?category=tcp).
