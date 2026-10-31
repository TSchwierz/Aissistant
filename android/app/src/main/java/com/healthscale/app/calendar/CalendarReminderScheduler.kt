package com.healthscale.app.calendar

import android.app.AlarmManager
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import com.healthscale.app.MainActivity
import com.healthscale.app.R
import com.healthscale.app.api.CalEvent
import com.healthscale.app.api.CalList
import com.healthscale.app.api.parseCalendarList
import com.healthscale.app.data.AppDatabase
import kotlinx.coroutines.runBlocking
import org.json.JSONObject
import java.time.LocalDateTime
import java.time.OffsetDateTime
import java.time.ZoneId

object CalendarReminderScheduler {
    const val ACTION_REMIND = "com.healthscale.app.CALENDAR_REMINDER"
    const val EXTRA_TITLE = "title"
    const val EXTRA_BODY = "body"
    const val EXTRA_ID = "notificationId"
    private const val CHANNEL_ID = "calendar_reminders"
    private const val PREFS = "calendar_reminders"
    private const val KEY_CODES = "codes"

    fun rescheduleFromCache(context: Context) {
        val appContext = context.applicationContext
        val row = runBlocking { AppDatabase.get(appContext).calendarCacheDao().get() } ?: return
        val list = runCatching { parseCalendarList(JSONObject(row.payloadJson)) }.getOrNull() ?: return
        reschedule(appContext, list)
    }

    fun reschedule(context: Context, list: CalList) {
        val appContext = context.applicationContext
        val manager = appContext.getSystemService(AlarmManager::class.java) ?: return
        val prefs = appContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val previous = prefs.getString(KEY_CODES, "").orEmpty().split(',').mapNotNull { it.toIntOrNull() }
        previous.forEach { code ->
            val pending = pendingIntent(appContext, code, null, null)
            manager.cancel(pending)
            pending.cancel()
        }
        ensureChannel(appContext)
        val codes = mutableListOf<Int>()
        var code = 1
        val now = System.currentTimeMillis()
        for (event in list.events) {
            val at = reminderAtMillis(event, list.timezone) ?: continue
            if (at <= now) continue
            val body = if (event.allDay) {
                "All day · ${event.start.take(10)}"
            } else {
                "Starts ${event.start.drop(11).take(5)}"
            }
            val pending = pendingIntent(appContext, code, event.title, body)
            schedule(manager, at, pending)
            codes += code
            code += 1
        }
        prefs.edit().putString(KEY_CODES, codes.joinToString(",")).apply()
    }

    fun notify(context: Context, id: Int, title: String, body: String) {
        ensureChannel(context)
        val open = PendingIntent.getActivity(
            context,
            0,
            Intent(context, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val notification = NotificationCompat.Builder(context, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_stat_calendar)
            .setContentTitle(title)
            .setContentText(body)
            .setContentIntent(open)
            .setAutoCancel(true)
            .setCategory(NotificationCompat.CATEGORY_REMINDER)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .build()
        try {
            NotificationManagerCompat.from(context).notify(id, notification)
        } catch (_: SecurityException) {
            /* permission not granted; the event is still on the calendar */
        }
    }

    private fun schedule(manager: AlarmManager, triggerAt: Long, pending: PendingIntent) {
        val exactAllowed = Build.VERSION.SDK_INT < 31 || manager.canScheduleExactAlarms()
        try {
            if (exactAllowed) {
                manager.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, triggerAt, pending)
            } else {
                manager.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, triggerAt, pending)
            }
        } catch (_: SecurityException) {
            manager.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, triggerAt, pending)
        }
    }

    private fun pendingIntent(context: Context, code: Int, title: String?, body: String?): PendingIntent {
        val intent = Intent(context, CalendarReminderReceiver::class.java).apply {
            action = ACTION_REMIND
            if (title != null) {
                putExtra(EXTRA_TITLE, title)
                putExtra(EXTRA_BODY, body)
                putExtra(EXTRA_ID, code)
            }
        }
        return PendingIntent.getBroadcast(
            context,
            code,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
    }

    private fun ensureChannel(context: Context) {
        if (Build.VERSION.SDK_INT < 26) return
        val manager = context.getSystemService(NotificationManager::class.java) ?: return
        if (manager.getNotificationChannel(CHANNEL_ID) != null) return
        val channel = NotificationChannel(
            CHANNEL_ID,
            "Calendar reminders",
            NotificationManager.IMPORTANCE_HIGH,
        )
        channel.description = "Reminders for upcoming calendar events"
        manager.createNotificationChannel(channel)
    }

    private fun reminderAtMillis(event: CalEvent, timezone: String): Long? {
        val minutes = event.remindBeforeMinutes ?: return null
        if (minutes <= 0) return null
        val start = runCatching { eventStartMillis(event.start, timezone) }.getOrNull() ?: return null
        return start - minutes * 60_000L
    }

    private fun eventStartMillis(iso: String, timezone: String): Long {
        val zone = runCatching { ZoneId.of(timezone.ifBlank { "Europe/Berlin" }) }
            .getOrDefault(ZoneId.of("Europe/Berlin"))
        val text = iso.trim()
        runCatching { return OffsetDateTime.parse(text).toInstant().toEpochMilli() }
        val local = if (text.length >= 19) text.take(19) else text
        return LocalDateTime.parse(local).atZone(zone).toInstant().toEpochMilli()
    }
}
