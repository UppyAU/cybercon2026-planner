package expo.modules.exactalarm

import android.app.AlarmManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.provider.Settings
import expo.modules.kotlin.modules.Module
import expo.modules.kotlin.modules.ModuleDefinition

// Android 12+ only fires scheduled notifications on the minute when the app may use exact alarms,
// and Android 14 turns that off by default ("Alarms & reminders" in the app's settings).
// expo-notifications checks canScheduleExactAlarms() itself and falls back to an inexact alarm,
// which Doze can push back by several minutes: too late for "your session starts in 5 min".
class ExactAlarmModule : Module() {
  override fun definition() = ModuleDefinition {
    Name("ExactAlarm")

    Function("canSchedule") {
      if (Build.VERSION.SDK_INT < Build.VERSION_CODES.S) return@Function true
      val am = appContext.reactContext?.getSystemService(Context.ALARM_SERVICE) as? AlarmManager
      am?.canScheduleExactAlarms() ?: false
    }

    // Opens this app's "Alarms & reminders" switch.
    Function("openSettings") {
      if (Build.VERSION.SDK_INT < Build.VERSION_CODES.S) return@Function false
      val ctx = appContext.reactContext ?: return@Function false
      val intent = Intent(Settings.ACTION_REQUEST_SCHEDULE_EXACT_ALARM, Uri.parse("package:" + ctx.packageName))
        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
      ctx.startActivity(intent)
      true
    }
  }
}
