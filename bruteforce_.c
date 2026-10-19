#include <errno.h>
#include <inttypes.h>
#include <limits.h>
#include <openssl/des.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#define DEFAULT_KEY 900000ULL
#define DEFAULT_LIMIT 1000000ULL
#define SEARCH "la busqueda distribuida termina cuando aparece la frase clave"
#define MAX_DES_KEY (1ULL << 56)

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

static int tryKey(uint64_t key, const char *cipher, size_t len) {
    char temporary[len + 1];
    memcpy(temporary, cipher, len);
    temporary[len] = '\0';
    return crypt_buffer(key, temporary, len, DES_DECRYPT)
        && strstr(temporary, SEARCH) != NULL;
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
    size_t padded = ((size_t)raw_length + 7U) & ~(size_t)7U;
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

static int parse_number(const char *value, uint64_t *number) {
    char *end = NULL;
    if (*value == '-') return 0;
    errno = 0;
    *number = strtoull(value, &end, 10);
    return errno == 0 && end != value && *end == '\0';
}

int main(int argc, char **argv) {
    uint64_t secret_key = DEFAULT_KEY, limit = DEFAULT_LIMIT;
    for (int i = 1; i < argc; ++i) {
        if (strcmp(argv[i], "--help") == 0) {
            printf("Uso: %s [--key N] [--limit N]\n", argv[0]);
            return 0;
        }
        uint64_t *target = NULL;
        if (strcmp(argv[i], "--key") == 0) target = &secret_key;
        if (strcmp(argv[i], "--limit") == 0) target = &limit;
        if (target == NULL || ++i == argc || !parse_number(argv[i], target)) {
            fprintf(stderr, "Uso: %s [--key N] [--limit N]\n", argv[0]);
            return 2;
        }
    }
    if (limit == 0 || limit > MAX_DES_KEY || secret_key >= limit) {
        fprintf(stderr, "Se requiere 0 <= llave < limite <= 2^56.\n");
        return 2;
    }

    size_t length = 0;
    char *cipher = read_plaintext(&length);
    if (cipher == NULL) {
        fprintf(stderr, "No se pudo leer texto_plano.txt\n");
        return 1;
    }
    if (!crypt_buffer(secret_key, cipher, length, DES_ENCRYPT)) {
        fprintf(stderr, "Fallo al cifrar con DES.\n");
        free(cipher); return 1;
    }

    struct timespec started, stopped;
    timespec_get(&started, TIME_UTC);
    uint64_t winner = UINT64_MAX;
    for (uint64_t candidate = 0; candidate < limit; ++candidate) {
        if (tryKey(candidate, cipher, length)) {
            winner = candidate;
            break;
        }
    }
    timespec_get(&stopped, TIME_UTC);
    double elapsed = (double)(stopped.tv_sec - started.tv_sec)
        + (double)(stopped.tv_nsec - started.tv_nsec) / 1e9;
    if (winner == UINT64_MAX || !crypt_buffer(winner, cipher, length, DES_DECRYPT)) {
        fprintf(stderr, "No se encontro llave.\n");
        free(cipher); return 1;
    }
    printf("TIEMPO_TOTAL=%.6f\nLLAVE=%" PRIu64 "\nTEXTO_DESCIFRADO=%s\n", elapsed, winner, cipher);
    int correct = winner == secret_key;
    printf("VERIFICACION=%s\n", correct ? "CORRECTA" : "INCORRECTA");
    free(cipher);
    return correct ? 0 : 1;
}
