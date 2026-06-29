//+------------------------------------------------------------------+
//| LaunchEACharts.mq5                                               |
//| Reads ea_launch_plan.csv (TXT mode), opens charts, applies tpl.  |
//+------------------------------------------------------------------+
#property copyright "MT5 Orchestrator"
#property version   "1.00"

//+------------------------------------------------------------------+
//| Script program start function                                    |
//+------------------------------------------------------------------+
void OnStart()
{
   Print("[LAUNCHER] Starting...");
   Print("[LAUNCHER] Data folder: ", TerminalInfoString(TERMINAL_DATA_PATH));

   // --- Read entire CSV into lines (use relative path for sandbox) ---
   int fh = FileOpen("ea_launch_plan.csv", FILE_READ | FILE_TXT | FILE_ANSI);
   if(fh == INVALID_HANDLE) {
      Print("[LAUNCHER] ERROR: Cannot open ea_launch_plan.csv (err ", GetLastError(), ")");
      return;
   }

   string lines[];
   int line_count = 0;
   while(!FileIsEnding(fh)) {
      string line = FileReadString(fh);
      StringTrimLeft(line); StringTrimRight(line);
      if(StringLen(line) > 0) {
         ArrayResize(lines, line_count + 1);
         lines[line_count] = line;
         line_count++;
      }
   }
   FileClose(fh);
   Print("[LAUNCHER] Read ", line_count, " lines from CSV");

   if(line_count < 2) {
      Print("[LAUNCHER] ERROR: Not enough lines (need header + at least 1 data row)");
      return;
   }

   // --- Delete old log ---
   FileDelete("ea_launcher_log.csv");
   int log_handle = FileOpen("ea_launcher_log.csv", FILE_WRITE | FILE_CSV | FILE_ANSI, ",");
   if(log_handle == INVALID_HANDLE) {
      Print("[LAUNCHER] ERROR: Cannot create log (err ", GetLastError(), ")");
      return;
   }
   FileWrite(log_handle, "instance_id", "symbol", "timeframe", "template_name", "status", "error_code", "timestamp");

   int success_count = 0;
   int fail_count = 0;

   // Parse each data row (skip header at index 0)
   for(int i = 1; i < line_count; i++) {
      string line = lines[i];
      StringTrimLeft(line); StringTrimRight(line);

      Print("[LAUNCHER]   raw line ", i, ": [", line, "] len=", StringLen(line));

      string instance_id   = "";
      string symbol        = "";
      string timeframe_str = "";
      string template_name = "";
      string magic_str     = "";
      string enabled_str   = "";

      int p1 = StringFind(line, ",");
      if(p1 >= 0) { instance_id   = StringSubstr(line, 0, p1); line = StringSubstr(line, p1 + 1); }
      int p2 = StringFind(line, ",");
      if(p2 >= 0) { symbol        = StringSubstr(line, 0, p2); line = StringSubstr(line, p2 + 1); }
      int p3 = StringFind(line, ",");
      if(p3 >= 0) { timeframe_str = StringSubstr(line, 0, p3); line = StringSubstr(line, p3 + 1); }
      int p4 = StringFind(line, ",");
      if(p4 >= 0) { template_name = StringSubstr(line, 0, p4); line = StringSubstr(line, p4 + 1); }
      int p5 = StringFind(line, ",");
      if(p5 >= 0) { magic_str     = StringSubstr(line, 0, p5); enabled_str = StringSubstr(line, p5 + 1); }
      else        { enabled_str   = line; }

      Print("[LAUNCHER] Row ", i, ": ", instance_id, " ", symbol, " ", timeframe_str, " tpl=", template_name, " en=", enabled_str);

      if(enabled_str != "true") {
         Print("[LAUNCHER]   SKIP disabled");
         continue;
      }
      if(StringLen(symbol) == 0 || StringLen(timeframe_str) == 0 || StringLen(template_name) == 0) {
         Print("[LAUNCHER]   SKIP incomplete");
         FileWrite(log_handle, instance_id, symbol, timeframe_str, template_name, "SKIP", "INCOMPLETE", TimeToString(TimeCurrent()));
         continue;
      }

      ENUM_TIMEFRAMES tf = StringToTimeframe(timeframe_str);
      if(tf == PERIOD_CURRENT) {
         Print("[LAUNCHER]   FAIL invalid TF");
         FileWrite(log_handle, instance_id, symbol, timeframe_str, template_name, "FAIL", "INVALID_TF", TimeToString(TimeCurrent()));
         fail_count++;
         continue;
      }

      Print("[LAUNCHER]   ChartOpen ", symbol, " tf=", tf);
      long chart_id = ChartOpen(symbol, tf);
      if(chart_id == 0) {
         int err = GetLastError();
         Print("[LAUNCHER]   FAIL ChartOpen err=", err);
         FileWrite(log_handle, instance_id, symbol, timeframe_str, template_name, "FAIL", "CHART_OPEN_" + IntegerToString(err), TimeToString(TimeCurrent()));
         fail_count++;
         continue;
      }

      Sleep(2000);

      Print("[LAUNCHER]   ChartApplyTemplate ", template_name);
      bool ok = ChartApplyTemplate(chart_id, template_name);
      if(ok) {
         Print("[LAUNCHER]   SUCCESS");
         FileWrite(log_handle, instance_id, symbol, timeframe_str, template_name, "SUCCESS", "0", TimeToString(TimeCurrent()));
         success_count++;
      } else {
         int err = GetLastError();
         Print("[LAUNCHER]   FAIL template err=", err);
         FileWrite(log_handle, instance_id, symbol, timeframe_str, template_name, "FAIL", "TPL_" + IntegerToString(err), TimeToString(TimeCurrent()));
         fail_count++;
      }
   }

   FileClose(log_handle);
   Print("[LAUNCHER] DONE. Success: ", success_count, " | Failed: ", fail_count);
}

//+------------------------------------------------------------------+
ENUM_TIMEFRAMES StringToTimeframe(string tf_str)
{
   StringToUpper(tf_str);
   if(tf_str == "PERIOD_M1")    return PERIOD_M1;
   if(tf_str == "PERIOD_M2")    return PERIOD_M2;
   if(tf_str == "PERIOD_M3")    return PERIOD_M3;
   if(tf_str == "PERIOD_M4")    return PERIOD_M4;
   if(tf_str == "PERIOD_M5")    return PERIOD_M5;
   if(tf_str == "PERIOD_M6")    return PERIOD_M6;
   if(tf_str == "PERIOD_M10")   return PERIOD_M10;
   if(tf_str == "PERIOD_M12")   return PERIOD_M12;
   if(tf_str == "PERIOD_M15")   return PERIOD_M15;
   if(tf_str == "PERIOD_M20")   return PERIOD_M20;
   if(tf_str == "PERIOD_M30")   return PERIOD_M30;
   if(tf_str == "PERIOD_H1")    return PERIOD_H1;
   if(tf_str == "PERIOD_H2")    return PERIOD_H2;
   if(tf_str == "PERIOD_H3")    return PERIOD_H3;
   if(tf_str == "PERIOD_H4")    return PERIOD_H4;
   if(tf_str == "PERIOD_H6")    return PERIOD_H6;
   if(tf_str == "PERIOD_H8")    return PERIOD_H8;
   if(tf_str == "PERIOD_H12")   return PERIOD_H12;
   if(tf_str == "PERIOD_D1")    return PERIOD_D1;
   if(tf_str == "PERIOD_W1")    return PERIOD_W1;
   if(tf_str == "PERIOD_MN1")   return PERIOD_MN1;
   return PERIOD_CURRENT;
}
