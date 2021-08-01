![](https://img.shields.io/pypi/l/project.svg)
![](https://img.shields.io/coveralls/github/ztomsy/ibtwsbot.svg)
# ibtwsbot

Example [IB_insync](https://github.com/erdewit/ib_insync) bot 
for [Trader Workstation API](https://interactivebrokers.github.io/tws-api/index.html)
with [Hydra](https://hydra.cc/)

## Installation

Ensure you have git2.2 and python3.8 and higher installed.

Clone the repository.

Activate virtual environments and install requirements.

Edit config.yaml file.  

## Usage

### Example use case

Iterate on each timeframe:
```text
+----------------------------+  +----------------------------+  +----------------------------+
| Scan For Stock In Scanner  |  | Check Open Orders          |  | Check Positions            |
|                            |  |                            |  |                            |
+-------------+--------------+  +-------------+--------------+  +-------------+--------------+
              |                               |                               |
              v                               v                               v
+-------------+--------------+  +-------------+--------------+  +-------------+--------------+
| Check If Stock Not In Open |  | If Order Not Good (Terms)  |  | If New Terms Close         |
| Orders Or In Positions     |  | Cancel It                  |  |                            |
+-------------+--------------+  +----------------------------+  +----------------------------+
              |
              v
+-------------+--------------+
| Check Terms For Each Stock |
|                            |
+--^----------+--------------+
   |          |
   |          v
   |      +---+---+   Yes  +--------------------+
   +------+ Terms +------->+ Transmit New Order |
          +-------+        +--------------------+
```

## Tests

You can run tests by running `python -m unittest discover test`. 
Code coverage is enabled by default.

