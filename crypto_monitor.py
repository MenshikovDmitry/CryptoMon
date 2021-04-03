import time
from monitors import (FarmChecker,
                      BinanceCheker,  
                      BlockChainLiquidityPairsTracker,
                     )
from utils import TelegramMessenger, CoinMarketCap, TokenTracker

#consts
import constants

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

bots = [farmer, binance_mon, pairtracker]

while True:
    for bot in bots:
        try:
            bot.updates()
        except Exception as e:
            print("ERROR\n", bot.caption)
            print(e)
            print('-'*10)
    
    print('.', end="")        
        
    time.sleep(60)