// +------------------------------------------------------------------+
// |           tradeCorelogger v2.2 (MT5)                             |
// |  Builds on v2.1. Adds to TradeLog at every trade event:          |
// |    - balance     (AccountInfoDouble ACCOUNT_BALANCE)             |
// |    - equity      (AccountInfoDouble ACCOUNT_EQUITY)              |
// |    - drawdown    (equity - balance, negative = in drawdown)      |
// |                                                                  |
// |  Note: MT5 provides balance and equity natively via AccountInfo  |
// |  functions. No math embedding needed beyond drawdown = eq - bal. |
// +------------------------------------------------------------------+
#property strict

// ===================== USER INPUTS =====================

input bool LOGGING_ENABLED = true;

enum TRADING_MODE
{
   MODE_NORMAL,
   MODE_FOMO,
   MODE_FOMO_CUT_LOSSES,
   MODE_TEST,
   MODE_WAIT,
   MODE_STOP
};

input TRADING_MODE CURRENT_MODE = MODE_NORMAL;

// ===================== INDICATOR HANDLES =====================

int h_atr_long   = INVALID_HANDLE;
int h_atr_medium = INVALID_HANDLE;
int h_atr_short  = INVALID_HANDLE;

// ===================== GLOBAL VARIABLES =====================

int tick_file  = INVALID_HANDLE;
int trade_file = INVALID_HANDLE;

double prev_last     = 0;
long   prev_time_msc = 0;

// ===================== HELPER: Fetch M5 closes =====================
// CopyClose actively requests data from MT5 server if not yet cached.
// Far more reliable than iClose() on live/demo accounts.

bool FetchCloses(int count, double &out[])
{
   int copied = CopyClose(_Symbol, PERIOD_M5, 0, count, out);
   if(copied < count)
   {
      Print("History not ready: got ", copied, " of ", count, " bars");
      return false;
   }
   // Sanity check — ensure no zero prices in result
   for(int i = 0; i < count; i++)
      if(out[i] <= 0) return false;
   return true;
}

// ===================== HELPER: Compute RVA =====================

double GetRVA(int periods)
{
   double closes[];
   if(!FetchCloses(periods + 1, closes))
      return 0.0;

   double returns[];
   ArrayResize(returns, periods);
   for(int i = 0; i < periods; i++)
      returns[i] = closes[i] - closes[i + 1];

   double mean = 0;
   for(int i = 0; i < periods; i++) mean += returns[i];
   mean /= periods;

   double variance = 0;
   for(int i = 0; i < periods; i++)
      variance += (returns[i] - mean) * (returns[i] - mean);
   variance /= periods;

   return MathSqrt(variance) / _Point;
}

// ===================== HELPER: Compute ROC =====================

double GetROC(double current_price, int periods)
{
   double closes[];
   int needed = periods + 1;
   int copied = CopyClose(_Symbol, PERIOD_M5, 0, needed, closes);
   if(copied < needed) return 0.0;
   double base = closes[periods];
   if(base <= 0 || current_price <= 0) return 0.0;
   return (current_price - base) / base * 100.0;
}

// ===================== HELPER: Compute ATR =====================

double GetATR(int handle)
{
   double buf[];
   if(CopyBuffer(handle, 0, 0, 1, buf) < 1) return 0.0;
   return buf[0] / _Point;
}

// ===================== HELPER: Position stats =====================

struct PositionStats
{
   double floating_pnl;
   int    open_trades;
   int    open_buys;
   int    open_sells;
};

PositionStats GetPositionStats()
{
   PositionStats ps;
   ps.floating_pnl = 0;
   ps.open_trades  = 0;
   ps.open_buys    = 0;
   ps.open_sells   = 0;

   int total = PositionsTotal();
   for(int i = 0; i < total; i++)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;

      ps.floating_pnl += PositionGetDouble(POSITION_PROFIT);
      ps.open_trades++;

      long pos_type = PositionGetInteger(POSITION_TYPE);
      if(pos_type == POSITION_TYPE_BUY)  ps.open_buys++;
      if(pos_type == POSITION_TYPE_SELL) ps.open_sells++;
   }

   return ps;
}

// ===================== MARKET METRICS =====================

struct MarketMetrics
{
   double rva_long, rva_medium, rva_short;
   double roc_long, roc_medium, roc_short;
   double roc_live_interbar, roc_live_intrabar;
   double atr_long, atr_medium, atr_short;
   double live_pip_range;
   double live_velocity;
   string candle_direction;
};

MarketMetrics GetMetrics(double tick_last)
{
   // Fallback: if tick price is 0 (market closed / no quote), use last known bid
   if(tick_last <= 0)
      tick_last = SymbolInfoDouble(_Symbol, SYMBOL_BID);

   MarketMetrics m;

   m.rva_long   = GetRVA(60);
   m.rva_medium = GetRVA(20);
   m.rva_short  = GetRVA(5);

   m.roc_long   = GetROC(tick_last, 45);
   m.roc_medium = GetROC(tick_last, 15);
   m.roc_short  = GetROC(tick_last, 3);

   double prev_close_arr[];
   m.roc_live_interbar = 0;
   if(CopyClose(_Symbol, PERIOD_M5, 1, 1, prev_close_arr) == 1 && prev_close_arr[0] > 0)
      m.roc_live_interbar = (tick_last - prev_close_arr[0]) / prev_close_arr[0] * 100.0;

   double cur_open[];
   m.roc_live_intrabar = 0;
   if(CopyOpen(_Symbol, PERIOD_M5, 0, 1, cur_open) == 1 && cur_open[0] != 0)
      m.roc_live_intrabar = (tick_last - cur_open[0]) / cur_open[0] * 100.0;

   m.atr_long   = GetATR(h_atr_long);
   m.atr_medium = GetATR(h_atr_medium);
   m.atr_short  = GetATR(h_atr_short);

   double hi[], lo[];
   m.live_pip_range = 0;
   if(CopyHigh(_Symbol, PERIOD_M5, 0, 1, hi) == 1 &&
      CopyLow (_Symbol, PERIOD_M5, 0, 1, lo) == 1)
      m.live_pip_range = (hi[0] - lo[0]) / _Point;

   datetime bar_time[];
   m.live_velocity = 0;
   if(CopyTime(_Symbol, PERIOD_M5, 0, 1, bar_time) == 1)
   {
      long elapsed = (long)(TimeCurrent() - bar_time[0]);
      if(elapsed > 0)
         m.live_velocity = m.live_pip_range / (double)elapsed;
   }

   if(ArraySize(cur_open) > 0 && cur_open[0] > 0)
   {
      if(tick_last > cur_open[0])      m.candle_direction = "BULL";
      else if(tick_last < cur_open[0]) m.candle_direction = "BEAR";
      else                             m.candle_direction = "FLAT";
   }
   else m.candle_direction = "FLAT";

   return m;
}

// ===================== INIT =====================

int OnInit()
{
   // Force history preload — required on live/demo accounts so iClose()
   // returns real values instead of 0. We need at least 102 bars (ATR long=100 + buffer).
   int attempts = 0;
   while(Bars(_Symbol, PERIOD_M5) < 150 && attempts < 50)
   {
      SeriesInfoInteger(_Symbol, PERIOD_M5, SERIES_BARS_COUNT);
      Sleep(100);
      attempts++;
   }
   int loaded = Bars(_Symbol, PERIOD_M5);
   Print("📊 History bars loaded: ", loaded);
   if(loaded < 102)
   {
      Print("⚠️ Insufficient history (", loaded, " bars). ROC may show -100 until more bars load.");
   }

   h_atr_long   = iATR(_Symbol, PERIOD_M5, 100);
   h_atr_medium = iATR(_Symbol, PERIOD_M5, 50);
   h_atr_short  = iATR(_Symbol, PERIOD_M5, 10);

   if(h_atr_long == INVALID_HANDLE || h_atr_medium == INVALID_HANDLE || h_atr_short == INVALID_HANDLE)
   {
      Print("❌ ATR handle creation failed");
      return(INIT_FAILED);
   }

   string date = TimeToString(TimeCurrent(), TIME_DATE);

   string tick_file_name  = "TickLog_"  + _Symbol + "_" + date + ".csv";
   string trade_file_name = "TradeLog_" + _Symbol + "_" + date + ".csv";

   tick_file  = FileOpen(tick_file_name,  FILE_WRITE|FILE_READ|FILE_CSV|FILE_COMMON|FILE_SHARE_READ, ',');
   trade_file = FileOpen(trade_file_name, FILE_WRITE|FILE_READ|FILE_CSV|FILE_COMMON|FILE_SHARE_READ, ',');

   if(tick_file == INVALID_HANDLE || trade_file == INVALID_HANDLE)
   {
      Print("❌ File open failed");
      return(INIT_FAILED);
   }

   // --- Tick Header
   FileWrite(tick_file,
      "timestamp", "timestamp_msc", "symbol",
      "bid", "ask", "last", "volume", "spread",
      "delta_price", "delta_time_msc",
      "rva_long", "rva_medium", "rva_short",
      "roc_long", "roc_medium", "roc_short",
      "roc_live_interbar", "roc_live_intrabar",
      "atr_long", "atr_medium", "atr_short",
      "live_pip_range", "live_velocity", "candle_direction",
      "mode"
   );

   // --- Trade Header
   FileWrite(trade_file,
      "timestamp", "symbol", "event_type", "order_type",
      "volume", "price", "slippage", "position_id",
      "rva_long", "rva_medium", "rva_short",
      "roc_long", "roc_medium", "roc_short",
      "roc_live_interbar", "roc_live_intrabar",
      "atr_long", "atr_medium", "atr_short",
      "live_pip_range", "live_velocity", "candle_direction",
      "floating_pnl", "open_trades", "open_buys", "open_sells",
      "balance", "equity", "drawdown",
      "mode"
   );

   FileFlush(tick_file);
   FileFlush(trade_file);

   Print("✅ tradeCorelogger v2.2 initialized");
   return(INIT_SUCCEEDED);
}

// ===================== TICK LOGGER =====================

void OnTick()
{
   if(!LOGGING_ENABLED)
      return;

   MqlTick tick;
   if(!SymbolInfoTick(_Symbol, tick))
      return;

   double spread      = tick.ask - tick.bid;
   double delta_price = 0;
   long   delta_time  = 0;

   if(prev_time_msc != 0)
   {
      delta_price = tick.bid - prev_last;
      delta_time  = tick.time_msc - prev_time_msc;
   }

   prev_last     = tick.bid;
   prev_time_msc = tick.time_msc;

   MarketMetrics m = GetMetrics(tick.bid);
   string ts = TimeToString(tick.time, TIME_SECONDS);

   FileWrite(tick_file,
      ts, tick.time_msc, _Symbol,
      tick.bid, tick.ask, tick.bid, tick.volume, spread,
      delta_price, delta_time,
      m.rva_long, m.rva_medium, m.rva_short,
      m.roc_long, m.roc_medium, m.roc_short,
      m.roc_live_interbar, m.roc_live_intrabar,
      m.atr_long, m.atr_medium, m.atr_short,
      m.live_pip_range, m.live_velocity, m.candle_direction,
      EnumToString(CURRENT_MODE)
   );

   FileFlush(tick_file);
}

// ===================== TRADE LOGGER =====================

void OnTradeTransaction(const MqlTradeTransaction& trans,
                        const MqlTradeRequest&     request,
                        const MqlTradeResult&      result)
{
   if(!LOGGING_ENABLED)
      return;

   string ts = TimeToString(TimeCurrent(), TIME_SECONDS);

   double slippage = 0;
   if(request.price > 0 && result.price > 0)
      slippage = result.price - request.price;

   MqlTick tick;
   SymbolInfoTick(_Symbol, tick);
   MarketMetrics m  = GetMetrics(tick.bid);
   PositionStats ps = GetPositionStats();

   // Account info — native MT5 functions, no math needed
   double balance  = AccountInfoDouble(ACCOUNT_BALANCE);
   double equity   = AccountInfoDouble(ACCOUNT_EQUITY);
   double drawdown = equity - balance; // negative = in drawdown

   FileWrite(trade_file,
      ts, trans.symbol,
      EnumToString(trans.type), EnumToString(request.type),
      trans.volume, trans.price, slippage, trans.position,
      m.rva_long, m.rva_medium, m.rva_short,
      m.roc_long, m.roc_medium, m.roc_short,
      m.roc_live_interbar, m.roc_live_intrabar,
      m.atr_long, m.atr_medium, m.atr_short,
      m.live_pip_range, m.live_velocity, m.candle_direction,
      ps.floating_pnl, ps.open_trades, ps.open_buys, ps.open_sells,
      balance, equity, drawdown,
      EnumToString(CURRENT_MODE)
   );

   FileFlush(trade_file);
}

// ===================== CLEANUP =====================

void OnDeinit(const int reason)
{
   if(h_atr_long   != INVALID_HANDLE) IndicatorRelease(h_atr_long);
   if(h_atr_medium != INVALID_HANDLE) IndicatorRelease(h_atr_medium);
   if(h_atr_short  != INVALID_HANDLE) IndicatorRelease(h_atr_short);

   if(tick_file  != INVALID_HANDLE) FileClose(tick_file);
   if(trade_file != INVALID_HANDLE) FileClose(trade_file);

   Print("🛑 tradeCorelogger v2.2 stopped");
}
