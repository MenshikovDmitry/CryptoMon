import time
from monitors import (FarmChecker,
                      BinanceCheker,  
                      BlockChainLiquidityPairsTracker,
                      PCS_DeveloperMon
                     )
from utils import TelegramMessenger, CoinMarketCap, TokenTracker

#consts
import constants

import logging
logfile = "main.log"
logging.basicConfig(level = logging.INFO,filename=logfile,
                    format = u'%(filename)s %(lineno)  %(levelname)-8s %(asctime)s   %(message)s')
logger=logging.getLogger()

msgr = TelegramMessenger(constants.TELEGRAM_TOKEN)
msgr.contacts = {'chat': constants.chatid,
                 'dima': constants.dimaid}
msgr.broadcast_list = ['dima']

cmc = CoinMarketCap(constants.COIN_MARKET_CAP_API_TOKEN)
tokentracker = TokenTracker()

farmer = FarmChecker(msgr, cmc)
binance_mon = BinanceCheker(msgr, constants.BSCSCAN_API_KEY, 
                                  constants.BINANCE_API_SECRET)
pairtracker = BlockChainLiquidityPairsTracker(msgr, cmc, tokentracker, 
                                                constants.BSCSCAN_API_KEY)
pcs_dev_monitor = PCS_DeveloperMon(msgr, tokentracker, cmc, constants.BSCSCAN_API_KEY, )


bots = [farmer, binance_mon, pairtracker, pcs_dev_monitor]

while True:
    tokentracker.refresh_bnb_price()
    for bot in bots:
        try:
            bot.updates()
        except Exception as e:
            print("ERROR\n", bot.caption)
            print(e)
            print('-'*10)
    
    print('.', end="")        
        
    time.sleep(60)