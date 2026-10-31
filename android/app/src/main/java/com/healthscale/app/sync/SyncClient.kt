package com.healthscale.app.sync

import com.healthscale.app.data.PendingMeasurement
import com.healthscale.app.data.PendingMeasurementDao
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import com.healthscale.app.api.apiHttpClient
import com.healthscale.app.api.withApiKey
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.time.Instant

class SyncClient(
    private val dao: PendingMeasurementDao,
    http: OkHttpClient = apiHttpClient(readSeconds = 15),
) {
    private val http: OkHttpClient = http.withApiKey()

    suspend fun testConnection(baseUrl: String): Result<String> = withContext(Dispatchers.IO) {
        runCatching {
            val req = Request.Builder().url("${baseUrl.trimEnd('/')}/api/health").get().build()
            http.newCall(req).execute().use { resp ->
                if (resp.code == 401) error("API key rejected")
                if (!resp.isSuccessful) error("HTTP ${resp.code}")
                resp.body?.string() ?: "ok"
            }
        }
    }

    suspend fun syncPending(baseUrl: String): Result<SyncResult> = withContext(Dispatchers.IO) {
        runCatching {
            val pending = dao.getUnsynced()
            if (pending.isEmpty()) return@runCatching SyncResult(0, 0)

            val array = JSONArray()
            pending.forEach { array.put(it.toJson()) }
            val body = array.toString().toRequestBody(JSON)
            val req = Request.Builder()
                .url("${baseUrl.trimEnd('/')}/api/measurements")
                .post(body)
                .build()

            http.newCall(req).execute().use { resp ->
                if (resp.code == 401) error("API key rejected")
                if (!resp.isSuccessful) {
                    error("HTTP ${resp.code}: ${resp.body?.string()}")
                }
                pending.forEach { dao.markSynced(it.clientId) }
                dao.deleteSynced()
                SyncResult(synced = pending.size, failed = 0)
            }
        }
    }

    private fun PendingMeasurement.toJson(): JSONObject =
        JSONObject()
            .put("client_id", clientId)
            .put("measured_at", Instant.ofEpochMilli(measuredAtEpochMs).toString())
            .put("weight_kg", weightKg)
            .put("impedance_ohm", impedanceOhm ?: JSONObject.NULL)
            .put("unit", unit)
            .put("scale_mac", scaleMac ?: JSONObject.NULL)
            .put("raw_hex", rawHex)

    companion object {
        private val JSON = "application/json; charset=utf-8".toMediaType()
    }
}

data class SyncResult(val synced: Int, val failed: Int)
