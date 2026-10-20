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
    private val themeModeKey = stringPreferencesKey("theme_mode")
    private val themeAccentKey = stringPreferencesKey("theme_accent")

    val serverUrl: Flow<String> = context.dataStore.data.map { prefs ->
        // Unified Personal AIssistent Pi process (was Health hub :8000).
        prefs[serverUrlKey] ?: "http://192.168.178.23:8741"
    }

    val themeMode: Flow<String> = context.dataStore.data.map { prefs ->
        normalizeMode(prefs[themeModeKey])
    }

    val themeAccent: Flow<String> = context.dataStore.data.map { prefs ->
        normalizeAccent(prefs[themeAccentKey])
    }

    suspend fun setServerUrl(url: String) {
        context.dataStore.edit { it[serverUrlKey] = url.trim().trimEnd('/') }
    }

    suspend fun setThemeMode(mode: String) {
        context.dataStore.edit { it[themeModeKey] = normalizeMode(mode) }
    }

    suspend fun setThemeAccent(accent: String) {
        context.dataStore.edit { it[themeAccentKey] = normalizeAccent(accent) }
    }

    private fun normalizeMode(mode: String?): String = when (mode) {
        "system", "dark", "light" -> mode
        else -> "dark"
    }

    private fun normalizeAccent(accent: String?): String = when (accent) {
        "teal", "blue", "amber", "rose" -> accent
        else -> "teal"
    }
}
