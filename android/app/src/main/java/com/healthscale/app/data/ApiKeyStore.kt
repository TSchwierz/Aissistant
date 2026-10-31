package com.healthscale.app.data

/**
 * In-memory copy of the API key so OkHttp can attach it without reading DataStore
 * on the request thread. SettingsRepository updates this whenever the key is saved.
 */
object ApiKeyStore {
    @Volatile
    var apiKey: String = ""
}
