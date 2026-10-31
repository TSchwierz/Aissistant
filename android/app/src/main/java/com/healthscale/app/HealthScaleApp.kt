package com.healthscale.app

import android.app.Application
import com.healthscale.app.data.ApiKeyStore
import com.healthscale.app.data.AppDatabase
import com.healthscale.app.data.SettingsRepository
import com.healthscale.app.sync.SyncClient
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking

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
        runBlocking(Dispatchers.IO) {
            ApiKeyStore.apiKey = settings.apiKey.first()
        }
        syncClient = SyncClient(database.pendingDao())
    }
}
