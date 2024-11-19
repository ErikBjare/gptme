from gptme.config import get_config


def test_get_config():
    config = get_config()
    print(f"config: {config}")
    assert config
