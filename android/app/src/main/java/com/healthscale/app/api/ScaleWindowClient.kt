package com.healthscale.app.api

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
data class ScaleWindowStatus(
    val startHour: Int,
    val endHour: Int,
    val window: String,
    val mode: String,
    val phase: String,
    val detail: String,
)

class ScaleWindowClient(
    http: OkHttpClient = apiHttpClient(),
) {
    private val http: OkHttpClient = http.withApiKey()

    suspend fun status(baseUrl: String): ScaleWindowStatus = withContext(Dispatchers.IO) {
        parse(send(baseUrl, "GET", "/api/scale", null))
    }

    suspend fun save(baseUrl: String, startHour: Int, endHour: Int): ScaleWindowStatus =
        withContext(Dispatchers.IO) {
            val body = JSONObject()
                .put("start_hour", startHour)
                .put("end_hour", endHour)
            parse(send(baseUrl, "POST", "/api/scale/window", body.toString()))
        }

    private fun send(baseUrl: String, method: String, path: String, json: String?): String {
        val builder = Request.Builder().url(baseUrl.trim().trimEnd('/') + path)
        if (json == null) builder.method(method, null)
        else builder.method(method, json.toRequestBody(JSON_MEDIA))
        return http.newCall(builder.build()).execute().use { response ->
            val text = response.body?.string().orEmpty()
            if (!response.isSuccessful) fail(response.code, text)
            text
        }
    }

    private fun parse(body: String): ScaleWindowStatus {
        val root = JSONObject(body)
        if (!root.has("start_hour") || root.isNull("start_hour") || !root.has("end_hour") || root.isNull("end_hour")) {
            error("Scale status did not include the listen window")
        }
        val startHour = root.getInt("start_hour")
        val endHour = root.getInt("end_hour")
        val window = root.optString("window").ifBlank {
            "%02d:00-%02d:00".format(startHour, endHour)
        }
        return ScaleWindowStatus(
            startHour = startHour,
            endHour = endHour,
            window = window,
            mode = root.optString("mode").ifBlank { "auto" },
            phase = root.optString("phase"),
            detail = root.optString("detail"),
        )
    }

    private fun fail(code: Int, body: String): Nothing {
        if (code == 401) error("API key rejected")
        val detail = runCatching { JSONObject(body).opt("detail") }.getOrNull()
        val message = when (detail) {
            is String -> detail
            is JSONArray -> (0 until detail.length()).joinToString("; ") { index ->
                when (val item = detail.opt(index)) {
                    is JSONObject -> item.optString("msg").ifBlank { item.toString() }
                    is String -> item
                    else -> item?.toString().orEmpty()
                }
            }.ifBlank { body.take(180) }
            is JSONObject -> detail.optString("message").ifBlank { detail.toString().take(180) }
            else -> body.take(180)
        }
        error("HTTP $code: $message")
    }

    companion object {
        private val JSON_MEDIA = "application/json; charset=utf-8".toMediaType()
    }
}
