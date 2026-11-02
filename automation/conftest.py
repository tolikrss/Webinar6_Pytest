import os
import pytest
from device import Device

@pytest.fixture
def device():
    port = os.getenv("DEVICE_PORT")
    if not port:
        pytest.skip("Set DEVICE_PORT, e.g. COM5 or /dev/ttyUSB0")
    dev = Device(port, timeout=1.0)
    yield dev
    try:
        dev.command("RESET")
    finally:
        dev.close()
