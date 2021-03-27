# CryptoMon
---
Binance Smart Chain tracker:
- Monitors new farms at PancakeSwap by parsing the page source
- Monitors new traiding pairs at binance.com
- Monitors new transactions to PancakeSwap main staking account
- Reporting through telegram
- powered by bscScan & CoinMarketCap
- ~~содержит говнокод~~ !average code quality!
- 
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
