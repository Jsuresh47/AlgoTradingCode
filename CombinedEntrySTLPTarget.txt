from kiteconnect import KiteConnect
import time

# Enter position values
Qty         = 75
S1          = "NIFTY2170115850CE"
S2          = "NIFTY2170115850PE"
entryPrice  = 190
stopLoss    = 200
targetPrice = 170

# Initialise
kite = KiteConnect(api_key="ENTERYOURAPIKEY")
kite.set_access_token("ENTERYOURACCESSTOKEN")

# Function to place orders
def placeOrders(trans_type):
  try:
    kite.place_order(tradingsymbol=S1, variety='regular', exchange='NFO', transaction_type=trans_type,
                     quantity=Qty, order_type='MARKET', product='MIS')
  except: print("Order placement failed")

  try:
    kite.place_order(tradingsymbol=S2, variety='regular', exchange='NFO', transaction_type=trans_type,
                     quantity=Qty, order_type='MARKET', product='MIS')
  except: print("Order placement failed")

# Loop for entry orders
while True:
  try:
    combinedPremium = kite.ltp(['NFO:'+S1])['NFO:'+S1]['last_price'] + kite.ltp(['NFO:'+S2])['NFO:'+S2]['last_price']
  except: continue

  print("Combined Premium = ", combinedPremium)

  if (combinedPremium >= entryPrice):
    placeOrders('SELL')
    break

  time.sleep(5) # Change as per your need

# Loop for stoploss/target orders
while True:
  try:
    combinedPremium = kite.ltp(['NFO:'+S1])['NFO:'+S1]['last_price'] + kite.ltp(['NFO:'+S2])['NFO:'+S2]['last_price']
  except: continue              

  print("Combined Premium = ", combinedPremium)

  if (combinedPremium >= stopLoss or combinedPremium <= targetPrice):
    placeOrders('BUY')   # Stoploss/Target hit
    break

  time.sleep(5) # Change as per your need

