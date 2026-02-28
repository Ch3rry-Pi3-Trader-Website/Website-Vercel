from src.strategies.breakout import Breakout
from src.strategies.mean_reversion import BollingerMeanReversion
from src.strategies.momentum import Momentum


REGISTRY = {
    "momentum": Momentum,
    "mean_reversion": BollingerMeanReversion,
    "breakout": Breakout,
}
