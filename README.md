# CryptoMon
---
**!ATTENTION!**
_Hey guys, thanks for visiting this repo. Sorry, I no longer keep developing it. Instead, I am working on hidden fork with some advanced features and signals. If you are interested, please, feel free to join the telegram chat with signals from this bot:_ https://t.me/joinchat/HTdk31mnFcEiU2fp
_So far it is free of charge_ :)
---
  
I know which new farms are coming on pancakeswap beforehand ;)

**Binance Smart Chain tracker**:
- Monitors new farms at PancakeSwap.finance by parsing the web page source
- Monitors new traiding pairs at binance.com
- Monitors new transactions to PancakeSwap main staking account
- Monitors in and out transactions of pancakeswap developers
- Monitors creations of new SmartChief contracts (New Farms)
- Reporting through telegram
- powered by bscScan, Web3 & CoinMarketCap
- ~~содержит говнокод~~ !average code quality!

***

## Before Use:
- Download Chromedriver from https://chromedriver.chromium.org/downloads and put it to PATH. Needed for Selenium.
- Create **constants.py** with API tokens and telegram contacts.
- Update lib/python3.x/site-packages/bscscan/bscscan.py  line 2:  

from
```python
from importlib import resources
```
to
```python
import importlib_resources as resources
```
Otherwise it will not work.
