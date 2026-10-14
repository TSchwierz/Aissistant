package com.healthscale.app.api

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.net.URLEncoder
import java.util.concurrent.TimeUnit

data class BriefSection(val id: String, val title: String, val body: String)

data class MorningBrief(
    val date: String,
    val script: String,
    val sections: List<BriefSection>,
    val emptyReason: String?,
)

data class CalEvent(
    val id: String,
    val title: String,
    val start: String,
    val end: String?,
    val allDay: Boolean,
    val location: String?,
    val notes: String?,
    val tags: List<String>,
)

data class CalList(
    val count: Int,
    val rangeStart: String,
    val rangeEnd: String,
    val events: List<CalEvent>,
)

data class CalDraft(
    val title: String,
    val start: String,
    val end: String?,
    val allDay: Boolean,
    val location: String?,
    val notes: String?,
    val tags: List<String>,
    val editing: Boolean,
)

data class HealthSnapshot(
    val count: Int,
    val latestKg: Double?,
    val avg7: Double?,
    val bmi: Double?,
    val bodyFat: Double?,
    val profileName: String,
    val profileComplete: Boolean,
    val scalePhase: String?,
    val scaleDetail: String?,
)

data class ClimateSnapshot(
    val tempC: Double?,
    val humidity: Double?,
    val status: String?,
    val outside: String?,
)

data class NewsTopicRow(
    val id: String,
    val label: String,
    val goal: String,
    val schedule: String,
    val feeds: Int,
    val lastRun: String?,
)

data class NewsDigestRow(
    val id: String,
    val label: String,
    val status: String,
    val digest: String,
    val itemCount: Int,
)

class HubClient(
    private val http: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(5, TimeUnit.SECONDS)
        .readTimeout(20, TimeUnit.SECONDS)
        .build(),
) {
    suspend fun morningBrief(baseUrl: String): MorningBrief = io {
        val root = jsonObject(baseUrl, "/briefing/morning")
        val meta = root.optJSONObject("meta") ?: JSONObject()
        MorningBrief(
            date = meta.optString("date"),
            script = root.optString("script"),
            sections = root.optJSONArray("sections").objects { section ->
                BriefSection(
                    id = section.optString("id"),
                    title = section.optString("title"),
                    body = section.optString("body"),
                )
            },
            emptyReason = meta.optString("empty_reason").ifBlank { null },
        )
    }

    suspend fun calendarWeeks(baseUrl: String, from: String, tag: String?): CalList = io {
        val path = buildString {
            append("/calendar/weeks?from=")
            append(from)
            if (!tag.isNullOrBlank()) append("&tag=").append(encode(tag))
        }
        parseCalendar(jsonObject(baseUrl, path))
    }

    suspend fun calendarMonth(baseUrl: String, month: String, tag: String?): CalList = io {
        val path = buildString {
            append("/calendar/month/")
            append(month)
            if (!tag.isNullOrBlank()) append("?tag=").append(encode(tag))
        }
        parseCalendar(jsonObject(baseUrl, path))
    }

    suspend fun calendarTags(baseUrl: String): List<String> = io {
        jsonObject(baseUrl, "/calendar/tags").optJSONArray("tags").strings()
    }

    suspend fun saveEvent(baseUrl: String, id: String?, draft: CalDraft) = io {
        val body = JSONObject()
            .put("title", draft.title)
            .put("start", draft.start)
            .put("all_day", draft.allDay)
            .put("tags", JSONArray(draft.tags))
        putOptional(body, "end", draft.end, draft.editing, "clear_end")
        putOptional(body, "location", draft.location, draft.editing, "clear_location")
        putOptional(body, "notes", draft.notes, draft.editing, "clear_notes")
        val path = if (id.isNullOrBlank()) "/calendar/events" else "/calendar/events/${encode(id)}"
        send(baseUrl, if (id.isNullOrBlank()) "POST" else "PUT", path, body.toString())
    }

    suspend fun deleteEvent(baseUrl: String, id: String) = io {
        send(baseUrl, "DELETE", "/calendar/events/${encode(id)}", "{}")
    }

    suspend fun climate(baseUrl: String): ClimateSnapshot = io {
        val current = jsonObject(baseUrl, "/climate/current")
        val measurement = current.optJSONObject("measurement")
        val outside = runCatching { jsonObject(baseUrl, "/climate/outside") }.getOrNull()
        val reading = outside?.optJSONObject("reading")
        val outsideText = reading?.let {
            val temp = it.optDoubleOrNull("temperature_c")?.let { value -> "${"%.1f".format(value)}°C" } ?: "—"
            val condition = it.optString("condition")
            if (condition.isBlank()) temp else "$temp · $condition"
        }
        ClimateSnapshot(
            tempC = measurement?.optDoubleOrNull("temperature_c"),
            humidity = measurement?.optDoubleOrNull("humidity_pct"),
            status = current.optJSONObject("status")?.optString("overall")?.ifBlank { null },
            outside = outsideText,
        )
    }

    suspend fun health(baseUrl: String): HealthSnapshot = io {
        val stats = jsonObject(baseUrl, "/api/stats")
        val profile = jsonObject(baseUrl, "/api/profile")
        val scale = runCatching { jsonObject(baseUrl, "/api/scale") }.getOrNull()
        val latest = stats.optJSONObject("latest")
        HealthSnapshot(
            count = stats.optInt("count"),
            latestKg = latest?.optDoubleOrNull("weight_kg"),
            avg7 = stats.optDoubleOrNull("avg_weight_7d"),
            bmi = latest?.optDoubleOrNull("bmi"),
            bodyFat = latest?.optDoubleOrNull("body_fat_pct"),
            profileName = profile.optString("name"),
            profileComplete = profile.optBoolean("is_complete"),
            scalePhase = scale?.optString("phase")?.ifBlank { null },
            scaleDetail = scale?.optString("detail")?.ifBlank { null },
        )
    }

    suspend fun newsTopics(baseUrl: String): List<NewsTopicRow> = io {
        jsonArray(baseUrl, "/news/topics").objects { topic ->
            val enabled = topic.optBoolean("schedule_enabled")
            NewsTopicRow(
                id = topic.optString("id"),
                label = topic.optString("label"),
                goal = topic.optString("goal"),
                schedule = if (enabled) {
                    "%02d:%02d".format(topic.optInt("schedule_hour"), topic.optInt("schedule_minute"))
                } else {
                    "off"
                },
                feeds = topic.optJSONArray("feed_urls")?.length() ?: 0,
                lastRun = topic.optString("last_run_status").ifBlank { null },
            )
        }
    }

    suspend fun newsDigests(baseUrl: String): List<NewsDigestRow> = io {
        jsonArray(baseUrl, "/news/digests/latest").objects { digest ->
            NewsDigestRow(
                id = digest.optString("id"),
                label = digest.optString("topic_label"),
                status = digest.optString("status"),
                digest = digest.optString("digest"),
                itemCount = digest.optInt("item_count"),
            )
        }
    }

    suspend fun ping(baseUrl: String): String = io {
        jsonObject(baseUrl, "/health").optString("status").ifBlank { "ok" }
    }

    private fun parseCalendar(root: JSONObject) = CalList(
        count = root.optInt("count"),
        rangeStart = root.optString("range_start"),
        rangeEnd = root.optString("range_end"),
        events = root.optJSONArray("events").objects { eventFrom(it) },
    )

    private fun eventFrom(obj: JSONObject) = CalEvent(
        id = obj.optString("id"),
        title = obj.optString("title"),
        start = obj.optString("start"),
        end = obj.optString("end").ifBlank { null },
        allDay = obj.optBoolean("all_day"),
        location = obj.optString("location").ifBlank { null },
        notes = obj.optString("notes").ifBlank { null },
        tags = obj.optJSONArray("tags").strings(),
    )

    private fun putOptional(
        body: JSONObject,
        key: String,
        value: String?,
        editing: Boolean,
        clearKey: String,
    ) {
        if (value.isNullOrBlank()) {
            body.put(key, JSONObject.NULL)
            if (editing) body.put(clearKey, true)
        } else {
            body.put(key, value)
        }
    }

    private suspend fun jsonObject(baseUrl: String, path: String): JSONObject =
        JSONObject(send(baseUrl, "GET", path, null))

    private suspend fun jsonArray(baseUrl: String, path: String): JSONArray =
        JSONArray(send(baseUrl, "GET", path, null))

    private suspend fun send(baseUrl: String, method: String, path: String, json: String?): String =
        withContext(Dispatchers.IO) {
            val builder = Request.Builder().url(baseUrl.trimEnd('/') + path)
            if (json == null) builder.method(method, null)
            else builder.method(method, json.toRequestBody(JSON_MEDIA))
            http.newCall(builder.build()).execute().use { resp ->
                val text = resp.body?.string().orEmpty()
                if (!resp.isSuccessful) fail(resp.code, text)
                text
            }
        }

    private fun fail(code: Int, body: String): Nothing {
        val detail = runCatching { JSONObject(body).opt("detail") }.getOrNull()
        val message = when (detail) {
            is String -> detail
            is JSONArray -> (0 until detail.length()).joinToString("; ") { index ->
                detail.optJSONObject(index)?.optString("msg")?.ifBlank { null }
                    ?: detail.optString(index)
            }
            else -> body.take(180)
        }
        error("HTTP $code: $message")
    }

    private fun encode(value: String): String = URLEncoder.encode(value, Charsets.UTF_8.name())

    private suspend fun <T> io(block: suspend () -> T): T = withContext(Dispatchers.IO) { block() }

    companion object {
        private val JSON_MEDIA = "application/json; charset=utf-8".toMediaType()
    }
}

private inline fun <T> JSONArray?.objects(block: (JSONObject) -> T): List<T> {
    if (this == null) return emptyList()
    return (0 until length()).map { block(getJSONObject(it)) }
}

private fun JSONArray?.strings(): List<String> {
    if (this == null) return emptyList()
    return (0 until length()).map { optString(it) }.filter { it.isNotBlank() }
}

private fun JSONObject.optDoubleOrNull(key: String): Double? {
    if (!has(key) || isNull(key)) return null
    val value = optDouble(key)
    return if (value.isNaN()) null else value
}
