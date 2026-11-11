package com.healthscale.app.api

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject
import java.io.File
import java.security.MessageDigest
import java.util.concurrent.TimeUnit

data class AppRelease(
    val available: Boolean,
    val versionCode: Long,
    val versionName: String,
    val sha256: String,
    val bytes: Long,
) {
    companion object {
        fun none() = AppRelease(false, 0, "", "", 0)
    }
}

class AppReleaseClient(
    http: OkHttpClient = apiHttpClient(connectSeconds = 10, readSeconds = 30),
) {
    private val http: OkHttpClient = http.newBuilder()
        .followRedirects(false)
        .followSslRedirects(false)
        .readTimeout(10, TimeUnit.MINUTES)
        .writeTimeout(10, TimeUnit.MINUTES)
        .callTimeout(15, TimeUnit.MINUTES)
        .build()
        .withApiKey()

    suspend fun release(baseUrl: String): AppRelease = withContext(Dispatchers.IO) {
        val root = JSONObject(get(baseUrl, "/app/release"))
        if (!root.optBoolean("available")) return@withContext AppRelease.none()
        val versionCode = root.optLong("versionCode")
        val versionName = root.optString("versionName").trim()
        val sha256 = root.optString("sha256").trim().lowercase()
        val bytes = root.optLong("bytes")
        if (versionCode < 1 || versionName.isEmpty() || !sha256.matches(SHA256) || bytes < 1) {
            error("The Pi release description is incomplete")
        }
        AppRelease(
            available = true,
            versionCode = versionCode,
            versionName = versionName,
            sha256 = sha256,
            bytes = bytes,
        )
    }

    suspend fun downloadApk(
        baseUrl: String,
        dest: File,
        release: AppRelease,
        onProgress: (read: Long, total: Long) -> Unit,
    ) = withContext(Dispatchers.IO) {
        if (!release.available || !release.sha256.matches(SHA256) || release.bytes < 1) {
            error("The Pi release description is incomplete")
        }
        val folder = dest.parentFile ?: error("Could not store the update")
        folder.mkdirs()
        val partial = File(folder, dest.name + ".partial")
        var committed = false
        try {
            val request = Request.Builder().url(root(baseUrl) + "/app/apk").get().build()
            http.newCall(request).execute().use { response ->
                if (response.code in 300..399) error("The Pi refused to send the APK directly")
                if (!response.isSuccessful) {
                    fail(response.code, response.body?.string().orEmpty())
                }
                val body = response.body ?: error("The Pi returned an empty APK")
                val total = when {
                    body.contentLength() > 0 -> body.contentLength()
                    else -> release.bytes
                }
                body.byteStream().use { input ->
                    partial.outputStream().use { output ->
                        val buffer = ByteArray(64 * 1024)
                        var read = 0L
                        var nextReport = 0L
                        while (true) {
                            val count = input.read(buffer)
                            if (count < 0) break
                            output.write(buffer, 0, count)
                            read += count
                            if (read >= nextReport || (total > 0 && read >= total)) {
                                val snapshot = read
                                withContext(Dispatchers.Main) { onProgress(snapshot, total) }
                                nextReport = read + (256 * 1024)
                            }
                        }
                    }
                }
            }
            if (partial.length() != release.bytes) error("The download stopped early")
            if (!sha256(partial).equals(release.sha256, ignoreCase = true)) {
                error("The download did not match the release on the Pi")
            }
            if (dest.exists() && !dest.delete()) error("Could not replace the previous download")
            if (!partial.renameTo(dest)) {
                partial.copyTo(dest, overwrite = true)
                if (!partial.delete() && partial.exists()) partial.delete()
            }
            committed = true
        } finally {
            if (!committed) partial.delete()
        }
    }

    private fun get(baseUrl: String, path: String): String {
        val request = Request.Builder().url(root(baseUrl) + path).get().build()
        return http.newCall(request).execute().use { response ->
            val text = response.body?.string().orEmpty()
            if (response.code in 300..399) error("The Pi refused to send the release directly")
            if (!response.isSuccessful) fail(response.code, text)
            text
        }
    }

    private fun root(baseUrl: String): String = baseUrl.trim().trimEnd('/')

    private fun fail(code: Int, body: String): Nothing {
        if (code == 401) error("API key rejected")
        val detail = runCatching { JSONObject(body).optString("detail") }.getOrNull()
        val message = detail?.takeIf { it.isNotBlank() } ?: body.take(180)
        error("HTTP $code: $message")
    }

    private fun sha256(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        file.inputStream().use { input ->
            val buffer = ByteArray(64 * 1024)
            while (true) {
                val count = input.read(buffer)
                if (count < 0) break
                digest.update(buffer, 0, count)
            }
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }

    companion object {
        private val SHA256 = Regex("^[0-9a-f]{64}$")
    }
}
