#include <errno.h>
#include <inttypes.h>
#include <limits.h>
#include <mpi.h>
#include <openssl/des.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define DEFAULT_KEY 900000ULL
#define DEFAULT_LIMIT 1000000ULL
#define NOT_FOUND UINT64_MAX
#define CHUNK_SIZE 4096ULL
#define SEARCH "la busqueda distribuida termina cuando aparece la frase clave"
#define MAX_DES_KEY (1ULL << 56)

/* Convierte los 56 bits efectivos en 8 bytes DES y fija los bits de paridad. */
static void key_to_des(uint64_t key, DES_cblock *des_key) {
    for (int i = 7; i >= 0; --i) {
        (*des_key)[i] = (unsigned char)((key & 0x7fU) << 1);
        key >>= 7;
    }
    DES_set_odd_parity(des_key);
}

static int crypt_buffer(uint64_t key, char *buffer, size_t len, int mode) {
    if (len % 8 != 0) return 0;
    DES_cblock des_key, input, output;
    DES_key_schedule schedule;
    key_to_des(key, &des_key);
    DES_set_key_unchecked(&des_key, &schedule);
    for (size_t offset = 0; offset < len; offset += 8) {
        memcpy(input, buffer + offset, 8);
        DES_ecb_encrypt(&input, &output, &schedule, mode);
        memcpy(buffer + offset, output, 8);
    }
    return 1;
}

static int encrypt(uint64_t key, char *text, size_t len) {
    return crypt_buffer(key, text, len, DES_ENCRYPT);
}

static int decrypt(uint64_t key, char *text, size_t len) {
    return crypt_buffer(key, text, len, DES_DECRYPT);
}

static int try_key(uint64_t key, const char *cipher, size_t len) {
    char temporary[len + 1];
    memcpy(temporary, cipher, len);
    temporary[len] = '\0';
    int valid = decrypt(key, temporary, len) && strstr(temporary, SEARCH) != NULL;
    return valid;
}

static char *read_plaintext(size_t *length) {
    FILE *file = fopen("texto_plano.txt", "rb");
    if (file == NULL) return NULL;
    if (fseek(file, 0, SEEK_END) != 0) { fclose(file); return NULL; }
    long raw_length = ftell(file);
    rewind(file);
    if (raw_length < 1 || (unsigned long)raw_length > UINT_MAX - 8U) {
        fclose(file); return NULL;
    }
    size_t padded = ((size_t)raw_length + 7U) & ~7U;
    char *text = calloc(padded + 1, 1);
    if (text != NULL && fread(text, 1, (size_t)raw_length, file) != (size_t)raw_length) {
        free(text); text = NULL;
    }
    fclose(file);
    if (text != NULL) {
        memset(text + raw_length, ' ', padded - (size_t)raw_length);
        *length = padded;
    }
    return text;
}

static uint64_t parse_argument(const char *value, const char *name) {
    char *end = NULL;
    errno = 0;
    uint64_t number = strtoull(value, &end, 10);
    if (*value == '-' || errno || end == value || *end != '\0') {
        fprintf(stderr, "Valor invalido para %s: %s\n", name, value);
        MPI_Abort(MPI_COMM_WORLD, 2);
    }
    return number;
}

int main(int argc, char **argv) {
    MPI_Init(&argc, &argv);
    int processes, rank;
    MPI_Comm_size(MPI_COMM_WORLD, &processes);
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);

    uint64_t secret_key = DEFAULT_KEY, limit = DEFAULT_LIMIT;
    for (int i = 1; i < argc; ++i) {
        if (strcmp(argv[i], "--key") == 0 && i + 1 < argc) secret_key = parse_argument(argv[++i], "--key");
        else if (strcmp(argv[i], "--limit") == 0 && i + 1 < argc) limit = parse_argument(argv[++i], "--limit");
        else if (strcmp(argv[i], "--help") == 0) {
            if (rank == 0) printf("Uso: %s [--key N] [--limit N]\n", argv[0]);
            MPI_Finalize(); return 0;
        } else {
            if (rank == 0) fprintf(stderr, "Uso: %s [--key N] [--limit N]\n", argv[0]);
            MPI_Finalize(); return 2;
        }
    }
    if (limit == 0 || limit > MAX_DES_KEY || secret_key >= limit) {
        if (rank == 0) fprintf(stderr, "Se requiere 0 <= llave < limite <= 2^56.\n");
        MPI_Finalize(); return 2;
    }

    size_t length = 0;
    char *cipher = read_plaintext(&length);
    if (cipher == NULL) {
        if (rank == 0) fprintf(stderr, "No se pudo leer texto_plano.txt\n");
        MPI_Abort(MPI_COMM_WORLD, 1);
    }
    if (!encrypt(secret_key, cipher, length)) {
        if (rank == 0) fprintf(stderr, "Fallo al cifrar con DES.\n");
        MPI_Abort(MPI_COMM_WORLD, 1);
    }

    uint64_t base = limit / (uint64_t)processes;
    uint64_t extra = limit % (uint64_t)processes;
    uint64_t lower = (uint64_t)rank * base + ((uint64_t)rank < extra ? (uint64_t)rank : extra);
    uint64_t upper = lower + base + ((uint64_t)rank < extra ? 1U : 0U);
    uint64_t local = NOT_FOUND, winner = NOT_FOUND;
    uint64_t max_work = (limit + (uint64_t)processes - 1U) / (uint64_t)processes;

    MPI_Barrier(MPI_COMM_WORLD);
    double started = MPI_Wtime();
    /* Todos hacen las mismas colectivas; una victoria se propaga al terminar un bloque corto. */
    for (uint64_t offset = 0; offset < max_work; offset += CHUNK_SIZE) {
        uint64_t end = lower + offset + CHUNK_SIZE;
        if (end > upper || end < lower) end = upper;
        if (local == NOT_FOUND) {
            for (uint64_t candidate = lower + offset; candidate < end; ++candidate) {
                if (try_key(candidate, cipher, length)) {
                    local = candidate;
                    break;
                }
            }
        }
        MPI_Allreduce(&local, &winner, 1, MPI_UINT64_T, MPI_MIN, MPI_COMM_WORLD);
        if (winner != NOT_FOUND) break;
    }
    double elapsed = MPI_Wtime() - started;

    double total_elapsed = 0.0;
    MPI_Reduce(&elapsed, &total_elapsed, 1, MPI_DOUBLE, MPI_MAX, 0, MPI_COMM_WORLD);
    printf("PROCESO=%d RANGO=[%" PRIu64 ",%" PRIu64 ") TIEMPO=%.6f\n", rank, lower, upper, elapsed);
    if (rank == 0) {
        if (winner == NOT_FOUND) fprintf(stderr, "No se encontro llave.\n");
        else {
            if (!decrypt(winner, cipher, length)) {
                fprintf(stderr, "Fallo al descifrar con DES.\n");
                MPI_Abort(MPI_COMM_WORLD, 1);
            }
            printf("TIEMPO_TOTAL=%.6f\nLLAVE=%" PRIu64 "\nTEXTO_DESCIFRADO=%s\n", total_elapsed, winner, cipher);
            printf("VERIFICACION=%s\n", winner == secret_key ? "CORRECTA" : "INCORRECTA");
        }
    }
    free(cipher);
    MPI_Finalize();
    return winner != secret_key;
}
