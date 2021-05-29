import requests
import json
import ccxt
import time
import numpy as np
import talib

apiKey = '填上你自己的'
secret = '填上你自己的'

exchange = ccxt.huobipro({
    #     #代理部分
    #     'proxies':{
    #     'http':'socks5h://127.0.0.1:7891',
    #     'https':'socks5h://127.0.0.1:7891'
    #     },
    # api登陆
    'apiKey': apiKey,
    'secret': secret
})
# 币种
exchange.symbol = 'OXT/USDT'
# 交易所该币种交易最小数量精度
exchange.AmountPrecision = 4
# 交易所该币种价格最小精度
exchange.PricePrecision = 4


class MidClass():

    # 初始化
    def __init__(self, ThisExchange):
        self.Exchange = ThisExchange
        self.Symbol = ThisExchange.symbol
        self.AmountPrecision = ThisExchange.AmountPrecision
        self.PricePrecision = ThisExchange.PricePrecision

    # 获得交易对行情信息
    def GetTicker(self):
        self.High = '___'
        self.Low = '___'
        self.Buy = '___'
        self.Sell = '___'
        self.Last = '___'
        try:
            self.Ticker = self.Exchange.fetchTicker(self.Symbol)
            self.High = self.Ticker['high']
            self.Low = self.Ticker['low']
            self.Buy = self.Ticker['bid']
            self.Sell = self.Ticker['ask']
            self.Last = self.Ticker['last']
            return True  # 只要有一个成功就返回True
        except:
            return False  # 如果全都获取不了返回False

    # 获得账户对于该交易对信息
    def GetAccount(self):
        self.Account = '___'
        self.Balance = '___'
        self.FrozenBalance = '___'
        self.Stocks = '___'
        self.FrozenStocks = '___'

        self.SymbolStocksName = self.Symbol.split('/')[0]
        self.SymbolBalanceName = self.Symbol.split('/')[1]
        try:
            self.Account = self.Exchange.fetchBalance()
            self.Balance = self.Account[self.SymbolBalanceName]['free']
            self.FrozenBalance = self.Account[self.SymbolBalanceName]['used']
            self.Stocks = self.Account[self.SymbolStocksName]['free']
            self.FrozenStocks = self.Account[self.SymbolStocksName]['used']
            return True
        except:
            return False

    # 确认是否获取到账户和交易对信息
    def RefreshData(self):
        if not self.GetAccount():
            return 'false get account'
        if not self.GetTicker():
            return 'false get ticker'
        return 'refresh data finish!'

    # 创建订单
    def CreateOrder(self, OrderType, Price, Amount):
        if OrderType == 'buy':
            # 执行买单
            OrderId = self.Exchange.createLimitBuyOrder(self.Symbol, round(Amount, self.AmountPrecision),
                                                        round(Price, self.PricePrecision))['id']
        elif OrderType == 'sell':
            # 执行卖单
            OrderId = self.Exchange.createLimitSellOrder(self.Symbol, round(Amount, self.AmountPrecision),
                                                         round(Price, self.PricePrecision))['id']
        else:
            pass
        # 订单每次执行结束后，等待一点时间，让订单执行完，再刷新数据，再返回订单
        time.sleep(1)
        self.GetAccount()
        return OrderId

    # 获取订单状态
    def GetOrder(self, Idd):
        self.OrderId = '___'
        self.OrderPrice = '___'
        self.OrderNum = '___'
        self.OrderDealNum = '___'
        self.OrderAvgPrice = '___'
        self.OrderStatus = '___'

        try:
            self.Order = self.Exchange.fetchOrder(Idd, self.Symbol)
            self.OrderId = self.Order['id']
            self.OrderPrice = self.Order['price']
            self.OrderNum = self.Order['amount']
            self.OrderDealNum = self.Order['filled']
            self.OrderAvgPrice = self.Order['average']
            self.OrderStatus = self.Order['status']
            return True
        except:
            return False

    # 取消订单
    def CancelOrder(self, Idd):
        self.CancelResult = '___'
        try:
            self.CancelResult = self.Exchange.cancelOrder(Idd, self.Symbol)
            return True
        except:
            return False

            # 获取k线数据

    def GetRecords(self, Timeframe='1m'):
        self.Records = '___'
        try:
            self.Records = self.Exchange.fetchOHLCV(self.Symbol, Timeframe)
            return True
        except:
            return False


class RiskClass():

    # 风控模块初始化，传入实例化后的中间类
    def __init__(self, ThisMyMid):
        self.MyMid = ThisMyMid

    def CheckRisk(self, Price, Amount):
        self.MyMid.RefreshData()
        if self.MyMid.Balance >= Price * Amount:
            return True
        else:
            print('余额不足，买单未执行')
            return False


# 策略类
class DoubleMa():

    # 双均线策略初始化，传入传入实例化后的中间类以及双均线需要的窗口参数
    def __init__(self, ThisMyMid, ThisMyRisk, BuySellAmount, MyFastWindow, MySlowWindow):
        self.MyMid = ThisMyMid
        self.MyRisk = ThisMyRisk
        self.RemainStocks = self.MyMid.Stocks
        self.BuySellAmount = BuySellAmount
        self.FastWindow = MyFastWindow
        self.SlowWindow = MySlowWindow
        self.SentOrders = []  # 创建一个订单列表，可以记录目前的委托订单状态

    # 数据清洗并作出分析
    def BeginTrade(self):
        self.MyMid.GetRecords()
        self.CloseArrar = np.zeros(1000)  # 初始化收盘价数组，一共1000根k线有1000个数据
        t = 0
        for i in self.MyMid.Records:
            self.CloseArrar[t] = i[4]
            t += 1
        self.FastMaArrar = talib.SMA(self.CloseArrar, self.FastWindow)  # 快速均线数组
        self.SlowMaArrar = talib.SMA(self.CloseArrar, self.SlowWindow)  # 慢速均线数组
        # 得到最新的Ma值，包括最近一个和上一个
        self.fast_ma0 = self.FastMaArrar[-1]
        self.fast_ma1 = self.FastMaArrar[-2]
        self.slow_ma0 = self.SlowMaArrar[-1]
        self.slow_ma1 = self.SlowMaArrar[-2]
        # 金叉和死叉的判断
        CrossOver = self.fast_ma0 > self.slow_ma0 and self.fast_ma1 < self.slow_ma1  # 金叉
        CrossBelow = self.fast_ma0 < self.slow_ma0 and self.fast_ma1 > self.slow_ma1  # 死叉
        # 通过判断进行交易
        if CrossOver:  # 如果金叉买入
            if MyRisk.CheckRisk(0.23, self.BuySellAmount):  # 风控
                self.OrderId = self.MyMid.CreateOrder("buy", self.CloseArrar[-1], self.BuySellAmount)  # 创建买单
                self.SentOrders.append(self.OrderId)  # 添加这一个订单id到订单id列表
                print('买入价', self.CloseArrar[-1] * 0.99)
                print('产生一个限价买单!!!!!!!!!!!!!!!!!')
        if CrossBelow:  # 如果死叉卖出
            if self.RemainStocks > self.BuySellAmount:
                self.OrderId = self.MyMid.CreateOrder("sell", self.CloseArrar[-1], self.BuySellAmount)  # 创建卖单
                self.SentOrders.append(self.OrderId)  # 添加这一个订单id到订单id列表
                print('卖出价', self.CloseArrar[-1] * 1.01)
                print('产生一个限价卖单!!!!!!!!!!!!!!!!!')
            else:
                print('该币种数量不足，卖单未执行')

    # 检查策略完成后的信息
    def CheckAndReTrade(self):
        for i in self.SentOrders:  # 在订单id列表中遍历
            self.MyMid.GetOrder(i)  # 获得目前的订单id的订单状态
            if self.MyMid.OrderStatus == 'closed':  # 如果订单完成
                self.SentOrders.remove(i)  # 移除在订单id列表的信息
            if self.MyMid.OrderStatus == 'open':
                pass  # 不进行操作，可以修改价格再放上去，因为长期放着会占用保证金
            if self.MyMid.OrderStatus == 'canceled':  # 如果撤单
                self.SentOrders.remove(i)  # 移除在订单id列表的信息，或者可以修改价格再放上去


# 中间模块实例化
MyMid = MidClass(exchange)

# 数据更新
print(MyMid.RefreshData())

# 风险模块实例化
MyRisk = RiskClass(MyMid)

# 策略模块实例化
MyDoubleMa = DoubleMa(MyMid, MyRisk, BuySellAmount=30, MyFastWindow=3, MySlowWindow=10)  # 设置交易参数

# 显示相关数据
print(MyMid.Symbol, '最新价:', MyMid.Last)
print('该币种可用额度为:', round(MyMid.Stocks, 2), MyMid.SymbolStocksName)
print('该币种冻结额度为:', round(MyMid.FrozenStocks, 2), MyMid.SymbolStocksName)
print('账户可用额度为:', round(MyMid.Balance, 2), 'USD')
print('账户冻结额度为:', round(MyMid.FrozenBalance, 2), 'USD')

step = 1
while True:
    time.sleep(60)
    MyDoubleMa.BeginTrade()
    MyDoubleMa.CheckAndReTrade()
    print('目前挂单情况', MyDoubleMa.SentOrders)
    # 数据更新
    print(MyMid.RefreshData())
    print(MyMid.Symbol, '最新价:', MyMid.Last)
    print('该币种可用额度为:', round(MyMid.Stocks, 2), MyMid.SymbolStocksName)
    print('该币种冻结额度为:', round(MyMid.FrozenStocks, 2), MyMid.SymbolStocksName)
    print('账户可用额度为:', round(MyMid.Balance, 2), 'USD')
    print('账户冻结额度为:', round(MyMid.FrozenBalance, 2), 'USD')
    print('------------------------第', step, '轮尝试，等待60秒----------------------------')
    if step % 2 == 0:
        for i in MyDoubleMa.SentOrders:  # 在订单id列表中遍历
            MyDoubleMa.MyMid.GetOrder(i)  # 获得目前的订单id的订单状态
            if MyDoubleMa.MyMid.OrderStatus == 'closed':  # 如果订单完成
                MyDoubleMa.SentOrders.remove(i)  # 移除在订单id列表的信息
            if MyDoubleMa.MyMid.OrderStatus == 'open':  # 如果订单还没交易
                MyDoubleMa.MyMid.CancelOrder(i)  # 取消订单
                print('排除了一个未成交的挂单')
            if MyDoubleMa.MyMid.OrderStatus == 'canceled':  # 如果撤单
                MyDoubleMa.SentOrders.remove(i)  # 移除在订单id列表的信息，或者可以修改价格再放上去
    step = step + 1

