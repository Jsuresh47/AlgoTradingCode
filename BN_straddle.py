#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jun  2 14:47:28 2022
pip install websocket-client==0.40.0
@author: Suresh_Kumar
"""


#import logging
import datetime
import sys
from datetime import date, timedelta,datetime,time
import calendar
import statistics
from time import sleep
import pandas as pd
from alice_blue import *
import telegram


# PARAMETERS -:  CHANGE AS PER YOUR REQUIREMENTS

#Alice blue credentials
username = '****'
password = '******'
api_secret = '*****'
twoFA = '****'
app_id='*****'


## Telegram details ####
my_token="*****"  #trade_update
bot_chat_id=*****  # Always same



first_position_entry_time = [time(9,19,55),time(9,16,55),time(10,49,55),time(12,16,55),time(17,16,57),
                             time(21,25,57),time(9,16,57)]    # Change time as per your wish Mon to sun

final_position_exit_time  = time(15,10)    # Change time as per your wish
market_close_time         = time(15,30)

num_of_lots               = 1              #ATM 
is_Modify_ctc_required    = True           #True/False
is_Reentry_required       = True
Reentry_wait_min          = 5
Num_of_Reentry            = 1
max_reentry_time          = time(14,30)
strangle_diff             = [100,0,0,0,0,100,0]   # Is u want to sell strangle

sl_percentage             = [30,30,30,30,20,50,100]  #common Stoploss
stoploss_buffer_points    = 30   

# OTM buy details- Hedge
is_buy_required           = True
otm_diff_to_buy           = [3000,3000,3000,2000,3000,3000,3000]  #from mon to sunday to buy far OTM


max_loss_for_the_day      = -5000            # Portfolio level stoploss
max_loss_for_the_day_switch = ['N','Y','Y','Y','Y','N','N']


####################  NO CHANGE AFTER THIS  #####################

# Sell OTM
isSellOTM_Req             = False
strike_diff               = [300,300,300,300,300,300,300]   # To Sell OTM

num_of_lots_otm           = 0              #OTM

#Trail details:
sec_interveral_to_chk    = 5
trail_points             = 10


Live_Trade = True
NSE_holiday = [date(2021, 1, 26),date(2021, 3, 11),date(2021, 3, 29),date(2021, 4, 2),
               date(2021, 4, 14),date(2021, 4, 21),date(2021, 5, 13),
               date(2021, 7, 21),date(2021, 8, 19),date(2021, 9, 10),
               date(2021, 10, 15),date(2021, 11, 5),date(2021, 11, 19)]

#  PARAMETERS ENDS:::: -:  CHANGE AS PER REQUIREMENTS ENDS

alice = None
socket_opened = False
isRunNow=False
just_testing = False

if not isSellOTM_Req:
    num_of_lots_otm=0
    
total_buy_lots = num_of_lots+num_of_lots_otm

df_token_ltp = pd.DataFrame(columns=['token','ltp','Open','high','low','close'])
todays_max_min_pnl = pd.DataFrame(columns=['time','pnl'])

otm_diff_to_buy = otm_diff_to_buy[datetime.now().weekday()]
first_position_entry_time = first_position_entry_time[datetime.now().weekday()]
max_loss_switch =max_loss_for_the_day_switch[datetime.now().weekday()]
strike_otm = strike_diff[datetime.now().weekday()]
strangle_diff = strangle_diff[datetime.now().weekday()]
sl_order_id_list,sl_order_id_list1=[0,0],[0,0]
sl_price_list,sl_price_list1=[0,0],[0,0]
sl_completed_orders=[]
login_re_attempt=3

today = date.today()
position_start = datetime.combine(today, first_position_entry_time)
position_entry_wait_time = position_start - timedelta(minutes=30)
all_instruments=[]
ce_buy_exited,pe_buy_exited=False,False
completed_sl_orders=[]

def event_handler_quote_update(message):
    global ltp,volume
    
    message.pop("instrument",None)        
    ltp = message['ltp']
    Token =message['token']
    Open = message['open']
    high = message['high']
    low = message['low']
    close = message['close']
    token_ohlc = [Token,ltp,Open,high,low,close]
    append_token_ltp(token_ohlc)
    
def append_token_ltp(token_ohlc):
    try:
        global df_token_ltp
    
        new_series = pd.Series(token_ohlc, index = df_token_ltp.columns)
        df_token_ltp = df_token_ltp.append(new_series, ignore_index=True)
        df_token_ltp.drop_duplicates(subset='token',keep='last',inplace=True)
        
    except Exception as e:
        print(f"error while appending ltp: {e} ::time::{datetime.now().time()}")


def open_callback():
    global socket_opened
    socket_opened = True
    
def open_socket_now():
    global socket_opened

    socket_opened = False
    alice.start_websocket(subscribe_callback=event_handler_quote_update,
                          socket_open_callback=open_callback,
                          run_in_background=True)
    sleep(10)
    while(socket_opened==False):    # wait till socket open & then subscribe
        pass 
    
                                    
def get_call_n_put_n_place_straddle(atm_ce,atm_pe):
    print('get_call_n_put_n_place_straddle')
    try:
        global bank_nifty_call,bank_nifty_put,ce_executed_price,pe_executed_price,all_instruments
           
        combined_executed_price=0
    
        bank_nifty_call = alice.get_instrument_for_fno(symbol = 'BANKNIFTY', expiry_date= datecalc, is_fut=False, strike=atm_ce, is_CE = True)
        alice.subscribe(bank_nifty_call, LiveFeedType.MARKET_DATA)
        sleep(1)
        bank_nifty_put = alice.get_instrument_for_fno(symbol = 'BANKNIFTY', expiry_date= datecalc, is_fut=False, strike=atm_pe, is_CE = False)
        alice.subscribe(bank_nifty_put, LiveFeedType.MARKET_DATA)
        sleep(1)  
        all_instruments.append(str(bank_nifty_call[1]))        
        all_instruments.append(str(bank_nifty_put[1]))    
          
        ce_order_placed =  df_token_ltp.loc[df_token_ltp['token']==bank_nifty_call[1]]['ltp'].values[0]
        pe_order_placed =  df_token_ltp.loc[df_token_ltp['token']==bank_nifty_put[1]]['ltp'].values[0]
        
        ce_executed_price,pe_executed_price =ce_order_placed,pe_order_placed
        
        order_success,ce_executed_price = sell_Alice_ce(bank_nifty_call,ce_order_placed)  
        if order_success:
            order_success,pe_executed_price = sell_Alice_pe(bank_nifty_put,pe_order_placed)
        else:
            send(f"Order Failed for CE..Not placing PE sell order")
          
    except Exception as e:
        print(f"Error in get_ce_curr_price::{e}")
        
def sell_Alice_ce(bank_nifty_call,ce_order_placed):
    print('sell_bank_nifty_call')
    order_success=False
   
    quantity = num_of_lots*int(bank_nifty_call[5])
    sl_prcnt = get_stoploss_percentage()
    
    try:
        sell_order = alice.place_order(transaction_type = TransactionType.Sell,
                                 instrument = bank_nifty_call,
                                 quantity = quantity,
                                 order_type = OrderType.Market,
                                 product_type = ProductType.Intraday,
                                 price = 0.0,
                                 trigger_price = None,
                                 stop_loss = None,
                                 square_off = None,
                                 trailing_sl = None,
                                 is_amo = False)
       
        if sell_order['status'] == 'success':
            order_id = sell_order['data']['oms_order_id']
            order_success,ce_executed_price = get_order_execued_price(order_id)
            if order_success:
                if ce_executed_price ==0:
                    ce_executed_price=ce_order_placed
                sl_order = alice.place_order(transaction_type = TransactionType.Buy,
                             instrument = bank_nifty_call,
                             quantity = quantity,
                             order_type = OrderType.StopLossLimit,
                             product_type = ProductType.Intraday,
                             price = float(round(sl_prcnt*ce_executed_price)) + stoploss_buffer_points,
                             trigger_price = float(round(sl_prcnt*ce_executed_price)),
                             stop_loss = None,
                             square_off = None,
                             trailing_sl = None,
                             is_amo = False)
                
                sl_order_id_list[0]=sl_order['data']['oms_order_id']
                sl_price_list[0]=float(round(sl_prcnt*ce_executed_price))
                
                send(f"Sell {quantity} CE strike:{bank_nifty_call[2]} placed at price :{ce_executed_price} with sl:{float(round(sl_prcnt*ce_executed_price))} at time: {datetime.now().time()}")
            
          
        else:
            print(f"Sell CE failed..please check")
    except Exception as e:
        print(f"Error in sell_Alice_ce::{e}")
    return order_success,ce_executed_price

def sell_Alice_pe(bank_nifty_put,pe_order_placed):
    print('sell_bank_nifty_put')
    order_success=False

    quantity = num_of_lots*int(bank_nifty_put[5])
    sl_prcnt = get_stoploss_percentage()
   
    try:  
        sell_order = alice.place_order(transaction_type = TransactionType.Sell,
                                 instrument = bank_nifty_put,
                                 quantity = quantity,
                                 order_type = OrderType.Market,
                                 product_type = ProductType.Intraday,
                                 price = 0.0,
                                 trigger_price = None,
                                 stop_loss = None,
                                 square_off = None,
                                 trailing_sl = None,
                                 is_amo = False)
       
        if sell_order['status'] == 'success':
            order_id = sell_order['data']['oms_order_id']
            order_success,pe_executed_price = get_order_execued_price(order_id)
            if order_success:
                if pe_executed_price ==0:
                    pe_executed_price=pe_order_placed
                    
                sl_order = alice.place_order(transaction_type = TransactionType.Buy,
                            instrument = bank_nifty_put,
                            quantity = quantity,
                            order_type = OrderType.StopLossLimit,
                            product_type = ProductType.Intraday,
                            price = float(round(sl_prcnt*pe_executed_price)) + stoploss_buffer_points,
                            trigger_price = float(round(sl_prcnt*pe_executed_price)),
                            stop_loss = None,
                            square_off = None,
                            trailing_sl = None,
                            is_amo = False)
                
                sl_order_id_list[1]=sl_order['data']['oms_order_id']
                sl_price_list[1]=float(round(sl_prcnt*pe_executed_price))
                
                send(f"Sell {quantity} PE strike:{bank_nifty_put[2]} placed at price :{pe_executed_price} with sl:{float(round(sl_prcnt*pe_executed_price))} at time {datetime.now().time()}")
                
       
        else:
            print(f"Sell PE failed..please check")
    except Exception as e:
        print(f"Error in sell_Alice_pe::{e}")
    return order_success,pe_executed_price
        
def Buy_Alice_call_put(call_put,ind):
    
      

    if ind == 'Sell':
        tran_type = TransactionType.Sell
    else:
        tran_type = TransactionType.Buy
        
    order_success = False
    quantity = total_buy_lots*int(call_put[5])
    all_instruments.append(str(call_put[1]))
    
    if just_testing:
        send(f"{ind} {quantity} {call_put[2]} placed at price")
        order_success=True
        return order_success
    
    try:      
        buy_order = alice.place_order(transaction_type =tran_type,
                                 instrument = call_put,
                                 quantity = quantity,
                                 order_type = OrderType.Market,
                                 product_type = ProductType.Intraday,
                                 price = 0.0,
                                 trigger_price = None,
                                 stop_loss = None,
                                 square_off = None,
                                 trailing_sl = None,
                                 is_amo = False)
   
        if buy_order['status'] == 'success':
            order_id = buy_order['data']['oms_order_id']
            order_success,executed_price = get_order_execued_price(order_id)
            order_success=True
            
            print(f"{ind} {quantity} {call_put[2]} placed at price:{executed_price} at time {datetime.now().time()}")      
        else:
            print(f"Buy cover order failed..please check")
    except Exception as e:
        print(f"Error in sell_Alice_ce::{e}")
    return order_success       
def get_order_execued_price(order_id):
    num_of_re_rettempt=3
    order_success,executed_price=False,0
    if just_testing:
        order_success = True
        executed_price=300
        num_of_re_rettempt=1
      
    for i in range(num_of_re_rettempt):
        try:            
            order = alice.get_order_history(order_id)
            try:
                if len(order['data']) > 0:
                    if order['data'][0]['order_status'] != 'complete':
                        send(f"Rejection reason is:: {order['data'][0]['rejection_reason']}")
                        #print(f"order object::{order}")
                        sleep(1)
                    else:
                        executed_price = order['data'][0]['average_price']
                        order_success = True
                        break
            except Exception as e:
                print(f"Error in get_order_for order id:: {e}")
            if executed_price ==0:
                send(f"Issue while placing order....order_id is {order_id}")
        
        except Exception as e:
            print(f"Error in get_order_execued_price:: {e}")
    
    return order_success,executed_price


def check_for_triggered_order():
    
        try:   
            orders = alice.get_order_history()
            if len(orders['data']['pending_orders']) > 0:
                for order in orders['data']['pending_orders']:
                   
                    if order['order_status'] == 'open' and order['oms_order_id'] in sl_order_id_list:
                                        
                        curr_ltp = df_token_ltp.loc[df_token_ltp['token']==order['instrument_token']]['ltp'].values[0]
                        trigger_price = order['trigger_price']
                        instrument = alice.get_instrument_by_token('NFO', order['instrument_token']) 
                        send(f"Order triggered but not executed::order id is {order['oms_order_id']}\ncurr price n trigger price:{curr_ltp} & {trigger_price} of {instrument[2]}") 
                
        except Exception as e:
            print(f"error in check_for_triggered_order :{e}")
    
def trail_sl_order(entry_pr,sl_price,sl_order_id,ins):   
    try:
        curr_pr = df_token_ltp.loc[df_token_ltp['token']==ins[1]]['ltp'].values[0]

        curr_diff = entry_pr - curr_pr
        if curr_diff >=trail_points and sl_order_id not in sl_completed_orders:
            order = alice.get_order_history(sl_order_id)
            sleep(1)
            quantity = order['data'][0]['quantity']
            if len(order['data']) > 0:
                if  order['data'][0]['order_status'] == 'trigger pending':
                    curr_tr_price = order['data'][0]['trigger_price']
                    curr_tr_diff = sl_price - curr_tr_price
                    curr_diff_round = round(int(curr_diff/10)*10)
                    if curr_diff_round - curr_tr_diff >=trail_points:
                    
                        #modify order with price 
                        tr_price = curr_tr_price- round(int(curr_diff_round - curr_tr_diff))
                        modify_existing_order(sl_order_id,ins,quantity,tr_price,curr_tr_price)
                if order['data'][0]['order_status'] == 'complete':
                    sl_completed_orders.append(sl_order_id)
                    
                        
    except Exception as e:
        print(f"error in trail_sl_order :{e}")  
            
def modify_existing_order(sl_order_id,ins,quantity,tr_price,prev_trigger):
    if is_Modify_ctc_required:   
        tr_price = float(round(tr_price))
        quantity = round(quantity)
        try:   
            mod_order = alice.modify_order(transaction_type =TransactionType.Buy,
                                     instrument = ins,
                                     quantity=quantity,
                                     product_type = ProductType.Intraday,
                                     order_id = sl_order_id,
                                     order_type = OrderType.StopLossLimit,
                                     price = tr_price+ stoploss_buffer_points,
                                     trigger_price = tr_price,
                                     )
            send(f"Trailing existing order of {ins[2]} from {prev_trigger} to price {tr_price}")
        except Exception as e:
            print(f"error in modify_existing_order :{e}")   

def get_net_positions():
    global ce_buy_exited,pe_buy_exited
    ce_buy_exit,pe_buy_exit = False,False
    ce_qty,pe_qty=0,0
    
    try:
        if Live_Trade and (not ce_buy_exited or not pe_buy_exited ):
            positions = alice.get_netwise_positions()
            if len(positions['data']['positions']) >0:
                for pos in positions['data']['positions']:                
                    if pos['net_quantity'] < 0:
                        #print(pos)
                        if 'CE' in pos['trading_symbol']:
                            ce_qty+=1
                                                   
                        if 'PE' in pos['trading_symbol']:
                            pe_qty+=1
            if len(positions['data']['positions']) >0:
                if ce_qty == 0 and not  ce_buy_exited:
                    ce_buy_exited = True 
                    ce_buy_exit = True
                if pe_qty == 0 and not  pe_buy_exited:
                    pe_buy_exited = True 
                    pe_buy_exit=True
    except Exception as e:
        print(f"Error in get_net_positions::{e} ")
                
    return ce_buy_exit,pe_buy_exit

def get_date_curr_expiry(atm_ce):
    
    global datecalc,isTrade_nextExpiry,days_to_expiry
    call = None
    datecalc = date.today()
    while call == None:        
        try:
            call = alice.get_instrument_for_fno(symbol = 'BANKNIFTY', expiry_date= datecalc, is_fut=False, strike=atm_ce, is_CE = True)
            if call == None:
                datecalc = datecalc + timedelta(days=1)
            
        except:
            pass
    days_to_expiry = datecalc-date.today()
    print(f"Date_curr_expiry is::{datecalc} and days_to_expiry is {days_to_expiry}")
    

def get_mtm():
    global todays_max_min_pnl
    pnl,isExit =0,False
    try:    
        positions = alice.get_daywise_positions()
        if positions !=None:
            if len(positions['data']['positions']) >0:
                
                for pos in positions['data']['positions']:
                    #pnl = int(float(pos['m2m'])) + int(float(pos['realised_pnl'])) + pnl
                    pnl = int(float((pos['m2m']).replace(',',''))) + pnl
                new_row = [datetime.now().time(),pnl]
                new_series = pd.Series(new_row, index = todays_max_min_pnl.columns)
                todays_max_min_pnl = todays_max_min_pnl.append(new_series, ignore_index=True)
   
    except Exception as e:
        send(f"error get_actual_mtm: {e}")
    return pnl
        
def cancel_all_orders():
    send(f"Cancelling All pending orders")
    try:
        if Live_Trade:            
            orders = alice.get_order_history()
            if len(orders['data']['pending_orders']) >0:
                for order in orders['data']['pending_orders']:
                    if order['instrument_token'] in all_instruments:
                        alice.cancel_order(order['oms_order_id'])
                        print(f"Cancelled order for {order['trading_symbol']}")
    except Exception as e:
        send(f"Error in cancel_all_orders::{e}")
                    

                        
def exit_all_positions():
    print(f"Exiting all active position")
    try:
        if Live_Trade:
            positions = alice.get_netwise_positions()
            if len(positions['data']['positions']) >0:
                for pos in positions['data']['positions']:
                    if pos['net_quantity'] != 0 and pos['instrument_token'] in all_instruments:
                        
                        if pos['net_quantity'] <0:
                            tran_type = TransactionType.Buy
                            Quantity=-pos['net_quantity']
                        
                            order = alice.place_order(transaction_type = tran_type,
                                         instrument = alice.get_instrument_by_token('NFO', pos['instrument_token']),
                                         quantity = Quantity,
                                         order_type = OrderType.Market,
                                         product_type = ProductType.Intraday,
                                         price = 0.0,
                                         trigger_price = None,
                                         stop_loss = None,
                                         square_off = None,
                                         trailing_sl = None,
                                         is_amo = False)
                            send(f"EXit {str(tran_type).split('.')[-1]} {Quantity} Quantity placed for {pos['trading_symbol']} at {pos['ltp']}")
                            
                            
            sleep(2)                
            positions = alice.get_netwise_positions()
            if len(positions['data']['positions']) >0:
                for pos in positions['data']['positions']:
                    if pos['net_quantity'] != 0 and pos['instrument_token'] in all_instruments:
                        
                        if pos['net_quantity'] >0:
                            tran_type = TransactionType.Sell
                            Quantity=pos['net_quantity']
                                               
                            order = alice.place_order(transaction_type = tran_type,
                                         instrument = alice.get_instrument_by_token('NFO', pos['instrument_token']),
                                         quantity = Quantity,
                                         order_type = OrderType.Market,
                                         product_type = ProductType.Intraday,
                                         price = 0.0,
                                         trigger_price = None,
                                         stop_loss = None,
                                         square_off = None,
                                         trailing_sl = None,
                                         is_amo = False)
                            send(f"EXit {str(tran_type).split('.')[-1]} {Quantity} Quantity placed for {pos['trading_symbol']} at {pos['ltp']}")
    except Exception as e:
        send(f"Error in exit_all_positions::{e}")    
        
def get_order_execued_status(sl_order_id_list,call_ins,put_ins,ce_ex_price,pe_ex_price):
    st_ce_ext_price,st_pe_ext_price = 0,0
    ce_complete_status,pe_complete_status = False,False
    try:            
        if sl_order_id_list[0] not in completed_sl_orders:            
            order = alice.get_order_history(sl_order_id_list[0])
            if len(order['data']) > 0:
                if order['data'][0]['order_status'] == 'complete':
                    completed_sl_orders.append(sl_order_id_list[0])
                    send(f"Sl hit-order completed for {order['data'][0]['trading_symbol']} at price {order['data'][0]['average_price']}")
                    ce_complete_status = True
                    st_ce_ext_price = order['data'][0]['average_price']
                    
        if sl_order_id_list[1] not in completed_sl_orders:            
            order = alice.get_order_history(sl_order_id_list[1])
            if len(order['data']) > 0:
                if order['data'][0]['order_status'] == 'complete':
                    completed_sl_orders.append(sl_order_id_list[1])
                    send(f"Sl  hit-order completed  for {order['data'][0]['trading_symbol']} at price {order['data'][0]['average_price']}")
                    pe_complete_status = True
                    st_pe_ext_price = order['data'][0]['average_price']
                           
    except Exception as e:
        print(f"get_order_execued_status::{e}")
    return ce_complete_status,pe_complete_status,st_ce_ext_price,st_pe_ext_price
            
def get_stoploss_percentage():
    sl_prcnt = 1.5
    sl_prcnt = (sl_percentage[datetime.now().weekday()]+100)/100
    
    return sl_prcnt

def send(msg, chat_id=bot_chat_id, token=my_token):
    print(msg)
    bot = telegram.Bot(token=token)
    bot.sendMessage(chat_id=chat_id, text=msg)
    
   
def main():
    global alice,socket_opened,ltp,isRunNow,sell_otm_now
    
    while datetime.now().time()<= position_entry_wait_time.time():
        sleep(60)
    
    if Live_Trade:
        send(f"Algo running in Live mode|Stoploss for the Day is {sl_percentage[datetime.now().weekday()]} % And max_loss_switch is {max_loss_switch}::Start Time::{datetime.now().time()}")
    else:
        send(f"Algo running in Paper mode|Stoploss for the Day is {sl_percentage[datetime.now().weekday()]} % And max_loss_switch is {max_loss_switch}::Start Time::{datetime.now().time()}")  
    for i in range(login_re_attempt):
       print('logging in alice')
       try:
           access_token =  AliceBlue.login_and_get_access_token(username=username, password=password, twoFA=twoFA,  api_secret=api_secret, app_id=app_id)
           alice = AliceBlue(username=username, password=password, access_token=access_token, master_contracts_to_download=['NSE','NFO'])
           if alice != None:
               send('logged in alice successfully')
               break
       except Exception as e:
           send(f"login failed Alice..Retrying in 5 seconds after resolving error ::{e}..Attempt nbr {i+1}")
           sleep(5)
    if alice == None: 
        raise SystemExit
    
    if socket_opened == False:
        open_socket_now()
        
    # Get Bank Nifty Symbol
    NiftyBank_Index = alice.get_instrument_by_symbol('NSE', 'Nifty Bank') 
   

    order_placed,curr_actual_mtm,buy_order_placed=False,0,False
    sell_otm_now,order_entered = False,False
    cur_minute,straddle_num=99,0
    if datetime.now().time() < first_position_entry_time:
        send(f"Waiting to take first position till {first_position_entry_time}")
    
    
    while datetime.now().time()<= market_close_time:
        try:      
            if datetime.now().time() >= first_position_entry_time and not order_placed and not order_entered or isRunNow:
                order_entered = True
                alice.subscribe(NiftyBank_Index, LiveFeedType.MARKET_DATA)             
                sleep(1)
                curr_ltp  = df_token_ltp.loc[df_token_ltp['token']==NiftyBank_Index[1]]['ltp'].values[0]
                atm_ce,atm_pe = round(curr_ltp/100)*100,round(curr_ltp/100)*100
                atm_ce,atm_pe = atm_ce+strangle_diff, atm_pe-strangle_diff
                
                send(f"Bank Nifty curr price::{curr_ltp},Selected CE_strike::{atm_ce},Selected PE_strike:{atm_pe} at time {datetime.now().time()}")
                alice.unsubscribe(NiftyBank_Index, LiveFeedType.MARKET_DATA)
                               
                get_date_curr_expiry(atm_ce)
                if is_buy_required:# and not buy_order_placed:
                    
                    atm_500ce,atm_500pe = round(curr_ltp/100)*100,round(curr_ltp/100)*100
                    atm_500ce,atm_500pe=atm_500ce+otm_diff_to_buy ,atm_500pe-otm_diff_to_buy
                                        
                    bank_nifty_call_buy = alice.get_instrument_for_fno(symbol = 'BANKNIFTY', expiry_date= datecalc, is_fut=False, strike=atm_500ce, is_CE = True)                   
                    bank_nifty_put_buy = alice.get_instrument_for_fno(symbol = 'BANKNIFTY', expiry_date= datecalc, is_fut=False, strike=atm_500pe, is_CE = False)
                    
                    order_status_call = Buy_Alice_call_put(bank_nifty_call_buy,'Buy')                        
                    order_status_put = Buy_Alice_call_put(bank_nifty_put_buy,'Buy')
                       
                    if not order_status_call or not order_status_put:                       
                        send(f"Buy hedge order failed after multiple reattempts..Exiting Algo")
                        exit_all_positions()
                        break
                    buy_order_placed = True
                    sleep(2)
                get_call_n_put_n_place_straddle(atm_ce,atm_pe)                
                order_placed,isRunNow = True,False
                straddle_num+=1
            if order_placed:                
                curr_actual_mtm = get_mtm()
                ce_ltp = df_token_ltp.loc[df_token_ltp['token']==bank_nifty_call[1]]['ltp'].values[0]
                pe_ltp = df_token_ltp.loc[df_token_ltp['token']==bank_nifty_put[1]]['ltp'].values[0]
                quantity = num_of_lots*int(bank_nifty_put[5])
                s1_ce_comp_status,s1_pe_comp_status,s1_ce_ext_price,s1_pe_ext_price =get_order_execued_status\
                (sl_order_id_list,bank_nifty_call,bank_nifty_put,ce_executed_price,pe_executed_price)
                
                if (s1_ce_comp_status and s1_ce_ext_price>0) or just_testing:
                    s1f_ce_ext_price=s1_ce_ext_price
                    send(f"Sl hit  of CE Leg..at {s1f_ce_ext_price} at time:{datetime.now().time()}")
                    modify_existing_order(sl_order_id_list[1],bank_nifty_put,quantity,pe_executed_price,sl_price_list[1])
                    if is_Reentry_required and straddle_num <= Num_of_Reentry and datetime.now().time() <= max_reentry_time:
                        send(f"Waiting for {Reentry_wait_min} mins before re-entring straddle")
                        sleep(Reentry_wait_min*60)
                        isRunNow = True
                if s1_pe_comp_status and s1_pe_ext_price>0:
                    s1f_pe_ext_price=s1_pe_ext_price
                    send(f"Sl hit  of PE Leg..at {s1f_pe_ext_price} at time:{datetime.now().time()}")
                    modify_existing_order(sl_order_id_list[0],bank_nifty_call,quantity,ce_executed_price,sl_price_list[0])
                    if is_Reentry_required and straddle_num <= Num_of_Reentry and datetime.now().time() <= max_reentry_time:
                        send(f"Waiting for {Reentry_wait_min} mins before re-entring straddle")
                        sleep(Reentry_wait_min*60)
                        isRunNow = True
                
                if max_loss_switch == 'Y':                    
                    if  curr_actual_mtm < max_loss_for_the_day:
                        send(f"Exiting for the as Max loss has reached:: Actual MTM: {round(curr_actual_mtm,2)}")                        
                        cancel_all_orders()
                        exit_all_positions()
                        break
                                                
                if datetime.now().minute%5==0 and  datetime.now().minute != cur_minute:
                    cur_minute = datetime.now().minute                     
                    print(f"\nATM :CE_PRICE::{ce_ltp}|PE_PRICE::{pe_ltp}|\nActual MTM: {round(curr_actual_mtm,2)}")
                if datetime.now().time() >= final_position_exit_time:
                    send(f"Exiting all the position at {final_position_exit_time} with Actual MTM: {round(curr_actual_mtm,2)}")
                    cancel_all_orders()
                    exit_all_positions()
                    break
                if is_buy_required and  buy_order_placed:
                    ce_buy_exit,pe_buy_exit = get_net_positions()
                    if ce_buy_exit and is_buy_required:
                        #exit ce
                        order_status_call = Buy_Alice_call_put(bank_nifty_call_buy,'Sell')                        
                        
                    if pe_buy_exit and is_buy_required:
                        #exit pe                                  
                        order_status_put = Buy_Alice_call_put(bank_nifty_put_buy,'Sell')
                check_for_triggered_order()        
            sleep(sec_interveral_to_chk)
            
                    
        except Exception as e:
            send(f"some error occured at initial main:::->{e}")

           
    
if(__name__ == '__main__'):
    print('started Straddle')
   
    if date.today() not in NSE_holiday:
        main()
        send(f"Exiting for the day at time :: {datetime.now().time()}")
        curr_actual_mtm = get_mtm()
        send(f"Today's Max MTM:{todays_max_min_pnl['pnl'].max()},\nToday's Min MTM:{todays_max_min_pnl['pnl'].min()}\nFinal mtm::{round(curr_actual_mtm,2)}")
    else:
       print('Enjoy!!..Its a no trade day')
        
    
        


   
    
