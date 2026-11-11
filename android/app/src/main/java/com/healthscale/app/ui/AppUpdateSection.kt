package com.healthscale.app.ui

import android.content.ActivityNotFoundException
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.healthscale.app.HealthScaleApp
import com.healthscale.app.api.AppRelease
import com.healthscale.app.api.AppReleaseClient
import com.healthscale.app.update.AppUpdate
import com.healthscale.app.update.InstalledApp
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlin.coroutines.coroutineContext

@Composable
internal fun AppUpdateSection(baseUrl: String) {
    val context = LocalContext.current
    val app = context.applicationContext as HealthScaleApp
    val client = remember { AppReleaseClient() }
    val installed = remember { AppUpdate.installed(context) }
    val scope = rememberCoroutineScope()
    val savedKey by app.settings.apiKey.collectAsStateWithLifecycle(initialValue = "")
    var release by remember(baseUrl) { mutableStateOf<AppRelease?>(null) }
    var status by remember(baseUrl) { mutableStateOf("Checking for an update…") }
    var statusIsError by remember(baseUrl) { mutableStateOf(false) }
    var checking by remember(baseUrl) { mutableStateOf(false) }
    var downloading by remember(baseUrl) { mutableStateOf(false) }

    suspend fun check() {
        if (baseUrl.isBlank()) {
            release = null
            status = "Save a Pi server URL first"
            statusIsError = true
            return
        }
        checking = true
        statusIsError = false
        status = "Checking for an update…"
        try {
            val found = client.release(baseUrl)
            release = found
            status = describe(installed, found)
            statusIsError = false
        } catch (error: CancellationException) {
            throw error
        } catch (error: Exception) {
            release = null
            status = error.message ?: "Could not check for an update"
            statusIsError = true
        } finally {
            if (coroutineContext.isActive) checking = false
        }
    }

    LaunchedEffect(baseUrl, savedKey) {
        check()
    }

    val newer = release?.takeIf { it.available && it.versionCode > installed.versionCode }

    Column(
        modifier = Modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Text("App update", style = MaterialTheme.typography.titleMedium)
        Text(
            "A newer signed APK on the Pi can be installed from here. Android still asks you to confirm.",
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(
            status,
            color = if (statusIsError) {
                MaterialTheme.colorScheme.error
            } else {
                MaterialTheme.colorScheme.onSurface
            },
        )
        if (newer != null) {
            Button(
                onClick = {
                    if (!AppUpdate.canInstallPackages(context)) {
                        status = "Allow this app to install unknown apps, then tap Update again."
                        statusIsError = true
                        runCatching { AppUpdate.openInstallPermission(context) }
                            .onFailure { error ->
                                status = error.message ?: "Could not open install settings"
                            }
                        return@Button
                    }
                    downloading = true
                    statusIsError = false
                    status = "Downloading…"
                    scope.launch {
                        try {
                            val apk = AppUpdate.apkFile(context)
                            client.downloadApk(baseUrl, apk, newer) { read, total ->
                                status = downloadStatus(read, total)
                            }
                            AppUpdate.startInstall(context, apk)
                            status = "Confirm the install on the next screen."
                            statusIsError = false
                        } catch (error: CancellationException) {
                            throw error
                        } catch (error: ActivityNotFoundException) {
                            status = "This phone has no installer that can open the APK."
                            statusIsError = true
                        } catch (error: Exception) {
                            status = error.message ?: "Could not download the update"
                            statusIsError = true
                        } finally {
                            if (coroutineContext.isActive) downloading = false
                        }
                    }
                },
                enabled = !checking && !downloading && baseUrl.isNotBlank(),
            ) { Text(if (downloading) "Downloading…" else "Update to ${newer.versionName}") }
        }
        OutlinedButton(
            onClick = { scope.launch { check() } },
            enabled = !checking && !downloading && baseUrl.isNotBlank(),
        ) { Text(if (checking) "Checking…" else "Check again") }
    }
}

private fun describe(installed: InstalledApp, release: AppRelease): String {
    val local = "${installed.versionName} (${installed.versionCode})"
    if (!release.available) {
        return "Installed $local. No build is published on the Pi yet."
    }
    val remote = "${release.versionName} (${release.versionCode})"
    return when {
        release.versionCode > installed.versionCode ->
            "Installed $local. The Pi has $remote."
        release.versionCode == installed.versionCode ->
            "Installed $local. That is the build on the Pi."
        else ->
            "Installed $local. The Pi has an older build, $remote."
    }
}

private fun downloadStatus(read: Long, total: Long): String {
    val done = megabytes(read)
    return if (total > 0) "Downloading $done of ${megabytes(total)}" else "Downloading $done"
}

private fun megabytes(bytes: Long): String = "%.1f MB".format(bytes / (1024.0 * 1024.0))
