FROM ubuntu:22.04

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        build-essential openmpi-bin libopenmpi-dev \
        openssh-server openssh-client libssl-dev ca-certificates procps iproute2 \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /run/sshd /root/.ssh \
    && chmod 700 /root/.ssh \
    && rm -f /etc/ssh/ssh_host_* \
    && printf '%s\n' \
        'PermitRootLogin yes' \
        'PubkeyAuthentication yes' \
        'PasswordAuthentication no' \
        'KbdInteractiveAuthentication no' \
        'AuthenticationMethods publickey' \
        > /etc/ssh/sshd_config.d/00-mpi-lab.conf \
    && printf '%s\n' \
        'Host *' \
        '    StrictHostKeyChecking no' \
        > /root/.ssh/config \
    && chmod 600 /root/.ssh/config

WORKDIR /app

COPY bruteforce_.c bruteforce_mpi.c texto_plano.txt ./
RUN gcc -std=c11 -O2 bruteforce_.c -lcrypto -o bruteforce_serial \
    && mpicc -std=c11 -O2 bruteforce_mpi.c -lcrypto -o bruteforce_mpi

COPY docker/entrypoint.sh /usr/local/bin/mpi-entrypoint
RUN chmod 755 /usr/local/bin/mpi-entrypoint

ENV OMPI_ALLOW_RUN_AS_ROOT=1
ENV OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1

EXPOSE 22
ENTRYPOINT ["/usr/local/bin/mpi-entrypoint"]
CMD ["/bin/bash"]
