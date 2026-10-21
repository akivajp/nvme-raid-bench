// Strata のエキスパート読み込み (load_experts_gguf の Linux 経路) を模したベンチマーク。
// ファイルの先頭から指定量を「層」単位 (既定 1GiB) に分け、スレッドが次の層を取り合って読む。
// 読み先は事前にページを確保した (固定メモリと同じく、読み込み中にページフォルトが起きない) 領域。
//
// 読み方 (--mode):
//   fread   fopen + fread で一時バッファに読み、16 分割して memcpy で読み先へ写す (Strata の現行方式)
//   pread   バッファを介さず、pread で読み先へ直接読む (コピー1回分を省く)
//   direct  O_DIRECT の pread で読み先へ直接読む (ページキャッシュも通さない)
//   directbuf O_DIRECT の pread で整列した一時バッファに読み、16 分割して memcpy で写す
//           (Strata の Windows 経路 FILE_FLAG_NO_BUFFERING と同じ形。Linux へ移植したときの見込み)
//
// ビルド: gcc -O2 -pthread -o loader_bench scripts/loader_bench.c
// 例:     ./loader_bench --file model.gguf --bytes 32g --threads 6 --mode fread --drop
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>

static const char* g_file;
static uint64_t g_bytes = 32ull << 30;   // 読む量
static uint64_t g_layer = 1ull << 30;    // 1つの「層」の大きさ (スレッドの取り分の単位)
static uint64_t g_chunk = 16ull << 20;   // 1回の読み込みの大きさ (Strata は 16 エキスパート分)
static int g_threads = 6;
static const char* g_mode = "fread";
static uint8_t* g_dst;
static atomic_uint_fast64_t g_next;

static double now(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec + ts.tv_nsec / 1e9;
}

static uint64_t parse_size(const char* s) {
    char* end;
    uint64_t v = strtoull(s, &end, 10);
    switch (*end) {
        case 'k': case 'K': return v << 10;
        case 'm': case 'M': return v << 20;
        case 'g': case 'G': return v << 30;
        default: return v;
    }
}

static void die(const char* what) {
    fprintf(stderr, "%s: %s\n", what, strerror(errno));
    exit(1);
}

static void* worker(void* arg) {
    (void) arg;
    const uint64_t layers = g_bytes / g_layer;
    if (strcmp(g_mode, "fread") == 0) {
        FILE* f = fopen(g_file, "rb");
        if (!f) die("fopen");
        uint8_t* buf = malloc(g_chunk);
        for (;;) {
            const uint64_t l = atomic_fetch_add(&g_next, 1);
            if (l >= layers) break;
            for (uint64_t done = 0; done < g_layer; done += g_chunk) {
                const uint64_t off = l * g_layer + done;
                if (fseeko(f, (off_t) off, SEEK_SET) != 0) die("fseeko");
                if (fread(buf, 1, g_chunk, f) != g_chunk) die("fread");
                // Strata はエキスパートごとに写す (1回の読み込み = 16 エキスパート)
                const uint64_t piece = g_chunk / 16;
                for (int k = 0; k < 16; ++k) memcpy(g_dst + off + k * piece, buf + k * piece, piece);
            }
        }
        free(buf);
        fclose(f);
    } else if (strcmp(g_mode, "directbuf") == 0) {
        const int fd = open(g_file, O_RDONLY | O_DIRECT);
        if (fd < 0) die("open");
        uint8_t* buf;
        if (posix_memalign((void**) &buf, 4096, g_chunk) != 0) die("posix_memalign");
        for (;;) {
            const uint64_t l = atomic_fetch_add(&g_next, 1);
            if (l >= layers) break;
            for (uint64_t done = 0; done < g_layer; done += g_chunk) {
                const uint64_t off = l * g_layer + done;
                uint64_t got = 0;
                while (got < g_chunk) {
                    const ssize_t r = pread(fd, buf + got, g_chunk - got, (off_t) (off + got));
                    if (r <= 0) die("pread");
                    got += (uint64_t) r;
                }
                const uint64_t piece = g_chunk / 16;
                for (int k = 0; k < 16; ++k) memcpy(g_dst + off + k * piece, buf + k * piece, piece);
            }
        }
        free(buf);
        close(fd);
    } else {
        const int direct = strcmp(g_mode, "direct") == 0;
        const int fd = open(g_file, O_RDONLY | (direct ? O_DIRECT : 0));
        if (fd < 0) die("open");
        for (;;) {
            const uint64_t l = atomic_fetch_add(&g_next, 1);
            if (l >= layers) break;
            for (uint64_t done = 0; done < g_layer; done += g_chunk) {
                const uint64_t off = l * g_layer + done;
                uint64_t got = 0;
                while (got < g_chunk) {
                    const ssize_t r = pread(fd, g_dst + off + got, g_chunk - got, (off_t) (off + got));
                    if (r <= 0) die("pread");
                    got += (uint64_t) r;
                }
            }
        }
        close(fd);
    }
    return NULL;
}

int main(int argc, char** argv) {
    int drop = 0;
    for (int i = 1; i < argc; ++i) {
        if (!strcmp(argv[i], "--file") && i + 1 < argc) g_file = argv[++i];
        else if (!strcmp(argv[i], "--bytes") && i + 1 < argc) g_bytes = parse_size(argv[++i]);
        else if (!strcmp(argv[i], "--threads") && i + 1 < argc) g_threads = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--mode") && i + 1 < argc) g_mode = argv[++i];
        else if (!strcmp(argv[i], "--chunk") && i + 1 < argc) g_chunk = parse_size(argv[++i]);
        else if (!strcmp(argv[i], "--drop")) drop = 1;
        else {
            printf("usage: %s --file F [--bytes 32g] [--threads 6] [--mode fread|pread|direct|directbuf] [--chunk 16m] [--drop]\n"
                   "  --drop  読む前に、そのファイルのページキャッシュを捨てる (posix_fadvise DONTNEED。root 不要)\n",
                   argv[0]);
            return !strcmp(argv[i], "-h") || !strcmp(argv[i], "--help") ? 0 : 2;
        }
    }
    if (!g_file) { fprintf(stderr, "--file が必要です\n"); return 2; }
    g_bytes -= g_bytes % g_layer;

    // 読み先: 透過的ヒュージページを勧め、全ページに触れておく (Strata は読み込み前に arena 全体を固定済み)
    g_dst = mmap(NULL, g_bytes, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (g_dst == MAP_FAILED) die("mmap");
    madvise(g_dst, g_bytes, MADV_HUGEPAGE);
    memset(g_dst, 1, g_bytes);

    if (drop) {
        const int fd = open(g_file, O_RDONLY);
        if (fd < 0) die("open (drop)");
        posix_fadvise(fd, 0, (off_t) g_bytes, POSIX_FADV_DONTNEED);
        close(fd);
    }

    pthread_t* th = calloc((size_t) g_threads, sizeof *th);
    const double t0 = now();
    for (int i = 0; i < g_threads; ++i) pthread_create(&th[i], NULL, worker, NULL);
    for (int i = 0; i < g_threads; ++i) pthread_join(th[i], NULL);
    const double sec = now() - t0;
    printf("mode=%-6s threads=%2d %s bytes=%.1fGiB time=%.2fs rate=%.2f GiB/s\n", g_mode, g_threads,
           drop ? "cold" : "warm", g_bytes / (double) (1ull << 30), sec, g_bytes / (double) (1ull << 30) / sec);
    return 0;
}
