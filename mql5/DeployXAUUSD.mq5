//+------------------------------------------------------------------+
//| DeployXAUUSD.mq5                                                  |
//| Opens XAUUSD M15 chart and applies xauusd5min.tpl template        |
//+------------------------------------------------------------------+
#property script_show_inputs

void OnStart()
{
   Print("[DEPLOY] Opening XAUUSD M15...");
   long chart_id = ChartOpen("XAUUSD", PERIOD_M15);
   if(chart_id == 0) {
      Print("[DEPLOY] FAIL ChartOpen err=", GetLastError());
      return;
   }
   Sleep(3000);

   Print("[DEPLOY] Applying xauusd5min.tpl...");
   bool ok = ChartApplyTemplate(chart_id, "xauusd5min.tpl");
   if(ok) {
      Print("[DEPLOY] SUCCESS - EA deployed on XAUUSD M15");
   } else {
      Print("[DEPLOY] FAIL template err=", GetLastError());
   }
}
