// Minimal host model of the ESP32 Arduino API used by the webinar sketches.
// Serial is backed by a pseudo-terminal so the unchanged pytest suite talks to it via pyserial.
#pragma once
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <cmath>
#include <cctype>
#include <cerrno>
#include <climits>
#include <string>
using std::isnan;

class String {
  std::string s;
public:
  String() {}
  String(const char *c) : s(c ? c : "") {}
  String(const std::string &x) : s(x) {}
  unsigned int length() const { return s.size(); }
  const char *c_str() const { return s.c_str(); }
  void trim() {
    size_t b = 0, e = s.size();
    while (b < e && isspace((unsigned char)s[b])) b++;
    while (e > b && isspace((unsigned char)s[e - 1])) e--;
    s = s.substr(b, e - b);
  }
  bool operator==(const char *o) const { return s == o; }
  bool operator==(const String &o) const { return s == o.s; }
  bool startsWith(const char *p) const { return s.rfind(p, 0) == 0; }
  String substring(unsigned int from) const { return from > s.size() ? String() : String(s.substr(from)); }
  // ESP32: atol() with 32-bit long -> strtol saturates at LONG_MIN/LONG_MAX (int32)
  long toInt() const {
    errno = 0;
    long long v = strtoll(s.c_str(), nullptr, 10);
    if (v > INT32_MAX) v = INT32_MAX;
    if (v < INT32_MIN) v = INT32_MIN;
    return (long)(int32_t)v;
  }
  String &operator+=(char c) { s += c; return *this; }
  char *begin() { return &s[0]; }
  char *end() { return &s[0] + s.size(); }
  const char *begin() const { return s.data(); }
  const char *end() const { return s.data() + s.size(); }
};

class HostSerial {
public:
  int fd = -1;
  unsigned long timeoutMs = 1000;
  std::string rx;
  void begin(unsigned long) {}
  void pump(int waitMs);
  int available();
  int read();
  String readStringUntil(char t);
  void write_raw(const char *d, size_t n);
  size_t println(const String &x) { write_raw(x.c_str(), x.length()); write_raw("\r\n", 2); return x.length() + 2; }
  size_t println(const char *x) { return println(String(x)); }
  size_t printf(const char *fmt, ...) __attribute__((format(printf, 2, 3)));
};
extern HostSerial Serial;

struct EspClass { uint32_t getFreeHeap() { return 287512; } };
extern EspClass ESP;

#define OUTPUT 1
#define INPUT 0
void pinMode(int, int);
void analogWrite(int pin, int v);
void delay(unsigned long ms);
unsigned long millis();
inline bool isDigit(char c) { return c >= '0' && c <= '9'; }
inline long map(long x, long a, long b, long c, long d) { return (x - a) * (d - c) / (b - a) + c; }
