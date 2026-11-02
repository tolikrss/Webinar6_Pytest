"""
test_firmware_cli.py — власні автотести для ESP32 Serial JSON CLI (Webinar 6, homework).

Що покрито (за умовами ДЗ):
  1. Три власні автотести на різні функції системи:
       - test_status_reflects_led_command      (SET LED -> STATUS, Req 2, 4)
       - test_status_reflects_pwm_command      (SET PWM -> STATUS, Req 2, 5)
       - test_every_command_returns_one_json_line (протокол: 1 команда = 1 JSON-рядок, Req 1-4, 7, 8)
       - бонус: test_reset_from_any_state_restores_safe_outputs (RESET зі станів LED/PWM, Req 7)
  2. Negative:  test_negative_invalid_input_rejected_without_side_effects (Req 6, 8)
  3. Boundary:  test_boundary_pwm_range_and_int32_limits                 (Req 5, 6)
  4. Усі тести використовують @pytest.mark.parametrize.
  5. Timeout:   test_timeout_is_finite_and_link_recovers,
                test_timeout_response_latency_below_client_timeout     (Req 9)

Принципи:
  - Black-box: oracle береться лише з requirements/device_requirements.md.
  - Контрольований precondition/cleanup через фікстуру `dut` (SET LED OFF),
    бо RESET сам є об'єктом перевірки (Req 7) і не може бути єдиним cleanup.
  - Evidence: кожен обмін друкується як TX>/RX< з сирими байтами;
    pytest показує цей вивід у звіті для кожного FAIL.

Запуск (з каталогу automation):
    export DEVICE_PORT=/dev/ttyUSB0        # Windows: $env:DEVICE_PORT="COM5"
    pytest tests/test_firmware_cli.py -v
"""

import json
import time

import pytest

# Відоме проміжне значення всередині 0..100, яке приймають обидві прошивки.
# Використовується як "мітка стану": після відхиленої команди STATUS має лишитися таким самим.
PWM_PRESET = 25

# Таймаут клієнта, з яким conftest.py створює Device (Device(port, timeout=1.0)).
CLIENT_TIMEOUT_S = 1.0


# --------------------------------------------------------------------------- helpers

def send(device, command):
    """Act + Evidence: надіслати команду, надрукувати сирий обмін, розпарсити JSON.

    Невалідний JSON -> pytest.fail з raw-відповіддю (а не голий JSONDecodeError),
    щоб у звіті одразу було видно, ЩО саме повернув пристрій.
    """
    raw = device.command_raw(command)
    print(f"TX> {command!r}\nRX< {raw!r}")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        pytest.fail(f"Invalid JSON for {command!r}: raw={raw!r} ({exc})")


def snapshot(device):
    """Поточний стан виходів за STATUS: (led, pwm)."""
    st = send(device, "STATUS")
    assert st["status"] == "OK", f"STATUS failed: {st}"
    return st["led"], st["pwm"]


# --------------------------------------------------------------------------- fixture

@pytest.fixture
def dut(device):
    """Device Under Test у відомому безпечному стані.

    Precondition: SET LED OFF (явний перехід у LED OFF / PWM 0).
    Cleanup:      SET LED OFF ще раз, незалежно від результату тесту.
    RESET з conftest.py виконується після цього, але на нього не покладаємось.
    """
    r = send(device, "SET LED OFF")
    assert r == {"status": "OK", "led": False}, f"precondition failed: {r}"
    yield device
    send(device, "SET LED OFF")


# =========================================================================== 1. Власні автотести

@pytest.mark.parametrize(
    "command, expected_led",
    [("SET LED ON", True), ("SET LED OFF", False)],
    ids=["led-on", "led-off"],
)
def test_status_reflects_led_command(dut, command, expected_led):
    """Req 2 + 4: відповідь на SET LED і наступний STATUS повідомляють той самий стан LED."""
    if not expected_led:                      # для OFF спершу вмикаємо, щоб перевірити саме перехід
        send(dut, "SET LED ON")

    r = send(dut, command)
    assert r["status"] == "OK"
    assert r["led"] is expected_led

    led, _pwm = snapshot(dut)
    assert led is expected_led, f"STATUS.led={led} after {command!r}"


@pytest.mark.parametrize("value", [0, 1, 50, 99], ids=lambda v: f"pwm={v}")
def test_status_reflects_pwm_command(dut, value):
    """Req 2 + 5: після SET PWM N стан PWM у STATUS реально змінюється.

    Requirements не задають одиниць поля STATUS.pwm (відсоток 0..100 чи duty 0..255),
    тому oracle навмисно не залежить від шкали:
      N == 0  -> pwm == 0 і LED вимкнено (безпечний стан);
      N  > 0  -> pwm > 0;
      heap присутній і є додатним цілим.
    """
    send(dut, f"SET PWM {PWM_PRESET}")       # стан, відмінний від цільового для value=0

    r = send(dut, f"SET PWM {value}")
    assert r["status"] == "OK"
    assert r["pwm"] == value

    st = send(dut, "STATUS")
    assert isinstance(st.get("heap"), int) and st["heap"] > 0, f"heap: {st}"
    if value == 0:
        assert st["pwm"] == 0 and st["led"] is False, f"PWM 0 must be OFF: {st}"
    else:
        assert st["pwm"] > 0, f"PWM {value} not reflected in STATUS: {st}"


@pytest.mark.parametrize(
    "command",
    ["PING", "STATUS", "GET TEMP", "SET LED ON", "SET LED OFF",
     "SET PWM 10", "RESET", "HELLO"],
)
def test_every_command_returns_one_json_line(dut, command):
    """Протокольний контракт: одна команда -> рівно один валідний JSON-рядок
    з полем status in {OK, ERROR}; після нього в буфері нічого не лишається
    (немає 'хвостів', які зламають наступний обмін)."""
    r = send(dut, command)
    assert r.get("status") in {"OK", "ERROR"}, f"no/unknown status: {r}"

    time.sleep(0.1)                            # даємо пристрою шанс надіслати зайве
    leftover = dut.ser.read(dut.ser.in_waiting or 0)
    assert leftover == b"", f"extra bytes after {command!r}: {leftover!r}"


@pytest.mark.parametrize(
    "setup_commands",
    [["SET LED ON"], ["SET PWM 1"], ["SET PWM 50"], ["SET PWM 99"], ["SET LED OFF"]],
    ids=["after-led-on", "after-pwm-1", "after-pwm-50", "after-pwm-99", "already-safe"],
)
def test_reset_from_any_state_restores_safe_outputs(dut, setup_commands):
    """Бонус, Req 7 (stateful): RESET з будь-якого стану виходів -> LED OFF / PWM 0,
    і STATUS це підтверджує (відповідь 'reset: true' сама по собі не є доказом)."""
    for cmd in setup_commands:
        assert send(dut, cmd)["status"] == "OK"

    r = send(dut, "RESET")
    assert r["status"] == "OK"

    assert snapshot(dut) == (False, 0), "RESET did not restore safe output state"


# =========================================================================== 2. Negative test

@pytest.mark.parametrize(
    "bad_command, allowed_codes",
    [
        ("SET PWM abc",   {"INVALID_VALUE"}),
        ("SET PWM 5.5",   {"INVALID_VALUE"}),
        ("SET PWM +5",    {"INVALID_VALUE"}),
        ("SET PWM 1e2",   {"INVALID_VALUE"}),
        ("SET PWM 0x10",  {"INVALID_VALUE"}),
        ("SET PWM 50 50", {"INVALID_VALUE"}),
        ("SET PWM -0",    {"INVALID_VALUE"}),
        ("SET PWM",       {"INVALID_VALUE", "UNKNOWN_COMMAND"}),
        ("SET LED BLINK", {"INVALID_VALUE", "UNKNOWN_COMMAND"}),
        ("set pwm 50",    {"UNKNOWN_COMMAND"}),
        ("PWM 50",        {"UNKNOWN_COMMAND"}),
        ("",              {"UNKNOWN_COMMAND"}),
    ],
    ids=["alpha", "float", "plus-sign", "exponent", "hex", "two-args", "minus-zero",
         "missing-arg", "led-bad-arg", "lowercase", "no-verb", "empty-line"],
)
def test_negative_invalid_input_rejected_without_side_effects(dut, bad_command, allowed_codes):
    """Req 6 + 8: некоректний ввід -> структурована помилка, і стан виходів НЕ змінюється."""
    send(dut, f"SET PWM {PWM_PRESET}")
    before = snapshot(dut)

    r = send(dut, bad_command)
    assert r["status"] == "ERROR", f"{bad_command!r} was accepted: {r}"
    assert r.get("code") in allowed_codes, f"unexpected code: {r}"

    after = snapshot(dut)
    assert after == before, f"state changed by {bad_command!r}: {before} -> {after}"


# =========================================================================== 3. Boundary test

@pytest.mark.parametrize(
    "value, accepted",
    [
        # межі робочого діапазону 0..100 (Req 5/6)
        (-1, False), (0, True), (1, True), (99, True), (100, True), (101, False),
        # межі типу int32 на ESP32: переповнення не має "загортати" значення у 0..100
        (2147483647, False),          # INT32_MAX
        (2147483648, False),          # INT32_MAX + 1
        (4294967296, False),          # 2^32       -> 0   при обрізанні до 32 біт
        (4294967396, False),          # 2^32 + 100 -> 100 при обрізанні до 32 біт
    ],
    ids=lambda p: str(p) if not isinstance(p, bool) else ("accept" if p else "reject"),
)
def test_boundary_pwm_range_and_int32_limits(dut, value, accepted):
    """Req 5 + 6: значення на межах і біля меж; для кожного перевіряємо і відповідь, і STATUS."""
    send(dut, f"SET PWM {PWM_PRESET}")
    before = snapshot(dut)

    r = send(dut, f"SET PWM {value}")

    if accepted:
        assert r == {"status": "OK", "pwm": value}, f"valid {value} rejected: {r}"
        led, pwm = snapshot(dut)
        assert (pwm == 0) == (value == 0), f"STATUS pwm={pwm} after SET PWM {value}"
    else:
        assert r == {"status": "ERROR", "code": "INVALID_VALUE"}, f"invalid {value}: {r}"
        assert snapshot(dut) == before, f"rejected {value} changed state"


# =========================================================================== 5. Timeout

@pytest.mark.parametrize("timeout_s", [0.2, 0.5, 1.0], ids=lambda t: f"{t}s")
def test_timeout_is_finite_and_link_recovers(dut, timeout_s):
    """Req 9: відсутність відповіді -> TimeoutError приблизно через заданий час (не раніше
    і не 'назавжди'); після таймауту канал придатний до роботи, без запізнілих відповідей."""
    dut.ser.timeout = timeout_s
    try:
        start = time.monotonic()
        with pytest.raises(TimeoutError):
            dut.command_raw("NO_RESPONSE")
        elapsed = time.monotonic() - start
        print(f"timeout={timeout_s}s elapsed={elapsed:.3f}s")
        assert timeout_s * 0.9 <= elapsed <= timeout_s + 0.5, f"elapsed {elapsed:.3f}s"
    finally:
        dut.ser.timeout = CLIENT_TIMEOUT_S

    r = send(dut, "PING")                     # наступна команда отримує СВОЮ відповідь
    assert r == {"status": "OK", "command": "PING"}


@pytest.mark.parametrize("command", ["PING", "STATUS", "GET TEMP", "SET PWM 10"])
def test_timeout_response_latency_below_client_timeout(dut, command):
    """Req 9 (зворотний бік): робоча команда має відповідати з запасом відносно client timeout.
    5 повторів; бюджет = 50 % таймауту, щоб нестабільна затримка не давала flaky FAIL."""
    latencies = []
    for _ in range(5):
        start = time.monotonic()
        dut.command_raw(command)
        latencies.append(time.monotonic() - start)
    worst = max(latencies)
    print(f"{command!r}: latencies ms = {[round(x * 1000, 1) for x in latencies]}")
    assert worst < CLIENT_TIMEOUT_S * 0.5, f"{command!r} worst latency {worst:.3f}s"
