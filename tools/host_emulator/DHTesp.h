#pragma once
#include "Arduino.h"
struct TempAndHumidity { float temperature; float humidity; };
class DHTesp {
public:
  enum DHT_MODEL_t { AUTO_DETECT, DHT11, DHT22, AM2302, RHT03 };
  void setup(int, DHT_MODEL_t) {}
  TempAndHumidity getTempAndHumidity() {
    const char *t = getenv("EMU_TEMP");          // default = Wokwi diagram value 24.5
    float v = t ? (strcmp(t, "nan") == 0 ? NAN : (float)atof(t)) : 24.5f;
    return {v, 45.0f};
  }
};
