import requests
import re
import datetime
import json
import os
import logging

from multiprocessing.pool import ThreadPool

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


import time, datetime, os
from threading import Thread

#========================================================================
#========================================================================

class TelegramMessenger:
    def __init__(self, TOKEN, polling=True):
        self.bot = telebot.TeleBot(TOKEN, parse_mode='Markdown')
        self.contacts = {}
        self.broadcast_list = []
        
        #bot commands
        @self.bot.message_handler(commands=['ok'])
        def start_message(message):
            self.bot.send_message(message.chat.id, 'running')
            
        @self.bot.message_handler(commands=['files'])
        def start_message(message):
            files = [o for o in os.listdir() if o[0]=='_']
            msg = ""
            for f in files:
                delta = datetime.datetime.now() - datetime.datetime.fromtimestamp(os.path.getmtime(f))
                secs = delta.seconds
                t = f"{secs}s" if secs<120 else f"{secs//60}m"
                msg += f"\n{t} {f}"
            msg = msg.replace('_', "")
            self.bot.send_message(message.chat.id, msg, parse_mode=None)    
            
        #start the thread
        if polling:
            self.thread = Thread(target = self.bot.polling, args = ())
            self.thread.start()
#------------------------------------------------------------------------

    def message(self, chat_id, message):
        self.bot.send_message(chat_id, message, disable_web_page_preview=True)        
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
    def __init__(self, BSCSCAN_API_KEY=None):
        self.filename = "_w3_token_tracker_data.json"
        self.caption = "====Token Tracker===="
        self.data = self.load_data()
        self.base_tokens = "WBNB, BUSD"
        if BSCSCAN_API_KEY:
            self.bsc = BscScan(BSCSCAN_API_KEY)
        else:
            self.bsc = None
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
    #deprecated
    def swap_rate(self, from_token, to_token, liq_pool, fee = 0.003):
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
    #deprecated
    def fetch_pools(self, n_blocks=100):
        """fetch data about recent pools transactions"""
        assert self.bsc, "No bscscan API key provided"
        logging.info('fetching pools data')
        block = self.w3.eth.block_number
        transactions = self.bsc.get_bep20_token_transfer_events_by_address(constants.pancake_router_address,
                                    startblock = block-n_blocks,
                                    endblock = None,
                                    sort = 'asc')
        txs = [t for t in transactions if t['to']!=constants.pancake_router_address]
        new_pools = [t['to'] for t in txs if not t['to'] in self.data.keys()]
        new_pools = list(set(new_pools))

        _ = self.token(new_pools, update=False, force=False, workers=20)



#------------------------------------------------------------------------

    def pools(self, token_address):
        """List of LP pools for this token address"""
        token_address = self.w3.toChecksumAddress(token_address)
        ps = [v for k,v in self.data.items() if v['subtokens'] and (token_address == v['subtokens'][0]['address'] 
                                                                 or token_address == v['subtokens'][1]['address'])]
        if len(ps)>0:
            return ps
        #get data from the factory for WBNB and BUSD only
        factory = self.w3.eth.contract(address=constants.pancake_factory_address, abi=constants.pancake_factory_abi)

        base_tokens = [constants.WBNB_address, constants.BUSD_address]
        for bt in base_tokens:
            pool_address = factory.functions.getPair(token_address, self.w3.toChecksumAddress(bt)).call()
            if '0000000000000000' in pool_address: continue # no such pool
            _ = self.token(pool_address)
        ps = [v for k,v in self.data.items() if v['subtokens'] and (token_address == v['subtokens'][0]['address'] 
                                                                 or token_address == v['subtokens'][1]['address'])]
        return ps                                                         
#------------------------------------------------------------------------

    def token(self, token_address, update = True, force = False, workers = 10):
        if type(token_address)==str:
            #only one
            token_data = [self.get_token(token_address, update=update, force=force),]
        else:

            def get_token_wrapper(token_address):
                return self.get_token(token_address, update=update, force=force)

            p = ThreadPool(workers)
            token_data = p.map(get_token_wrapper, token_address)

        new_ones = [t for t in token_data if t and not t['address'] in self.data.keys()]

        for t in new_ones:
            self.data[t['address']] = t

        if len(new_ones)>0: self.save_data()

        if len(token_data)==1:
            return token_data[0]

        return token_data
#------------------------------------------------------------------------        

    def get_token(self, token_address, update = True, force = False):

        #check that the address is correct
        try:
            t_address = self.w3.toChecksumAddress(token_address)
        except Exception as e:
            logging.error(f"{token_address} is not a correct address: " + str(e))
            return None

        if '0000000000000000000000000000000000' in t_address:
            #blank stuff, no idea
            return None

        #lookup in dict
        token = self.data.get(t_address, None)

        #forced update
        if force: token = None

        #do not need to update
        if token and not update:
            return token
        
        # update only reserves for Liquidity pair
        if token and update and token.get('symbol', None) in ["Cake-LP", ]:
            assert self.w3.isConnected() 
            token_data = token 
            token = self.w3.eth.contract(address=t_address, abi = constants.lp_abi)
            token_data['reserves'] = token.functions.getReserves().call()[:2]
            token_data['reserves'] = [int(self.w3.fromWei(r, 'ether')) for r in token_data['reserves']]
            if token_data['reserves'][0]>0 and token_data['reserves'][1]>0:
                token_data['rate'] = token_data['reserves'][0]/token_data['reserves'][1]
            else:
                token_data['rate']=0
            token_data['timestamp'] = f"{datetime.datetime.now().replace(microsecond=0)}"     

            return token_data

        
        #lookup in blockchain
        assert self.w3.isConnected() 
        token = self.w3.eth.contract(address=t_address, abi = constants.token_abi)

        #print(t_address)
        try:
            token_data = {'name' : token.functions.name().call(),
                        'symbol': token.functions.symbol().call(),
                        'address': t_address,
                        'decimals': token.functions.decimals().call(),
                        'pair' : None,
                        'subtokens': None,}       
        except Exception as e:
            logging.warning(f"Error on Contract {t_address}:",e)
            return None
        #Liquidity pair
        if token_data['symbol'] in ["Cake-LP", ]:
            token = self.w3.eth.contract(address=t_address, abi = constants.lp_abi)
            t0_address = token.functions.token0().call()
            t1_address = token.functions.token1().call()
            
            t0_data = self.get_token(t0_address)
            t1_data = self.get_token(t1_address)
            
            token_data['pair'] = [t0_data['symbol'], t1_data['symbol']]
            token_data['subtokens'] = [t0_data, t1_data]
            token_data['reserves'] = token.functions.getReserves().call()[:2]
            token_data['reserves'] = [int(self.w3.fromWei(r, 'ether')) for r in token_data['reserves']]
            if token_data['reserves'][0]>0 and token_data['reserves'][1]>0:
                token_data['rate'] = token_data['reserves'][0]/token_data['reserves'][1]
            else:
                token_data['rate']=0
            
            #base token WBNB or BUSD
            token_data['base']=None
            for i in [0,1]:
                if token_data['pair'][i].upper() in self.base_tokens:
                    token_data['base']=i
            token_data['timestamp'] = f"{datetime.datetime.now().replace(microsecond=0)}"
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