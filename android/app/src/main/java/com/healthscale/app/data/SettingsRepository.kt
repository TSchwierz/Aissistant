package com.healthscale.app.data

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

private val Context.dataStore by preferencesDataStore("settings")

class SettingsRepository(private val context: Context) {
    private val serverUrlKey = stringPreferencesKey("server_url")

    val serverUrl: Flow<String> = context.dataStore.data.map { prefs ->
        // Unified Personal AIssistent Pi process (was Health hub :8000).
        prefs[serverUrlKey] ?: "http://192.168.178.23:8741"
    }

    suspend fun setServerUrl(url: String) {
        context.dataStore.edit { it[serverUrlKey] = url.trim().trimEnd('/') }
    }
}
