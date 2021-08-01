import unittest
import mock
import pytest
from hydra.experimental import compose, initialize
from ibtwsbot import main


# Usage in unittest style tests is similar.
class TestGeneratedConfig(unittest.TestCase):
    def test_generated_config(self) -> None:
        with initialize(config_path="../ibtwshydra/"):
            cfg = compose(config_name="config", overrides=["script.loop_interval=20"])
        assert cfg.script.loop_interval == 20

# Test main load right config
class TestMainInitConfig(unittest.TestCase):
    def test_generated_config(self) -> None:
        with initialize(config_path="../ibtwshydra/"):
            cfg = compose(config_name="config", overrides=["script.loop_interval=20"])
        assert cfg.script.loop_interval == 20
    # Test init
    def test_init(self) -> None:
        with mock.patch.object(main, "main"):
            with mock.patch.object(main, "__name__", "__main__"):
                with mock.patch.object(main.sys, 'exit') as mock_exit:
                    with initialize(config_path="../ibtwshydra/"):
                        cfg = compose(config_name="config")
                        main.init()
                        assert mock_exit.call_args[0][0] == "30"
