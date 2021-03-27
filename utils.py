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

class BSCTokenTracker:
    def __init__(self, BSCSCAN_API_KEY):
        self.filename = "_token_tracker_data.json"
        self.caption = "===BSC Token Tracker==="
        self.bsc = BscScan(BSCSCAN_API_KEY)
        self.possible_tokens = ['0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c',  #WBNB
                                '0xe9e7cea3dedca5984780bafc599bd69add087d56',  #BUSD
                                '0x250632378e573c6be1ac2f97fcdf00515d0aa91b',  #BETH    
                               ]
        self.ignore_subtokens = ['BZN']
        self.data = self.load_data()
        if not self.data: 
            self.data = {}
            print("No data loaded")
            
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

    def token(self, token_address):
        #lookup in dict
        token = self.data.get(token_address, None)
        if token: return token
        
        #lookup in BSCScan
        url = 'https://bscscan.com/address/'+token_address
        headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'}
        try:
            result = requests.get(url, headers=headers)
        except Exception as e:
            print("Unable to obtain token info from bscScan with", e, datetime.datetime.now())
            print(url)
            return None
        result = result.content.decode()
        self.test = result
        
        #matches to <head><title> TokenName (TOKENSYMBOL) Token Tracker | BscScan </title>
        #pattern = "<head><title>\r\n\t([A-Za-z\.\- ]+)\(([A-Za-z\- ]+)\) Token Tracker Page\| BscScan\r\n</title>"
        
        #matches to View <token_address>? Token Tracker Page">TOKEN_NAME (TOKENSYMBOL)
        pattern='View 0?x?[0-9a-fA-F. ]*Token Tracker Page">([A-Za-z -]+) \(([a-zA-Z\-]+)\)' #updated 27th
        match = re.findall(string = result, pattern = pattern)
        if len(match)==0:
            self.last_err = "Can't parse..", url
            
            #print(result[:200])
            return None
        
        token_data = {'name' :match[0][0],
                      'symbol': match[0][1],
                      'address': token_address,
                      'pair' : None,
                      'subtokens': None,}
        #Liquidity pair
        if token_data['symbol']=="Cake-LP":
            token_data['subtokens'] = self.subtoken(result)
            if token_data['subtokens']:
                if len(token_data['subtokens'])<2:
                    #probably one of reserved
                    for t in self.possible_tokens:
                        if int(self.bsc.get_acc_balance_by_token_contract_address(address = token_address,
                                                      contract_address = t)) > 0:
                            token_data['subtokens'].append(self.token(t))
                if token_data['subtokens']:
                    try:
                        token_data['pair'] = "%".join([st['symbol'] for st in token_data['subtokens']])
                    except Exception as e:
                        pass
        
        self.data[token_address] = token_data
        
        
        self.save_data()
        self.test = result
        return token_data
        
    
    def subtoken(self, html_text):
        #pattern = '<a href="\/token\/(0x[0-9ABCGEFabcdef]{40})">[a-zA-Z]+<\/a>'
        pattern="href=\\'\/token\/(0x[0-9a-fA-F]{40})\?a=0x[0-9a-fA-F]{40}"
        match = re.findall(string=html_text, pattern = pattern)
        
        if len(match)==0: return None
        #print("MATCH"+match)
        token_data = [self.token(address) for address in match]
        #remove None's
        token_data = [t for t in token_data if t]
        token_data = [t for t in token_data if not t['symbol'] in self.ignore_subtokens]
        
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