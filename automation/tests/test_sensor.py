def test_temperature_is_valid_json(device):
    r = device.command("GET TEMP")
    assert r["status"] in {"OK", "ERROR"}
    if r["status"] == "OK":
        assert -40 <= r["temperature"] <= 80
