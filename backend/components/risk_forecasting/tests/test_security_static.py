from pathlib import Path

def test_reset_endpoint_removed():
    main_path = Path(__file__).resolve().parent.parent.parent.parent / "main.py"
    source = main_path.read_text(encoding="utf-8")
    assert "/reset-pramod-password" not in source, "The unsafe reset endpoint was not removed!"
