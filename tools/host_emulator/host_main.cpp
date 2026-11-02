#include "Arduino.h"
#include <cstdarg>
#include <fcntl.h>
#include <poll.h>
#include <termios.h>
#include <unistd.h>
#include <time.h>

HostSerial Serial;
EspClass ESP;
static int g_pin2 = 0;
static FILE *g_log = nullptr;   // pin/serial trace (evidence)

unsigned long millis() {
  static timespec t0; static bool init = false;
  timespec t; clock_gettime(CLOCK_MONOTONIC, &t);
  if (!init) { t0 = t; init = true; }
  return (t.tv_sec - t0.tv_sec) * 1000UL + (t.tv_nsec - t0.tv_nsec) / 1000000L;
}
void delay(unsigned long ms) { usleep(ms * 1000); }
void pinMode(int, int) {}
void analogWrite(int pin, int v) {
  if (pin == 2) g_pin2 = v;
  if (g_log) { fprintf(g_log, "[%8lu ms] GPIO%d duty=%d\n", millis(), pin, v); fflush(g_log); }
}

void HostSerial::pump(int waitMs) {
  pollfd p{fd, POLLIN, 0};
  if (poll(&p, 1, waitMs) > 0 && (p.revents & POLLIN)) {
    char buf[512];
    ssize_t n = ::read(fd, buf, sizeof buf);
    if (n > 0) {
      rx.append(buf, n);
      if (g_log) { fprintf(g_log, "[%8lu ms] RX ", millis()); fwrite(buf, 1, n, g_log); fprintf(g_log, "\n"); fflush(g_log); }
    }
  } else if (waitMs > 0) {
    // no data: avoid busy loop when slave side is closed (POLLHUP)
    if (p.revents & POLLHUP) usleep(waitMs * 1000);
  }
}
int HostSerial::available() { if (rx.empty()) pump(5); return rx.size(); }
int HostSerial::read() { if (rx.empty()) return -1; int c = (unsigned char)rx[0]; rx.erase(0, 1); return c; }
String HostSerial::readStringUntil(char t) {
  String out; unsigned long start = millis();
  while (millis() - start < timeoutMs) {
    if (rx.empty()) { pump(5); continue; }
    int c = read();
    if (c == t) return out;
    out += (char)c;
  }
  return out;
}
void HostSerial::write_raw(const char *d, size_t n) {
  if (g_log) { fprintf(g_log, "[%8lu ms] TX ", millis()); fwrite(d, 1, n, g_log); if (!n || d[n-1] != '\n') fprintf(g_log, "\n"); fflush(g_log); }
  while (n) { ssize_t w = ::write(fd, d, n); if (w <= 0) { usleep(1000); continue; } d += w; n -= w; }
}
size_t HostSerial::printf(const char *fmt, ...) {
  char buf[512]; va_list ap; va_start(ap, fmt);
  int n = vsnprintf(buf, sizeof buf, fmt, ap); va_end(ap);
  write_raw(buf, n); return n;
}

void setup(); void loop();

int main(int argc, char **argv) {
  if (argc < 2) { fprintf(stderr, "usage: %s <symlink-path> [trace.log]\n", argv[0]); return 2; }
  int m = posix_openpt(O_RDWR | O_NOCTTY);
  grantpt(m); unlockpt(m);
  const char *slave = ptsname(m);
  int s = open(slave, O_RDWR | O_NOCTTY);           // keep slave open: no EIO/HUP between test sessions
  termios tio; tcgetattr(s, &tio); cfmakeraw(&tio); tcsetattr(s, TCSANOW, &tio);
  unlink(argv[1]); if (symlink(slave, argv[1]) != 0) { perror("symlink"); return 1; }
  if (argc > 2) g_log = fopen(argv[2], "w");
  Serial.fd = m;
  fprintf(stderr, "virtual serial port: %s -> %s\n", argv[1], slave); fflush(stderr);
  setup();
  for (;;) loop();
}
