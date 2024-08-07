from gptme.config import load_config


def test_load_config():
    config = load_config()
    print(f"config: {config}")
    assert config
