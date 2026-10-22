package com.healthscale.app.api

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
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

data class ClimateReading(
    val tempC: Double?,
    val humidity: Double?,
    val status: String?,
)

data class ClimatePoint(
    val ts: String,
    val temperatureC: Double?,
    val humidityPct: Double?,
)

data class ProviderReport(
    val name: String,
    val ok: Boolean,
    val error: String?,
    val temperatureC: Double?,
    val humidityPct: Double?,
    val condition: String?,
)

data class ClimateOutside(
    val reports: List<ProviderReport>,
    val ventilationReason: String?,
)

data class ClimateSettings(
    val humidityMin: Double?,
    val humidityMax: Double?,
    val tempMin: Double?,
    val tempMax: Double?,
    val sampleIntervalSeconds: Int?,
)

data class ScaleListener(
    val mode: String,
    val line: String,
)

data class BodyMeasurement(
    val id: Long,
    val measuredAt: String,
    val weightKg: Double,
    val bodyFatPct: Double?,
    val muscleMassKg: Double?,
)

data class HealthProfile(
    val name: String,
    val heightCm: Double?,
    val age: Int?,
    val sex: String?,
    val activityLevel: String,
    val targetFatPct: Double?,
    val mealsPerDay: Int,
    val targetCalories: Double?,
    val proteinG: Double?,
    val fiberG: Double?,
)

data class MacroTotals(
    val kcal: Double,
    val proteinG: Double,
    val carbsG: Double,
    val fatG: Double,
    val fiberG: Double,
)

data class DayTargets(
    val targetCalories: Double?,
    val proteinG: Double?,
    val fiberG: Double?,
)

data class MealItem(
    val name: String,
    val grams: Double,
    val kcal: Double,
    val proteinG: Double,
    val carbsG: Double,
    val fatG: Double,
    val fiberG: Double,
    val source: String,
    val sourceId: String?,
)

data class MealEntry(
    val id: Long,
    val eatenAt: String,
    val note: String,
    val source: String,
    val items: List<MealItem>,
)

data class MealDay(
    val day: String,
    val totals: MacroTotals,
    val targets: DayTargets?,
    val meals: List<MealEntry>,
)

data class FoodHit(
    val name: String,
    val source: String,
    val sourceId: String?,
    val kcal100g: Double,
    val protein100g: Double,
    val carbs100g: Double,
    val fat100g: Double,
    val fiber100g: Double,
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

    suspend fun climateCurrent(baseUrl: String): ClimateReading = io {
        val root = jsonObject(baseUrl, "/climate/current")
        val measurement = root.optJSONObject("measurement")
        ClimateReading(
            tempC = measurement?.optDoubleOrNull("temperature_c"),
            humidity = measurement?.optDoubleOrNull("humidity_pct"),
            status = root.optJSONObject("status")?.optString("overall")?.ifBlank { null },
        )
    }

    suspend fun climateHistory(baseUrl: String, fromIso: String? = null): List<ClimatePoint> = io {
        val path = buildString {
            append("/climate/measurements?limit=50000")
            if (!fromIso.isNullOrBlank()) append("&from=").append(encode(fromIso))
        }
        jsonObject(baseUrl, path)
            .optJSONArray("measurements")
            .objects { point ->
                ClimatePoint(
                    ts = point.optString("ts"),
                    temperatureC = point.optDoubleOrNull("temperature_c"),
                    humidityPct = point.optDoubleOrNull("humidity_pct"),
                )
            }
    }

    suspend fun climateOutside(baseUrl: String): ClimateOutside = io {
        outsideFrom(jsonObject(baseUrl, "/climate/outside"))
    }

    suspend fun refreshClimateOutside(baseUrl: String): ClimateOutside = io {
        outsideFrom(requestObject(baseUrl, "POST", "/climate/outside/refresh", JSONObject()))
    }

    suspend fun climateSettings(baseUrl: String): ClimateSettings = io {
        climateSettingsFrom(jsonObject(baseUrl, "/climate/settings"))
    }

    suspend fun updateClimateSettings(
        baseUrl: String,
        humidityMin: Double,
        humidityMax: Double,
        tempMin: Double,
        tempMax: Double,
        sampleIntervalSeconds: Int,
    ): ClimateSettings = io {
        val body = JSONObject()
            .put("humidity_min", humidityMin)
            .put("humidity_max", humidityMax)
            .put("temp_min", tempMin)
            .put("temp_max", tempMax)
            .put("sample_interval_seconds", sampleIntervalSeconds)
        climateSettingsFrom(requestObject(baseUrl, "PUT", "/climate/settings", body))
    }

    suspend fun scaleListener(baseUrl: String): ScaleListener = io {
        listenerFrom(jsonObject(baseUrl, "/api/scale"))
    }

    suspend fun setScaleMode(baseUrl: String, action: String): ScaleListener = io {
        val body = JSONObject().put("action", action)
        listenerFrom(requestObject(baseUrl, "POST", "/api/scale/mode", body))
    }

    suspend fun bodyMeasurements(baseUrl: String, limit: Int = 500): List<BodyMeasurement> = io {
        jsonArray(baseUrl, "/api/measurements?limit=$limit").objects { row ->
            BodyMeasurement(
                id = row.optLong("id"),
                measuredAt = row.optString("measured_at"),
                weightKg = row.optDoubleOrNull("weight_kg") ?: 0.0,
                bodyFatPct = row.optDoubleOrNull("body_fat_pct"),
                muscleMassKg = row.optDoubleOrNull("muscle_mass_kg"),
            )
        }
    }

    suspend fun deleteBodyMeasurement(baseUrl: String, id: Long) = io {
        send(baseUrl, "DELETE", "/api/measurements/$id", null)
        Unit
    }

    suspend fun healthProfile(baseUrl: String): HealthProfile = io {
        profileFrom(jsonObject(baseUrl, "/api/profile"))
    }

    suspend fun saveHealthProfile(baseUrl: String, profile: HealthProfile): HealthProfile = io {
        val body = JSONObject()
            .put("name", profile.name)
            .put("height_cm", profile.heightCm ?: JSONObject.NULL)
            .put("age", profile.age ?: JSONObject.NULL)
            .put("sex", profile.sex ?: JSONObject.NULL)
            .put("activity_level", profile.activityLevel)
            .put("target_fat_pct", profile.targetFatPct ?: JSONObject.NULL)
            .put("meals_per_day", profile.mealsPerDay)
        profileFrom(requestObject(baseUrl, "PUT", "/api/profile", body))
    }

    suspend fun mealSummary(baseUrl: String, day: String): MealDay = io {
        val root = jsonObject(baseUrl, "/api/meals/summary?day=${encode(day)}")
        val totals = root.optJSONObject("totals")
        val targets = root.optJSONObject("targets")
        MealDay(
            day = root.optString("day").ifBlank { day },
            totals = MacroTotals(
                kcal = totals?.optDoubleOrNull("kcal") ?: 0.0,
                proteinG = totals?.optDoubleOrNull("protein_g") ?: 0.0,
                carbsG = totals?.optDoubleOrNull("carbs_g") ?: 0.0,
                fatG = totals?.optDoubleOrNull("fat_g") ?: 0.0,
                fiberG = totals?.optDoubleOrNull("fiber_g") ?: 0.0,
            ),
            targets = targets?.let {
                DayTargets(
                    targetCalories = it.optDoubleOrNull("target_calories"),
                    proteinG = it.optDoubleOrNull("protein_g"),
                    fiberG = it.optDoubleOrNull("fiber_g"),
                )
            },
            meals = root.optJSONArray("meals").objects { mealFrom(it) },
        )
    }

    suspend fun parseFoods(baseUrl: String, text: String): List<MealItem> = io {
        val root = requestObject(baseUrl, "POST", "/api/nutrition/parse", JSONObject().put("text", text))
        root.optJSONArray("items").objects { mealItemFrom(it) }
    }

    suspend fun parseFoodImage(baseUrl: String, jpeg: ByteArray): List<MealItem> = io {
        val body = MultipartBody.Builder()
            .setType(MultipartBody.FORM)
            .addFormDataPart(
                "image",
                "meal.jpg",
                jpeg.toRequestBody("image/jpeg".toMediaType()),
            )
            .build()
        val request = Request.Builder()
            .url(baseUrl.trim().trimEnd('/') + "/api/nutrition/parse-image")
            .post(body)
            .build()
        val caller = http.newBuilder()
            .readTimeout(90, TimeUnit.SECONDS)
            .callTimeout(120, TimeUnit.SECONDS)
            .build()
        val text = caller.newCall(request).execute().use { resp ->
            val raw = resp.body?.string().orEmpty()
            if (!resp.isSuccessful) fail(resp.code, raw)
            raw
        }
        JSONObject(text).optJSONArray("items").objects { mealItemFrom(it) }
    }

    suspend fun saveMeal(
        baseUrl: String,
        eatenAt: String,
        note: String,
        source: String,
        items: List<MealItem>,
    ) = io {
        val body = JSONObject()
            .put("eaten_at", eatenAt)
            .put("note", note)
            .put("source", when (source) {
                "barcode", "photo" -> source
                else -> "text"
            })
            .put("items", JSONArray().apply { items.forEach { put(it.toJson()) } })
        requestObject(baseUrl, "POST", "/api/meals", body)
        Unit
    }

    suspend fun deleteMeal(baseUrl: String, id: Long) = io {
        send(baseUrl, "DELETE", "/api/meals/$id", null)
        Unit
    }

    suspend fun searchFoods(baseUrl: String, query: String): List<FoodHit> = io {
        jsonObject(baseUrl, "/api/foods/search?q=${encode(query)}")
            .optJSONArray("foods")
            .objects { foodFrom(it) }
    }

    suspend fun foodByBarcode(baseUrl: String, code: String): FoodHit = io {
        foodFrom(jsonObject(baseUrl, "/api/foods/barcode/${encode(code)}"))
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

    private suspend fun requestObject(
        baseUrl: String,
        method: String,
        path: String,
        body: JSONObject?,
    ): JSONObject {
        val text = send(baseUrl, method, path, body?.toString())
        return if (text.isBlank()) JSONObject() else JSONObject(text)
    }

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
            is JSONObject -> detail.optString("message").ifBlank { detail.toString().take(180) }
            else -> body.take(180)
        }
        error("HTTP $code: $message")
    }

    private fun encode(value: String): String = URLEncoder.encode(value, Charsets.UTF_8.name())

    private fun outsideFrom(root: JSONObject) = ClimateOutside(
        reports = root.optJSONArray("provider_reports").objects { report ->
            ProviderReport(
                name = report.optString("name"),
                ok = report.optBoolean("ok"),
                error = report.optString("error").ifBlank { null },
                temperatureC = report.optDoubleOrNull("temperature_c"),
                humidityPct = report.optDoubleOrNull("humidity_pct"),
                condition = report.optString("condition").ifBlank { null },
            )
        },
        ventilationReason = root.optJSONObject("comparison")
            ?.optJSONObject("ventilation")
            ?.optString("reason")
            ?.ifBlank { null },
    )

    private fun climateSettingsFrom(obj: JSONObject) = ClimateSettings(
        humidityMin = obj.optDoubleOrNull("humidity_min"),
        humidityMax = obj.optDoubleOrNull("humidity_max"),
        tempMin = obj.optDoubleOrNull("temp_min"),
        tempMax = obj.optDoubleOrNull("temp_max"),
        sampleIntervalSeconds = obj.optDoubleOrNull("sample_interval_seconds")?.toInt(),
    )

    private fun listenerFrom(root: JSONObject): ScaleListener {
        val mode = root.optString("mode").ifBlank { "auto" }
        val window = root.optString("window")
        val phase = root.optString("phase")
        val detail = root.optString("detail")
        val head = listOf(mode, window, phase).filter { it.isNotBlank() }.joinToString(" · ")
        val line = if (detail.isBlank()) head else "$head — $detail"
        return ScaleListener(mode = mode, line = line)
    }

    private fun profileFrom(obj: JSONObject): HealthProfile {
        val nutrition = obj.optJSONObject("nutrition")
        val sex = obj.optString("sex").ifBlank { null }
        return HealthProfile(
            name = obj.optString("name"),
            heightCm = obj.optDoubleOrNull("height_cm"),
            age = obj.optIntOrNull("age"),
            sex = if (sex == "male" || sex == "female") sex else null,
            activityLevel = obj.optString("activity_level").ifBlank { "moderate" },
            targetFatPct = obj.optDoubleOrNull("target_fat_pct"),
            mealsPerDay = (obj.optIntOrNull("meals_per_day") ?: 3).coerceIn(1, 8),
            targetCalories = nutrition?.optDoubleOrNull("target_calories"),
            proteinG = nutrition?.optDoubleOrNull("protein_g"),
            fiberG = nutrition?.optDoubleOrNull("fiber_g"),
        )
    }

    private fun mealFrom(obj: JSONObject) = MealEntry(
        id = obj.optLong("id"),
        eatenAt = obj.optString("eaten_at"),
        note = obj.optString("note"),
        source = obj.optString("source"),
        items = obj.optJSONArray("items").objects { mealItemFrom(it) },
    )

    private fun mealItemFrom(obj: JSONObject) = MealItem(
        name = obj.optString("name"),
        grams = obj.optDoubleOrNull("grams") ?: 0.0,
        kcal = obj.optDoubleOrNull("kcal") ?: 0.0,
        proteinG = obj.optDoubleOrNull("protein_g") ?: 0.0,
        carbsG = obj.optDoubleOrNull("carbs_g") ?: 0.0,
        fatG = obj.optDoubleOrNull("fat_g") ?: 0.0,
        fiberG = obj.optDoubleOrNull("fiber_g") ?: 0.0,
        source = obj.optString("source"),
        sourceId = obj.optFlexibleString("source_id"),
    )

    private fun foodFrom(obj: JSONObject) = FoodHit(
        name = obj.optString("name"),
        source = obj.optString("source"),
        sourceId = obj.optFlexibleString("source_id"),
        kcal100g = obj.optDoubleOrNull("kcal_100g") ?: 0.0,
        protein100g = obj.optDoubleOrNull("protein_100g") ?: 0.0,
        carbs100g = obj.optDoubleOrNull("carbs_100g") ?: 0.0,
        fat100g = obj.optDoubleOrNull("fat_100g") ?: 0.0,
        fiber100g = obj.optDoubleOrNull("fiber_100g") ?: 0.0,
    )

    private fun MealItem.toJson(): JSONObject {
        val obj = JSONObject()
            .put("name", name)
            .put("grams", round2(grams))
            .put("kcal", round2(kcal))
            .put("protein_g", round2(proteinG))
            .put("carbs_g", round2(carbsG))
            .put("fat_g", round2(fatG))
            .put("fiber_g", round2(fiberG))
            .put("source", foodSource(source))
        if (sourceId.isNullOrBlank()) obj.put("source_id", JSONObject.NULL)
        else obj.put("source_id", sourceId)
        return obj
    }

    private fun foodSource(value: String): String = when (value) {
        "ciqual", "off", "manual" -> value
        else -> "manual"
    }

    private fun round2(value: Double): Double {
        if (value.isNaN() || value.isInfinite()) return 0.0
        return kotlin.math.round(value * 100.0) / 100.0
    }

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

private fun JSONObject.optIntOrNull(key: String): Int? {
    if (!has(key) || isNull(key)) return null
    return optInt(key)
}

private fun JSONObject.optFlexibleString(key: String): String? {
    if (!has(key) || isNull(key)) return null
    val value = get(key)
    val text = when (value) {
        is Number -> {
            val asLong = value.toLong()
            if (value.toDouble() == asLong.toDouble()) asLong.toString() else value.toString()
        }
        else -> value.toString()
    }
    return text.ifBlank { null }
}
