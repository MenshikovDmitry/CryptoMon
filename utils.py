import requests
import re
import datetime
import json
import os

#telegram
import telebot

#for API
from requests import Request, Session
from requests.exceptions import ConnectionError, Timeout, TooManyRedirects

from bscscan import BscScan

#Web3 for direct access to Blockchain
from web3 import Web3

#constants
import constants


def bscscan_token_info(token_address):
    url = 'https://bscscan.com/token/'+token_address
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'}
    try:
        result = requests.get(url, headers=headers)
    except Exception as e:
        print("Unable to obtain token info from bscScan with", e)
        print(url)
        return None
    result = result.content.decode()
    #matches to <head><title> TokenName (TOKENSYMBOL) Token Tracker | BscScan </title>
    pattern = "<head><title>\r\n\t([A-Za-z\.\- ]+)\(([A-Za-z]+)\) Token Tracker \| BscScan\r\n</title>"
    match = re.findall(string = result, pattern = pattern)
    if len(match)==0:
        print("Can't parse..")
        print(result[:result.find("title><meta")])
        return None
    return match[0]


class TelegramMessenger:
    def __init__(self, TOKEN):
        self.bot = telebot.TeleBot(TOKEN, parse_mode='Markdown')
        self.contacts = {}
        self.broadcast_list = []
#------------------------------------------------------------------------
    def broadcast(self, feed):
        for uid in self.broadcast_list:
            for message in feed:
                if len(message.split())>0:
                    self.bot.send_message(self.contacts[uid], message, disable_web_page_preview=True)

#========================================================================
#========================================================================

class Messenger:
    def __init__(self):
        pass
    def broadcast(self, feed):
        for f in feed:
            print(f)

#==========================================================================================
#==========================================================================================

class TokenTracker:
    def __init__(self):
        self.filename = "_w3_token_tracker_data.json"
        self.caption = "====Token Tracker===="
        self.data = self.load_data()
        if not self.data: 
            self.data = {}
            print("No data loaded")
        bsc = constants.binance_smart_chain
        self.w3 = Web3(Web3.HTTPProvider(bsc))
#------------------------------------------------------------------------
    
    def save_data(self):
        filename = self.filename
        data = {'data': self.data}
        data['time'] = f"{datetime.datetime.now().replace(microsecond=0)}"
        with open(filename, "w") as fp:
            json.dump(data , fp)
#------------------------------------------------------------------------

    def load_data(self, filename=None):
        if not filename:
            filename = self.filename
        if not os.path.exists(filename):
            return None
        with open(filename) as fp:
            data = json.load(fp)
        print(self.caption)
        print(f"Loaded {filename}, timestamp: {data['time']}")
        return data['data']            
#------------------------------------------------------------------------

    def swap_rate(self, from_token, to_token, liq_pool):
        fee = 0.003
        lp_contract = self.w3.eth.contract(address=liq_pool, abi=constants.lp_abi) 
        t0_address = lp_contract.functions.token0().call()
        t1_address = lp_contract.functions.token1().call()

        t0_bal, t1_bal, *_ = lp_contract.functions.getReserves().call()

        rate = t1_bal/t0_bal

        if from_token==t0_address and to_token==t1_address:
            return rate*(1-fee)

        if from_token==t1_address and to_token==t0_address:
            return 1/rate * (1-fee)

        raise "WTF"
#------------------------------------------------------------------------

    def token(self, token_address, force = False):

        #check that the address is correct
        try:
            t_address = self.w3.toChecksumAddress(token_address)
        except Exception as e:
            print(f"{token_address} is not a correct address", e)
            return None

        if '0000000000000000000000000000000000' in t_address:
            #blank stuff, no idea
            return None

        #lookup in dict
        token = self.data.get(t_address, None)

        if force: token=None # downloading new data either way
        if token: return token
        
        #lookup in blockchain
        assert self.w3.isConnected() 
        token = self.w3.eth.contract(address=t_address, abi = constants.token_abi)
        
        print(t_address)
        token_data = {'name' : token.functions.name().call(),
                      'symbol': token.functions.symbol().call(),
                      'address': t_address,
                      'pair' : None,
                      'subtokens': None,}       
       
        #Liquidity pair
        if token_data['symbol'] in ["Cake-LP", ]:
            token = self.w3.eth.contract(address=t_address, abi = constants.lp_abi)
            t0_address = token.functions.token0().call()
            t1_address = token.functions.token1().call()
            
            t0_data = self.token(t0_address)
            t1_data = self.token(t1_address)
            
            token_data['pair'] = f"{t0_data['symbol']}%{t1_data['symbol']}"
            token_data['subtokens'] = [t0_data, t1_data]
            token_data['rate'] = self.swap_rate(t0_address, t1_address, t_address)
            token_data['timestamp'] = f"{datetime.datetime.now().replace(microsecond=0)}"
            
        self.data[self.w3.toChecksumAddress(t_address)] = token_data
        self.save_data()
        return token_data        
#==========================================================================================
#==========================================================================================


CMC_API_KEY = constants.COIN_MARKET_CAP_API_TOKEN
class CoinMarketCap:
    def __init__(self, api_key, test_mode=False):
        self.api_key = api_key
        self.data = self.load_data()
        self.timestamp = datetime.datetime.now()
        self.ignore = ['bnb', 'btc', 'eth', 'cake', 'busd', 'wbnb']
        self.test_mode = test_mode # use existing data with no refresh
        
    def load_data(self):
        url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest'
        parameters = {
        #  'start':'1',
          'limit':'5000',
        #  'convert':'USD'
        }
        headers = {
          'Accepts': 'application/json',
          'X-CMC_PRO_API_KEY': self.api_key,
        }

        session = Session()
        session.headers.update(headers)

        try:
            response = session.get(url, params=parameters)
            data = json.loads(response.text)
            #print(data)
        except (ConnectionError, Timeout, TooManyRedirects) as e:
            print(e)
        return data['data']
    
    def smart_refresh(self):
        if self.test_mode: return 
        age = datetime.datetime.now() - self.timestamp
        if age.seconds > 60*5:
            self.refresh()
    
    def refresh(self):
        self.data = self.load_data()
        self.timestamp =datetime.datetime.now()
        
    def report(self, symbol):
        self.smart_refresh()
        cmc_url="https://coinmarketcap.com/currencies/"
        tokens = [d for d in self.data if d['symbol'].lower()==symbol.lower()]
        report=""
        # sometimes there is an extra 'b'. If there is no result, check without it
        if len(tokens)==0:
            tokens = [d for d in self.data if d['symbol'].lower()==symbol.lower()[1:]]
        if len(tokens)==0:
            return f"CMC: No Data available for {symbol}"
        for d in tokens:
            if d['symbol'].lower() in self.ignore:
                report+= f"[CMC:]({cmc_url}{d['slug']}) {d['symbol']} ({d['name']}), {d['num_market_pairs']} t.pairs."
                continue
            report+= f"[CMC:]({cmc_url}{d['slug']}) {d['symbol']} ({d['name']}), {d['num_market_pairs']} t.pairs,"
            if d['platform']:
                report += f" Platform: {d['platform']['name']}"
            report+= f"\nPrice: ${round(d['quote']['USD']['price'],3)}, mCap: ${int(d['quote']['USD']['market_cap']//1000000)}M,"
            report+= f"\nChng%: 1h/24h/7d/30d "
            report+= f"{int(d['quote']['USD']['percent_change_1h'])}/"
            report+= f"{int(d['quote']['USD']['percent_change_24h'])}/"
            report+= f"{int(d['quote']['USD']['percent_change_7d'])}/"
            report+= f"{int(d['quote']['USD']['percent_change_30d'])}/\n"
        return report
    
    def token(self, symbol_or_address):
        self.smart_refresh()
        if len(symbol_or_address)<6:
            tokens = [t for t in self.data if t['symbol'].lower()==symbol_or_address.lower()]
        else:
            tokens = [t for t in self.data if t['platform'] and t['platform']['token_address']==symbol_or_address]
            
        if len(tokens)>0:
            return tokens
        else: return None





if __name__=="__main__":
    pass