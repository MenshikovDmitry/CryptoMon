#binance
from binance.client import Client

from web3 import Web3

#bscScan
from bscscan import BscScan

from utils import CoinMarketCap, bscscan_token_info

#farming
from selenium import webdriver
#before using selenium - put the chromium driver to path
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.options import Options
chrome_options = Options()
chrome_options.add_argument("--headless")

#general
import warnings
warnings.filterwarnings("ignore")

import datetime, time, json, os, re

import constants
#========================================================================


class CryptoMonitor:
    """
    parent class
    """
    def __init__(self, messenger):
        self.messenger = messenger
        pass
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
    
    def updates(self, verbose = True):
        news = self.check_updates()
        if not news:
            return
        news = [n for n in news if len(n.split())>0]
        if len(news)==0:
            return
        
        feed = [f"*{self.caption}*\n{datetime.datetime.now().replace(microsecond=0)}",] + news
        self.messenger.broadcast(feed)
        
        if verbose:
            print()
            for f in feed:
                if len(f)>0:
                    print(f)
                    print("-"*20)
#------------------------------------------------------------------------

    def check_updates(self):
        """
        to be written in sub class
        """
        pass

#========================================================================
#========================================================================

class FarmChecker(CryptoMonitor):
    def __init__(self, messenger, coin_market_cap, farms_filename = None,):
        self.filename = "_farms.json"
        self.caption = "=====PanCake SWAP====="
        self.url = "https://pancakeswap.finance/farms"
        #self.mask = '>([A-Z]{3,9}-[A-Z]{3,9})\ LP' #matches to CAKE-BNB LP, capital symbols  
        self.mask = ">([A-Z]{3,9}-[A-Z]{3,9})<" # updated 27.03.2021
        self.cmc = coin_market_cap
        self.ignore_list = ['BNB', "ETH", "CAKE", "BUSD"]
        
        self.data = self.load_data(farms_filename)
        if not self.data:
            self.data = self.get_farms()
        super().__init__(messenger)
#------------------------------------------------------------------------            
    def get_farms(self):
        driver = webdriver.Chrome(chrome_options = chrome_options)
        driver.get(self.url)
        s = driver.page_source
        self.source = s
        driver.quit()
        match = re.findall(self.mask, s)
        farms = list(set(match))
        return farms
#------------------------------------------------------------------------    
    def check_updates(self, verbose = True):
        try:
            farms = self.get_farms()
        except Exception as e:
            print("Error loading farms:", e)
            return None

        update_info = []
        new_farms = [f for f in farms if not f in self.data]
        if len(new_farms) > 0:
            for new_farm in new_farms:
                t1, t2 = new_farm.split('-')
                if self.cmc:
                    report = ""
                    if not t1 in self.ignore_list:
                        r=self.cmc.report(t1)
                        if r: report += r
                    if not t2 in self.ignore_list:
                        r=self.cmc.report(t2)
                        if r: report += r
                    print(report)
                    update_info.append("New Farm:\n"+new_farm +"\n"+report)
                else:
                    update_info.append("New Farm:\n"+new_farm)
                
            
        self.data += new_farms
        self.save_data()
        if len(update_info)==0: return None
        return update_info

#========================================================================
#========================================================================

class BinanceCheker(CryptoMonitor):
    def __init__(self, messenger, api_key, api_secret, data_filename=None):
        self.filename = "_binance_exchange_info.json"
        self.caption = "=======Binance========"
        self.client = Client(api_key, api_secret)
        self.data = self.load_data(data_filename)
        if not self.data:
            self.data = self.client.get_exchange_info()['symbols']
            self.save_data()
            
        self.pair_dict, self.tokens, self.pair_active = self.parse_info(self.data)
        self.pair_active_list = [p for p, s in self.pair_active.items() if s]
        self.inactive_pair_list = [p for p, s in self.pair_active.items() if not s]
        self.info = {symbol['symbol']: symbol for symbol in self.data}    
        super().__init__(messenger)
#------------------------------------------------------------------------        
        
    def parse_info(self, exchange_info):
        out_of_order = 0
        pair_dict = {}
        pair_active = {}
        tokens = []
        for token_info in exchange_info:
            pair_active[token_info['symbol']] = token_info['status'] =='TRADING'
            if token_info['status']!='TRADING':
                #print(f"{token_info['symbol']}: {token_info['status']} ")
                out_of_order+=1
                continue
            baseAsset = token_info["baseAsset"]
            if not baseAsset in tokens: tokens.append(baseAsset)
            quoteAsset = token_info["quoteAsset"]
            if not quoteAsset in tokens: tokens.append(quoteAsset)

            pair_dict[f"{baseAsset}-{quoteAsset}"] = f"{token_info['symbol']}"
            pair_dict[f"{quoteAsset}-{baseAsset}"] = f"!{token_info['symbol']}"
        #print(f"Registered: {len(exchange_info) - out_of_order}\nOut of order: {out_of_order}")
        return pair_dict, tokens, pair_active
#------------------------------------------------------------------------    

    def check_updates(self):
        try:
            info_raw = self.client.get_exchange_info()
        except Exception as e:
            print ("Error loading data:", e, datetime.datetime.now())
            print("status:", self.client.get_system_status())
            return
            
        pair_dict, tokens, pair_active = self.parse_info(info_raw['symbols'])
        pair_active_list = [p for p, s in pair_active.items() if s]
        inactive_pair_list = [p for p, s in pair_active.items() if not s]
        
        new_tokens = [t for t in tokens if not t in self.tokens]
        new_pairs = [p for p in pair_active.items() if not p[0] in self.pair_active.keys()]
        
        activated_pairs = [p for p in pair_active_list if p not in self.pair_active_list]
        activated_pairs = [p for p in activated_pairs if not (p, True) in new_pairs]
        deactivated_pairs = [p for p in inactive_pair_list if not p in self.inactive_pair_list]
        deactivated_pairs = [p for p in deactivated_pairs if not (p, False) in new_pairs]
        
        info = {symbol['symbol']: symbol for symbol in info_raw['symbols']}
        
        update_info = []
        
        if len(new_tokens)>0 : 
            message = 'New tokens\n'
            message+=', '.join(new_tokens)
            update_info.append(message)
            
        if len(new_pairs)>0  : 
            message = 'New pairs\n'
            for p in new_pairs:
                message+=f"{p[0]}: {info[p[0]]['status']}\n"
            update_info.append(message)
            
        if len(activated_pairs)>0: 
            message = 'Activated pairs\n'
            for p in activated_pairs:
                try:
                    message+= f"{p}: {self.info[p]['status']} -> {info[p]['status']}\n"
                except:
                    continue
            update_info.append(message)
            
        if len(deactivated_pairs)>0 : 
            message = 'DEactivated pairs\n'
            for p in deactivated_pairs:
                
                try:
                    old_status = self.info[p]['status']
                except:
                    old_status = "Nope"
                message+= f"{p}: {old_status} -> {info[p]['status']}\n"
            update_info.append(message)
            
            
        self.pair_dict, self.tokens, self.pair_active = pair_dict, tokens, pair_active
        self.pair_active_list = pair_active_list
        self.inactive_pair_list = inactive_pair_list
        self.info = info
        self.data = info_raw['symbols']
        self.save_data()
        if len(update_info)==0:
            update_info = None
        return update_info

#========================================================================
#========================================================================

class bscScanMonitor(CryptoMonitor):
    def __init__(self, messenger, coimarket_cap, bsc_api_key, data_filename=None):
        self.bsc = BscScan(bsc_api_key)
        self.cmc = coimarket_cap
        self.filename = "_bscScan_data.json"
        self.caption = "======BSC Scanner====="
        self.data = self.load_data(data_filename)
        
        if not self.data:
            self.data = {'last_block': 586851}
            self.save_data()
            
        super().__init__(messenger)
#------------------------------------------------------------------------        
        
    def check_new_pairs(self):
        PANCAKESWAP_DEPLOYER = "0x0F9399FC81DaC77908A2Dde54Bb87Ee2D17a3373"
        PANCAKESWAP_FACTORY =  "0xBCfCcbde45cE874adCB698cC183deBcF17952812"
        CREATE_PAIR =     '0xc9c65396'
        ignore_symbols = ['BTC', 'ETH', 'WBNB', 'BNB', 'CAKE']
        
        bs_tx = "https://bscscan.com/tx/"
        bs_token = "https://bscscan.com/token/"
        cmc_token = "https://coinmarketcap.com/currencies/"
        def input2tokens(inp):
            token1 = "0x"+inp[-40:].lower()
            token2 = "0x"+inp[:-64][-40:].lower()
            return token1, token2
        try:
            transactions = self.bsc.get_normal_txs_by_address(address = PANCAKESWAP_DEPLOYER,
                                                      startblock = self.data['last_block'],
                                                      endblock = None,
                                                      sort='asc')
        except AssertionError:
            #no transactions
            return None
        
        if len(transactions)==0:
            return None
        last_block = transactions[-1]['blockNumber']
        self.data['last_block'] = last_block
        self.save_data()
        
        transactions = [t for t in transactions if t['to'].lower()==PANCAKESWAP_FACTORY.lower() and \
                                                   t['isError']=='0']
        if len(transactions)==0:
            return None
        update_info = []
        #update CoinMarketCap Data
        for tx in transactions:
            if tx['input'].startswith(CREATE_PAIR):
                token1, token2 = input2tokens(tx['input'])
                symbol1 = bscscan_token_info(token1)
                symbol2 = bscscan_token_info(token2)
                #symbol1 = token_by_address.get(token1, {'symbol': token1, 'name': "https://bscscan.com/address/"+token1})
                #symbol2 = token_by_address.get(token2, {'symbol': token2, 'name': "https://bscscan.com/address/"+token2})
                msg = f"New pair at block no {tx['blockNumber']}, \n{datetime.datetime.fromtimestamp(int(tx['timeStamp']))} [hash]({bs_tx}{tx['hash']})"
                msg += (f"\n{symbol1[0]} [({symbol1[1]})]({bs_token}{token1}) <-> {symbol2[0]} [({symbol2[1]})]({bs_token}{token2})")
                
                report=""
                symbol_slug = None
                for s in [symbol1, symbol2]:
                    #get report from CoinMarketCap
                    symbol = s[1]
                    if symbol in ignore_symbols:
                        continue
                    r = self.cmc.report(symbol)
                    if r:
                        report += r
                        try:
                            symbol_slug = self.cmc.token(symbol)[0]['slug']
                        except:
                            pass
                    else:
                        report += f"\nNo CMC data for {symbol}"
                if len(report)>0:
                    msg += f"\n[CoinMarketCap]({cmc_token}{symbol_slug}):"
                    msg += report
                
                update_info.append(msg)
                
        return update_info    
#------------------------------------------------------------------------    
    
    def check_updates(self):
        return self.check_new_pairs()

#========================================================================
#========================================================================


class BlockChainLiquidityPairsTracker(CryptoMonitor):
    def __init__(self, messenger, coimarket_cap, token_tracker, bsc_api_key, data_filename=None):
        self.bsc = BscScan(bsc_api_key)
        self.tt  = token_tracker
        self.cmc = coimarket_cap
        self.filename = "_BSC_farm_tracker.json"
        self.caption = "===BSC Farm Tracker==="
        self.data = self.load_data(data_filename)
        self.executeTransaction = "0x0825f38f"
        self.queueTransaction =   "0x3a66f901"
        
        if not self.data:
            self.data = {'last_block': 5322320}
            self.save_data()
            
        super().__init__(messenger)
#------------------------------------------------------------------------  

    def queue_or_exec_report(self, token_inf, tx):
        bs_tx = "https://bscscan.com/tx/"
        bs_token = "https://bscscan.com/address/"
        cmc_token = "https://coinmarketcap.com/currencies/"
        report=""
        src_tokens = ['WBNB', 'BUSD', 'BNB']
        #print(token_inf['pair'])
        t0, t1 = token_inf['pair']
        new_token = 0 if t1 in src_tokens else 1 # the one that is being promoted
        src_token = 1 if new_token==0 else 0
        #print(f"new token {token_inf['pair'][new_token]}")
        #print(f"base token {token_inf['pair'][src_token]}")
        # price of bnb or busd
        src_price = self.cmc.token(token_inf['pair'][src_token])[0]['quote']['USD']['price']
        #print(f"price of {token_inf['pair'][src_token]} is ${src_price}")
        
        report += f"block no {tx['blockNumber']}, time {datetime.datetime.fromtimestamp(int(tx['timeStamp']))}, [hash](https://bscscan.com/tx/{tx['hash']})"
        report += f"\nFarm: [{'-'.join(token_inf['pair'])}]({bs_token}{token_inf['address']})"
        
        report += f"\nRate: {round(token_inf['rate'],4)} {token_inf['subtokens'][0]['symbol']} for 1 {token_inf['subtokens'][1]['symbol']}"
        if new_token==0:
            if token_inf['rate']>0:
                report+=f"\n{round(1/token_inf['rate']*src_price,4)}$ / {token_inf['subtokens'][0]['symbol']}"
            else:
                report+="\nError calculating rates"
        else:
            report+=f"\n{round(token_inf['rate']*src_price,4)}$ / {token_inf['subtokens'][1]['symbol']}"

        report += f"\nReserves: {token_inf['reserves']}"
        for i, st in enumerate(token_inf['subtokens']):
            report += f"\n-----\n[Token {i+1}]({bs_token}{st['address']})"
            for key, value in st.items():
                if value: report += f"\n{key}: {value}"
            report += "\n" + self.cmc.report(st['symbol'])

        return report
#------------------------------------------------------------------------ 
    def queueTransaction2token(self, inp):
        chunks=self.chunkstring(inp[len(self.queueTransaction):], 64)
        token = chunks[-2][-40:]
        return token    
#------------------------------------------------------------------------    
    def chunkstring(self, string, length):
        return [string[0+i:length+i] for i in range(0, len(string), length)]
#------------------------------------------------------------------------
    def check_new_transactions(self):
        PANCAKESWAP_MAIN =     "0xa1f482dc58145ba2210bc21878ca34000e2e8fe4"
        
        try:
            transactions = self.bsc.get_normal_txs_by_address(address = PANCAKESWAP_MAIN,
                                                      startblock = int(self.data['last_block'])+1,
                                                      endblock = None,
                                                      sort='asc')
        except AssertionError:
            #no transactions
            self.save_data()
            return None
        
        tqueue = [t for t in transactions if t['input'].startswith(self.queueTransaction) and t['isError']=='0']
        texec =  [t for t in transactions if t['input'].startswith(self.executeTransaction) and t['isError']=='0']

        if len(transactions)==0:
            return None
        
        last_block = transactions[-1]['blockNumber']
        self.data['last_block'] = last_block
        self.save_data()
        
        if len(tqueue)==0 and len(texec)==0:
            return None
        
        update_info = []
        for tx in texec:
            report = ""
            token = self.queueTransaction2token(tx['input'])
            token_inf = self.tt.token('0x' + token)
            if token_inf:
                report += "Liquidity Token EXECUTED!\n"
                #print(token_inf)
                report += self.queue_or_exec_report(token_inf, tx)
            update_info.append(report)
            
        for tx in tqueue:
            report = ""
            token = self.queueTransaction2token(tx['input'])
            token_inf = self.tt.token('0x' + token)
            if token_inf:
                report += "Liquidity Token QUEUED\n"
                report += self.queue_or_exec_report(token_inf, tx)
            update_info.append(report)        
        
        return update_info    
#------------------------------------------------------------------------    
    
    def check_updates(self):
        return self.check_new_transactions()
    
#========================================================================
#========================================================================



class PCS_DeveloperMon(CryptoMonitor):
    def __init__(self, messenger, token_tracker, coimarket_cap, bsc_api_key, data_filename=None):
        self.bsc = BscScan(bsc_api_key)
        self.cmc = coimarket_cap
        self.filename = "_dev_mon.json"
        self.caption = "===Developer Monitor==="
        self.data = self.load_data(data_filename)
        self.bsc = BscScan(bsc_api_key)
        self.tt = token_tracker
        self.ignore_tokens = [constants.CAKE_address]
        bsc = constants.binance_smart_chain
        self.w3 = Web3(Web3.HTTPProvider(bsc))
        self.pancake_dev_addresses = [self.w3.toChecksumAddress(addr) for addr in constants.pancake_dev_address]        
        if not self.data:
            self.data = {'last_block': 6468900,
                         'farms_live': [],
                         'farms_pending': []}
            self.save_data()
            
        super().__init__(messenger)
#------------------------------------------------------------------------        
        
    def tx_report(self, tt_data, tx, tx_type):
        bs_tx = "https://bscscan.com/tx/"
        bs_token = "https://bscscan.com/address/"
        
        token_symbol = tt_data['symbol']
        token_address = tt_data['address']
        pools = self.tt.pools(tt_data['address'])
        cmc_report = self.cmc.report(token_symbol)
        
        report = ""
        report+=f"*{tx_type}* [TX]({bs_tx}{tx['hash']}): {int(round(tx['amount']//1000))}K {token_symbol} (${tx['cmc_value']}K) (${tx['pcs_value']}K)"
        report+=f"\n{datetime.datetime.fromtimestamp(int(tx['timeStamp']))} Block {tx['blockNumber']}"
        report+=f"\n*name:* {tx['tokenName']} ([{tx['tokenSymbol']}]({bs_token}{token_address}))"
        report+=f"\n*address:* {token_address}"
        report+=f"\n-----\n*LiqPools:* "
        for pool in pools:
            base_token = pool['base']
            new_one = 1 if base_token==0 else 0
            base_price = self.cmc.token(pool['pair'][base_token])[0]['quote']['USD']['price']

            report+=f"\n[{'-'.join(pool['pair'])}]({bs_token}{pool['address']}) {'/'.join([str(p) for p in pool['reserves']])} (${int(pool['reserves'][base_token]*base_price*2//1000)}K)"

            if pool['rate']==0:
                rate = -1
            else:
                if base_token==0:
                    rate=1/pool['rate']
                else:
                    rate=pool['rate']
            report+= f"\nRate: {round(rate,4)} {pool['pair'][new_one]} for 1 {pool['pair'][base_token]} (${round(1/rate*base_price,2)})"
        
        report+=f"\nPCS price {round(self.pancake_price(token_address),4)} BUSD for 1 {token_symbol}"
        if tt_data['decimals']!=18:
            report+=f"\n*Price may be wrong!! *{tt_data['decimals']} decimals!!"
        report+="\n\n"+cmc_report
    
        return report
#------------------------------------------------------------------------          
    
    def pancake_price(self, token_address):
        """returns PCS price in BUSD directly and through WBNB"""
        token_address = self.w3.toChecksumAddress(token_address)
        router = self.w3.eth.contract(address=constants.pancake_router_address, abi = constants.pancake_router_abi)
        route1 = [self.w3.toChecksumAddress(token_address),
                  self.w3.toChecksumAddress(constants.WBNB_address),
                  self.w3.toChecksumAddress(constants.BUSD_address)]
        route2 = [self.w3.toChecksumAddress(token_address),
                  self.w3.toChecksumAddress(constants.BUSD_address)]   
        prices=[]
        for path in [route1, route2]:
            try:
                value_wei = router.functions.getAmountsOut(self.w3.toWei(1, 'ether'), path).call()[-1]
            except Exception as e:
                value_wei = 0
                #print(e)
            prices.append(self.w3.fromWei(value_wei, 'ether'))
        #print(prices)
        token_price = max(prices)
        return token_price
#------------------------------------------------------------------------


    def check_transactions(self):
        update_info=[]
        bep20_transactions = []
        norm_transactions = []
        
        for developer in self.pancake_dev_addresses:
            try:
                bep20_txs = self.bsc.get_bep20_token_transfer_events_by_address(developer,
                                            startblock = str(int(self.data['last_block'])+1),
                                            endblock = None,
                                            sort = 'asc')
            except AssertionError:
                #No Transaction Found
                self.save_data()
                bep20_txs = []
            bep20_transactions += bep20_txs
            
            try:
                norm_txs = self.bsc.get_normal_txs_by_address(address = developer,
                                                      startblock = str(int(self.data['last_block'])+1),
                                                      endblock = None,
                                                      sort='asc')
            except AssertionError:
                #No Transaction Found
                self.save_data()
                norm_txs = []
            norm_transactions += norm_txs     
            
        #print(len(transactions))
        update_unfo=[]
        
        if len(bep20_transactions + norm_transactions)==0:
            return None
            
        blocks_numbers = [int(tx['blockNumber']) for tx  in bep20_transactions] + \
                         [int(tx['blockNumber']) for tx  in norm_transactions]
        self.data['last_block'] = max(blocks_numbers)
        self.save_data()
        
        report = self.process_bep20_txs(bep20_transactions)
        if report: update_info += report
            
        report = self.process_norm_txs(norm_transactions)
        if report: update_info += report
            
            
        if len(update_info)==0: return None        
        return update_info
#------------------------------------------------------------------------  

    def process_norm_txs(self, transactions):
        create_contract = '0x60806040526'
        bs_addr = "https://bscscan.com/address/"
        bs_tx = "https://bscscan.com/tx/"
        bs_block = "https://bscscan.com/block/countdown/"
        
        update_info = []
        for tx in transactions:
            if not tx['input'].startswith(create_contract): continue
            contract_address = self.w3.toChecksumAddress(tx['contractAddress'])
            contract = self.w3.eth.contract(contract_address, abi = constants.smart_chief_abi)
            try:
                reward_token_address = contract.functions.rewardToken().call()
            except:
                #Not a smartChief contract
                print(f"Not a SmartChief contract: {bs_addr}{contract_address}")
                continue
            start_block = contract.functions.startBlock().call()
            block_delta = start_block - int(tx['blockNumber'])
            sec_delta = block_delta * 3 # average block time
            start_time = datetime.datetime.fromtimestamp(int(tx['timeStamp'])) + datetime.timedelta(seconds=sec_delta)

            tt_data = self.tt.token(reward_token_address)
            pools = self.tt.pools(reward_token_address)
            cmc_report = self.cmc.report(tt_data['symbol'])
            
            report = ""
            report += f"[SmartChief]({bs_addr}{contract_address}) [created]({bs_tx}{tx['hash']})"
            report += f"\n{datetime.datetime.fromtimestamp(int(tx['timeStamp']))}; Start Block [{start_block}]({bs_block}{start_block})"
            report += f"\nLive at {start_time}"
            report += f"\n*name:* {tt_data['name']} ([{tt_data['symbol']}]({bs_addr}{reward_token_address}))"
            report += f"\n*address:* {reward_token_address}"            
            report += f"\n-----\n*LiqPools:* "
            
            for pool in pools:
                base_token = pool['base']
                new_one = 1 if base_token==0 else 0
                base_price = self.cmc.token(pool['pair'][base_token])[0]['quote']['USD']['price']
            
                report+=f"\n[{'-'.join(pool['pair'])}]({bs_addr}{pool['address']}) {'/'.join([str(p) for p in pool['reserves']])} (${int(pool['reserves'][base_token]*base_price*2//1000)}K)"    
                if pool['rate']==0:
                    rate = -1
                else:
                    if base_token==0:
                        rate=1/pool['rate']
                    else:
                        rate=pool['rate']
                report+= f"\nRate: {round(rate,4)} {pool['pair'][new_one]} for 1 {pool['pair'][base_token]} (${round(1/rate*base_price,2)})"
            report+=f"\nPCS price {round(self.pancake_price(reward_token_address),4)} BUSD for 1 {tt_data['symbol']}"
            if tt_data['decimals']!=18:
                report+=f"\n*Price may be wrong!! *{tt_data['decimals']} decimals!!"
            report += "\n\n" + cmc_report
            update_info.append(report)
        return update_info

#------------------------------------------------------------------------  
    
    def process_bep20_txs(self, transactions):
        update_info = []
        for tx in transactions:
            tx['from'] = self.w3.toChecksumAddress(tx['from'])
            report = ""
            if tx['from'] in self.pancake_dev_addresses:
                transaction_type = "OUT"
            else:
                transaction_type = "IN"
                
            token_symbol = tx['tokenSymbol']
            token_address = self.w3.toChecksumAddress(tx['contractAddress'])
            tt_data = self.tt.token(token_address)
            
            cmc_data = self.cmc.token(token_symbol)
            
            if cmc_data:    
                #it might be more than one token with this name
                #chose lowest price
                cmc_price = min([c['quote']['USD']['price'] for c in cmc_data])
            else:
                cmc_price = 0
            pcs_price = self.pancake_price(token_address)
            amount = int(self.w3.fromWei(int(tx['value']), 'ether'))
            tx['amount'] = amount
            #value in $1000
            cmc_value = int(amount*cmc_price//1000)
            pcs_value = int(amount*pcs_price//1000)
            tx['cmc_value'] = cmc_value
            tx['pcs_value'] = pcs_value
            #print(transaction_type, value, token_symbol, )
            
            #if transaction_type=='IN' and (cmc_value<1 and pcs_value<1): continue
            if token_address in self.ignore_tokens: continue
                
            if transaction_type=="IN":
                if not token_address in self.data['farms_pending']:
                    self.data['farms_pending'].append(token_address)
            else:
                #out transaction
                if not token_address in self.data['farms_live']:
                    self.data['farms_live'].append(token_address)
                    try:
                        self.data['farms_pending'].remove(token_address)
                    except:
                        pass
                    
            report = self.tx_report(tt_data, tx, transaction_type)
            update_info.append(report)
        return update_info
#------------------------------------------------------------------------    
    
    def check_updates(self):
        return self.check_transactions()
#========================================================================
#========================================================================
