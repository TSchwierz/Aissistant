package com.healthscale.app.api

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject
data class HourlyForecastPoint(
    val ts: String,
    val temperatureC: Double?,
    val humidityPct: Double?,
    val condition: String?,
    val conditionLabel: String,
    val precipitationProbability: Double?,
    val windKph: Double?,
    val providerCount: Int,
    val fetchedAt: String?,
)

data class HourlyForecast(
    val timezone: String,
    val windowHours: Int,
    val from: String,
    val to: String,
    val points: List<HourlyForecastPoint>,
)

/** GET /climate/outside/hourly. Separate from HubClient so that client stays unchanged. */
class ForecastClient(
    http: OkHttpClient = apiHttpClient(),
) {
    private val http: OkHttpClient = http.withApiKey()

    suspend fun hourly(baseUrl: String): HourlyForecast = withContext(Dispatchers.IO) {
        val request = Request.Builder()
            .url(baseUrl.trimEnd('/') + "/climate/outside/hourly")
            .get()
            .build()
        http.newCall(request).execute().use { response ->
            val text = response.body?.string().orEmpty()
            if (response.code == 401) error("API key rejected")
            if (!response.isSuccessful) {
                error("HTTP ${response.code}: ${text.take(180)}")
            }
            parseHourly(JSONObject(text))
        }
    }
}

private fun parseHourly(root: JSONObject): HourlyForecast {
    val points = root.optJSONArray("points")
    val rows = if (points == null) {
        emptyList()
    } else {
        (0 until points.length()).map { index -> pointFrom(points.getJSONObject(index)) }
    }
    return HourlyForecast(
        timezone = root.optString("timezone").ifBlank { "Europe/Berlin" },
        windowHours = root.optInt("window_hours", 24).takeIf { it > 0 } ?: 24,
        from = root.optString("from"),
        to = root.optString("to"),
        points = rows,
    )
}

private fun pointFrom(obj: JSONObject) = HourlyForecastPoint(
    ts = obj.optString("ts"),
    temperatureC = obj.optDoubleOrNull("temperature_c"),
    humidityPct = obj.optDoubleOrNull("humidity_pct"),
    condition = obj.optStringOrNull("condition"),
    conditionLabel = obj.optString("condition_label"),
    precipitationProbability = obj.optDoubleOrNull("precipitation_probability"),
    windKph = obj.optDoubleOrNull("wind_kph"),
    providerCount = obj.optInt("provider_count"),
    fetchedAt = obj.optStringOrNull("fetched_at"),
)

private fun JSONObject.optStringOrNull(key: String): String? {
    if (!has(key) || isNull(key)) return null
    return optString(key).ifBlank { null }
}

private fun JSONObject.optDoubleOrNull(key: String): Double? {
    if (!has(key) || isNull(key)) return null
    val value = optDouble(key)
    return if (value.isNaN()) null else value
}
