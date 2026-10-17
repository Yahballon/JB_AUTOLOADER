// SPDX-License-Identifier: GPL-3.0-or-later
//
// JAILBREAK ME — experimental native PS5 eboot (PPSA99767).
// The browser launcher call is derived from Yahballon/PS5-DevBridge,
// particularly loader/browser_open.cpp and app/src/browser_launcher.hpp.
//
// Intended for ALREADY debug-enabled/jailbroken consoles. An unsigned/debug
// fPKG cannot bootstrap the initial ability to run unsigned code on retail.
// Browser launch from a SANDBOXED app remains unverified: DevBridge does this
// from a privileged daemon. This code never claims success if the service
// refuses the request.

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <cerrno>
#include <cstdarg>
#include <dlfcn.h>
#include <sys/stat.h>
#include <unistd.h>

extern "C" {
int sceNetInit(void);
int sceNetSocket(const char *, int, int, int);
int sceNetBind(int, const void *, unsigned);
int sceNetListen(int, int);
int sceNetAccept(int, void *, unsigned *);
int sceNetRecv(int, void *, size_t, int);
int sceNetSend(int, const void *, size_t, int);
int sceNetSocketClose(int);
int sceSystemServiceHideSplashScreen(void);
int sceKernelUsleep(unsigned int);
}

namespace {
constexpr int kPort = 18181;
constexpr char kBrowserUrl[] = "http://127.0.0.1:18181/app/index.html";
constexpr char kWebRoot[] = "/app0/assets/web";
constexpr char kLogFolder[] = "/data/jailbreak-me-pkg";
constexpr char kLogFile[] = "/data/jailbreak-me-pkg/launch.log";

struct Address {
  std::uint8_t length, family;
  std::uint16_t port;
  std::uint32_t ip;
  std::uint16_t vport;
  std::uint8_t reserved[6];
};
static_assert(sizeof(Address) == 16);
static std::uint16_t network16(std::uint16_t x) {
  return static_cast<std::uint16_t>((x << 8) | (x >> 8));
}
static void log_line(const char* fmt, ...) {
  char text[700]{};
  va_list args;
  va_start(args, fmt);
  std::vsnprintf(text, sizeof(text), fmt, args);
  va_end(args);
  std::printf("[JBM-PKG] %s\n", text);
  std::fflush(stdout);
  // Logging is best effort; never fail to boot if this folder is protected.
  mkdir(kLogFolder, 0755);
  if (FILE* f = std::fopen(kLogFile, "a")) {
    std::fprintf(f, "%s\n", text);
    std::fclose(f);
  }
}
static bool write_all(int socket, const char* buf, size_t len) {
  while (len) {
    const int sent = sceNetSend(socket, buf, len, 0);
    if (sent <= 0) return false;
    buf += sent;
    len -= static_cast<size_t>(sent);
  }
  return true;
}
static const char* mime(const char* path) {
  if (const char* dot = std::strrchr(path, '.')) {
    if (!std::strcmp(dot, ".html")) return "text/html; charset=utf-8";
    if (!std::strcmp(dot, ".js") || !std::strcmp(dot, ".mjs")) return "application/javascript";
    if (!std::strcmp(dot, ".css")) return "text/css";
    if (!std::strcmp(dot, ".json")) return "application/json";
    if (!std::strcmp(dot, ".appcache")) return "text/cache-manifest";
    if (!std::strcmp(dot, ".svg")) return "image/svg+xml";
    if (!std::strcmp(dot, ".png")) return "image/png";
    if (!std::strcmp(dot, ".jpg") || !std::strcmp(dot, ".jpeg")) return "image/jpeg";
    if (!std::strcmp(dot, ".woff2")) return "font/woff2";
    if (!std::strcmp(dot, ".wasm")) return "application/wasm";
  }
  return "application/octet-stream";
}
static void reply_error(int fd, int code, const char* reason) {
  char h[240]{};
  const int length = std::snprintf(h, sizeof(h),
    "HTTP/1.1 %d %s\r\nContent-Length: 0\r\nConnection: close\r\nCache-Control: no-store\r\n\r\n",
    code, reason);
  if (length > 0 && static_cast<size_t>(length) < sizeof(h))
    write_all(fd, h, static_cast<size_t>(length));
}
static void serve(int fd) {
  char request[2048]{};
  const int n = sceNetRecv(fd, request, sizeof(request) - 1, 0);
  if (n <= 0) return;
  request[n] = '\0';
  if (std::strncmp(request, "GET ", 4) != 0) {
    reply_error(fd, 405, "Method Not Allowed");
    return;
  }
  char* path = request + 4;
  char* end = std::strchr(path, ' ');
  if (!end || end - path > 900 || *path != '/') {
    reply_error(fd, 400, "Bad Request");
    return;
  }
  *end = '\0';
  if (char* q = std::strchr(path, '?')) *q = '\0';
  // Reject encoded separators, traversal, backslashes and internal files.
  if (std::strstr(path, "..") || std::strchr(path, '%') ||
      std::strchr(path, '\\') || std::strstr(path, "//") ||
      !std::strcmp(path, "/VERSION")) {
    reply_error(fd, 403, "Forbidden");
    return;
  }
  if (!std::strcmp(path, "/")) path = const_cast<char*>("/app/index.html");
  char filename[1100]{};
  std::snprintf(filename, sizeof(filename), "%s%s", kWebRoot, path);
  struct stat st{};
  if (stat(filename, &st) != 0 || !S_ISREG(st.st_mode) || st.st_size < 0) {
    reply_error(fd, 404, "Not Found");
    return;
  }
  FILE* file = std::fopen(filename, "rb");
  if (!file) { reply_error(fd, 500, "Internal Server Error"); return; }
  char response[512]{};
  int nh = std::snprintf(response, sizeof(response),
    "HTTP/1.1 200 OK\r\nContent-Type: %s\r\nContent-Length: %llu\r\n"
    "Connection: close\r\nAccess-Control-Allow-Origin: http://127.0.0.1:18181\r\n"
    "Cache-Control: no-cache\r\n\r\n",
    mime(path), static_cast<unsigned long long>(st.st_size));
  if (nh <= 0 || static_cast<size_t>(nh) >= sizeof(response) ||
      !write_all(fd, response, static_cast<size_t>(nh))) {
    std::fclose(file); return;
  }
  char buffer[16384];
  for (;;) {
    const size_t got = std::fread(buffer, 1, sizeof(buffer), file);
    if (got == 0 || !write_all(fd, buffer, got)) break;
  }
  std::fclose(file);
}
static int open_browser() {
  // Uses the API that DevBridge successfully calls from its resident ELF
  // payload. Whether it can be invoked directly by this app is the test.
  void* usersvc = dlopen("libSceUserService.sprx", RTLD_LAZY);
  void* syssvc = dlopen("libSceSystemService.sprx", RTLD_LAZY);
  using InitFn = int (*)(void*);
  using OpenFn = int (*)(const char*, void*);
  using TermFn = int (*)();
  auto init = usersvc ? reinterpret_cast<InitFn>(dlsym(usersvc, "sceUserServiceInitialize")) : nullptr;
  auto open = syssvc ? reinterpret_cast<OpenFn>(dlsym(syssvc, "sceSystemServiceLaunchWebBrowser")) : nullptr;
  auto term = usersvc ? reinterpret_cast<TermFn>(dlsym(usersvc, "sceUserServiceTerminate")) : nullptr;
  if (!init || !open || !term) {
    log_line("BROWSER_EXPORTS_UNAVAILABLE (sandbox may block direct launch)");
    return -1;
  }
  const int urc = init(nullptr);
  if (urc < 0 && static_cast<unsigned>(urc) != 0x80960003u) {
    log_line("USER_SERVICE_FAILED code=0x%08x", static_cast<unsigned>(urc));
    return urc;
  }
  const int rc = open(kBrowserUrl, nullptr);
  if (urc == 0) term();
  log_line("BROWSER_LAUNCH url=%s rc=0x%08x", kBrowserUrl, static_cast<unsigned>(rc));
  return rc;
}
}  // namespace

int main() {
  log_line("BOOT JAILBREAK ME experimental native PKG launcher / PPSA99767");
  log_line("EXPERIMENTAL: direct browser launch from app sandbox is unverified");
  const int net = sceNetInit();
  log_line("NET_INIT rc=0x%08x", static_cast<unsigned>(net));
  if (net < 0) return 1;
  int fd = sceNetSocket("jbm_offline", 2, 1, 6);
  if (fd < 0) { log_line("SERVER_SOCKET_FAILED code=%d", fd); return 1; }
  Address address{sizeof(Address), 2, network16(kPort), 0x0100007fu, 0, {}};
  int rc = sceNetBind(fd, &address, sizeof(address));
  if (rc < 0) {
    log_line("SERVER_BIND_FAILED rc=%d (port 18181 occupied?)", rc);
    sceNetSocketClose(fd);
    return 1;
  }
  rc = sceNetListen(fd, 8);
  if (rc < 0) {
    log_line("SERVER_LISTEN_FAILED rc=%d", rc);
    sceNetSocketClose(fd);
    return 1;
  }
  log_line("SERVER_READY url=%s", kBrowserUrl);
  sceSystemServiceHideSplashScreen();
  rc = open_browser();
  if (rc != 0) {
    // Fail visibly in the log instead of claiming the exploit started.
    log_line("BROWSER_NOT_STARTED: manual actions NOT required by this prototype;"
             " debug log will report what native service refused");
  }
  for (;;) {
    Address client{};
    unsigned client_len = sizeof(client);
    int peer = sceNetAccept(fd, &client, &client_len);
    if (peer >= 0) {
      serve(peer);
      sceNetSocketClose(peer);
    } else {
      // Back off on resource exhaustion, preserving the server's memory.
      sceKernelUsleep(100000);
    }
  }
  return 0;
}
