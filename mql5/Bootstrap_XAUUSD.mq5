//+------------------------------------------------------------------+
//| Bootstrap_XAUUSD.mq5                                              |
//+------------------------------------------------------------------+
#property script_show_inputs
void OnStart()
{
   Print("[BOOT] Opening XAUUSD M15...");
   long chart_id = ChartOpen("XAUUSD", PERIOD_M15);
   if(chart_id == 0) { Print("[BOOT] FAIL err=", GetLastError()); return; }
   Sleep(3000);
   Print("[BOOT] Applying template...");
   bool ok = ChartApplyTemplate(chart_id, "xauusd5min.tpl");
   Print("[BOOT] ", ok ? "SUCCESS" : ("FAIL err=" + IntegerToString(GetLastError())));
}
