package com.healthscale.app.brief

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import com.healthscale.app.api.apiHttpClient
import com.healthscale.app.api.withApiKey
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONArray
import org.json.JSONObject

data class BriefSection(
    val id: String,
    val title: String,
    val body: String,
)

data class MorningBrief(
    val date: String,
    val timezone: String,
    val sectionsPresent: List<String>,
    val emptyReason: String?,
    val script: String,
    val sections: List<BriefSection>,
    val rawJson: String,
)

class BriefClient(
    http: OkHttpClient = apiHttpClient(),
) {
    private val http: OkHttpClient = http.withApiKey()

    suspend fun fetchMorningBrief(
        baseUrl: String,
        date: String? = null,
        refresh: Boolean = false,
    ): Result<MorningBrief> = withContext(Dispatchers.IO) {
        runCatching {
            val root = baseUrl.trimEnd('/')
            val qs = buildString {
                val parts = mutableListOf<String>()
                if (!date.isNullOrBlank()) parts += "date=$date"
                if (refresh) parts += "refresh=1"
                if (parts.isNotEmpty()) append("?").append(parts.joinToString("&"))
            }
            val req = Request.Builder()
                .url("$root/briefing/morning$qs")
                .get()
                .build()
            http.newCall(req).execute().use { resp ->
                val body = resp.body?.string().orEmpty()
                if (resp.code == 401) error("API key rejected")
                if (!resp.isSuccessful) error("HTTP ${resp.code}: $body")
                parse(body)
            }
        }
    }

    private fun parse(body: String): MorningBrief {
        val root = JSONObject(body)
        val meta = root.optJSONObject("meta") ?: JSONObject()
        val sectionsArr = root.optJSONArray("sections") ?: JSONArray()
        val sections = buildList {
            for (i in 0 until sectionsArr.length()) {
                val s = sectionsArr.getJSONObject(i)
                add(
                    BriefSection(
                        id = s.optString("id"),
                        title = s.optString("title"),
                        body = s.optString("body"),
                    ),
                )
            }
        }
        val presentArr = meta.optJSONArray("sections_present") ?: JSONArray()
        val present = buildList {
            for (i in 0 until presentArr.length()) add(presentArr.getString(i))
        }
        val empty = if (meta.isNull("empty_reason")) null else meta.optString("empty_reason", null)
        return MorningBrief(
            date = meta.optString("date"),
            timezone = meta.optString("timezone"),
            sectionsPresent = present,
            emptyReason = empty,
            script = root.optString("script"),
            sections = sections,
            rawJson = body,
        )
    }
}
