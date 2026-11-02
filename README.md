# Webinar6_Pytest — Python/Pytest автотести для ESP32 Serial JSON CLI

Домашнє завдання до Webinar 6 «Автоматизація на Python: пишемо автотести через Pytest».

## Що всередині

| Шлях | Опис |
|---|---|
| `automation/tests/test_firmware_cli.py` | **Нові тести** (48 кейсів, усі через `pytest.mark.parametrize`) |
| `automation/tests/test_*.py` | Базовий suite з вебінару (14 кейсів) |
| `automation/device.py`, `conftest.py` | Serial-хелпер і фікстура `device` (з вебінару, без змін) |
| `tools/host_emulator/` | Запуск `sketch.ino` без змін на host-моделі ESP32 з virtual serial — для прогону без Wokwi/плати |
| `results/` | Логи pytest, JUnit XML, serial-трейси, повторюваність |
| `docs/` | Заповнений Test Sheet (Execution Log, FAIL Classification, Bug Reports, Test Summary) |

### Нові тести (`test_firmware_cli.py`)

| Вимога ДЗ | Тест | Кейси |
|---|---|---|
| 3 власні автотести | `test_status_reflects_led_command`, `test_status_reflects_pwm_command`, `test_every_command_returns_one_json_line` | 2 + 4 + 8 |
| бонус | `test_reset_from_any_state_restores_safe_outputs` | 5 |
| 1 negative | `test_negative_invalid_input_rejected_without_side_effects` | 12 |
| 1 boundary | `test_boundary_pwm_range_and_int32_limits` | 10 |
| timeout | `test_timeout_is_finite_and_link_recovers`, `test_timeout_response_latency_below_client_timeout` | 3 + 4 |

## Запуск

```bash
cd automation
python -m pip install -r requirements.txt
export DEVICE_PORT=/dev/ttyUSB0          # Windows PowerShell: $env:DEVICE_PORT="COM5"
pytest -v                                # увесь suite
pytest tests/test_firmware_cli.py -v     # лише нові тести
pytest -k "negative or boundary or timeout" -v
```

Serial Monitor має бути закритий, поки pytest тримає порт.

## Результати

| Firmware | Результат |
|---|---|
| `demo_firmware` (контроль) | 62 / 62 PASS |
| `homework_buggy` | 53 PASS / 9 FAIL, стабільно 3/3 прогони |

Усі 9 FAIL зводяться до трьох firmware-дефектів:

| Bug | Req | Severity | Суть |
|---|---|---|---|
| BUG-01 | 5 | Major | `SET PWM 100` → `INVALID_VALUE` (межа зсунута, фактично 0..99) |
| BUG-02 | 3 | Major | `GET TEMP` при валідному показі → `{"status":"OK","temperature":24.5` без `}` |
| BUG-03 | 7 | Critical | `RESET` повертає `reset:true`, але LED/PWM лишаються увімкненими |

Відкрите питання до вимог: `STATUS.pwm` повертає duty 0..255 (`SET PWM 50` → `pwm:127`), а `SET PWM` приймає 0..100; Req 2 одиниць не визначає.

Прогін виконано на host-моделі ESP32 (`tools/host_emulator`, sketch без змін). Для фінального evidence ці самі тести треба запустити у Wokwi або на платі.
