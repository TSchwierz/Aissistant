package com.healthscale.app.calendar

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

class CalendarReminderReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        if (intent?.action == Intent.ACTION_BOOT_COMPLETED) {
            val pending = goAsync()
            Thread {
                try {
                    CalendarReminderScheduler.rescheduleFromCache(context.applicationContext)
                } finally {
                    pending.finish()
                }
            }.start()
            return
        }
        val title = intent?.getStringExtra(CalendarReminderScheduler.EXTRA_TITLE) ?: return
        val body = intent.getStringExtra(CalendarReminderScheduler.EXTRA_BODY).orEmpty()
        val id = intent.getIntExtra(CalendarReminderScheduler.EXTRA_ID, 0)
        CalendarReminderScheduler.notify(context.applicationContext, id, title, body)
    }
}
