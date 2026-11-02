def test_ping(device):
    r = device.command("PING")
    assert r["status"] == "OK"
    assert r["command"] == "PING"

def test_status(device):
    r = device.command("STATUS")
    assert r["status"] == "OK"
    assert "heap" in r
    assert "pwm" in r
