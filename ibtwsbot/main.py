from logging import (INFO, getLogger)
import sys
from omegaconf import DictConfig
import hydra

from .bot import Tbot


if not sys.warnoptions:
    import warnings; warnings.simplefilter("ignore")


@hydra.main(config_name="config")
def main(cfg: DictConfig) -> None:
    log = getLogger(__name__)
    log.setLevel(INFO)
    try:
        bot = Tbot(log, **cfg)
        bot.run_bot()
    except (KeyboardInterrupt, SystemExit):
        log.info(f'Shutdown application')
    except Exception as e:
        log.error(e.__doc__)


def init():
  if __name__ == "__main__":
    sys.exit(main())


init()

