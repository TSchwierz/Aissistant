package com.healthscale.app

import android.app.Application
import com.healthscale.app.data.AppDatabase
import com.healthscale.app.data.SettingsRepository
import com.healthscale.app.sync.SyncClient

class HealthScaleApp : Application() {
    lateinit var database: AppDatabase
        private set
    lateinit var settings: SettingsRepository
        private set
    lateinit var syncClient: SyncClient
        private set

    override fun onCreate() {
        super.onCreate()
        database = AppDatabase.get(this)
        settings = SettingsRepository(this)
        syncClient = SyncClient(database.pendingDao())
    }
}
