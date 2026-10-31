package com.healthscale.app.ui

import android.Manifest
import android.app.DownloadManager
import android.content.Context
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Environment
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.Button
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.healthscale.app.HealthScaleApp
import com.healthscale.app.api.HubClient
import com.healthscale.app.data.ApiKeyStore
import com.healthscale.app.api.ScaleWindowClient
import com.healthscale.app.ui.theme.accentColor
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.launch
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter

@Composable
fun SettingsPane(url: String, onSaveUrl: (String) -> Unit) {
    val context = LocalContext.current
    val app = context.applicationContext as HealthScaleApp
    val client = remember { HubClient() }
    val scope = rememberCoroutineScope()
    var draft by remember(url) { mutableStateOf(url) }
    var message by remember { mutableStateOf<String?>(null) }
    var testing by remember { mutableStateOf(false) }
    val savedKey by app.settings.apiKey.collectAsStateWithLifecycle(initialValue = "")
    var keyDraft by remember { mutableStateOf<String?>(null) }
    val mode by app.settings.themeMode.collectAsStateWithLifecycle(initialValue = "dark")
    val accent by app.settings.themeAccent.collectAsStateWithLifecycle(initialValue = "teal")

    fun typedKey(): String = (keyDraft ?: savedKey).trim()

    fun startBackup(notificationsOn: Boolean) {
        val base = draft.trim()
        if (base.isBlank()) {
            message = "Enter a Pi server URL"
            return
        }
        val key = typedKey()
        scope.launch {
            app.settings.setApiKey(key)
            message = runCatching {
                val name = enqueueBackup(context, base)
                if (notificationsOn) {
                    "Backup download started ($name)"
                } else {
                    "Backup download started ($name). Notifications are off, so progress may stay hidden."
                }
            }.getOrElse { it.message ?: "Could not start the download" }
        }
    }

    val notificationPermission = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { granted ->
        startBackup(granted)
    }

    SectionColumn {
        Text("Settings", style = MaterialTheme.typography.headlineSmall)
        Text(
            "Pi server, API key, backup, and appearance for this phone. The key stays on this phone.",
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        OutlinedTextField(
            value = draft,
            onValueChange = { draft = it },
            modifier = Modifier.fillMaxWidth(),
            label = { Text("Pi server URL") },
            singleLine = true,
        )
        OutlinedTextField(
            value = keyDraft ?: savedKey,
            onValueChange = { keyDraft = it },
            modifier = Modifier.fillMaxWidth(),
            label = { Text("API key") },
            singleLine = true,
            visualTransformation = PasswordVisualTransformation(),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
        )
        Button(onClick = { onSaveUrl(draft.trim()) }) { Text("Save URL") }
        Button(onClick = {
            scope.launch {
                app.settings.setApiKey(typedKey())
                keyDraft = typedKey()
                message = "API key saved"
            }
        }) { Text("Save API key") }
        OutlinedButton(
            onClick = {
                val base = draft.trim()
                if (base.isBlank()) {
                    message = "Enter a Pi server URL"
                    return@OutlinedButton
                }
                testing = true
                message = null
                scope.launch {
                    app.settings.setApiKey(typedKey())
                    message = runCatching { "Connected: ${client.ping(base)}" }
                        .getOrElse { connectionFailure(it) }
                    testing = false
                }
            },
            enabled = !testing,
        ) { Text(if (testing) "Testing…" else "Test connection") }
        OutlinedButton(onClick = {
            if (Build.VERSION.SDK_INT >= 33 &&
                ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) !=
                PackageManager.PERMISSION_GRANTED
            ) {
                notificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
            } else {
                startBackup(true)
            }
        }) { Text("Download backup") }
        if (!message.isNullOrBlank()) Text(message!!)

        ScaleListenWindowSettings(url.trim())

        Text("Appearance", style = MaterialTheme.typography.titleMedium)
        Text("Mode", color = MaterialTheme.colorScheme.onSurfaceVariant)
        Row(
            Modifier.horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            listOf("system" to "System", "dark" to "Dark", "light" to "Light").forEach { (id, label) ->
                FilterChip(
                    selected = mode == id,
                    onClick = { scope.launch { app.settings.setThemeMode(id) } },
                    label = { Text(label) },
                )
            }
        }
        Text("Accent", color = MaterialTheme.colorScheme.onSurfaceVariant)
        Row(
            Modifier.horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            listOf("teal" to "Teal", "blue" to "Blue", "amber" to "Amber", "rose" to "Rose").forEach { (id, label) ->
                FilterChip(
                    selected = accent == id,
                    onClick = { scope.launch { app.settings.setThemeAccent(id) } },
                    label = {
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(6.dp),
                        ) {
                            Box(
                                Modifier
                                    .size(12.dp)
                                    .clip(MaterialTheme.shapes.small)
                                    .background(accentColor(id)),
                            )
                            Text(label)
                        }
                    },
                )
            }
        }
    }
}

@Composable
internal fun ScaleListenWindowSettings(baseUrl: String) {
    val client = remember { ScaleWindowClient() }
    val scope = rememberCoroutineScope()
    var startText by remember(baseUrl) { mutableStateOf("") }
    var endText by remember(baseUrl) { mutableStateOf("") }
    var windowLabel by remember(baseUrl) { mutableStateOf<String?>(null) }
    var message by remember(baseUrl) { mutableStateOf<String?>(null) }
    var messageIsError by remember(baseUrl) { mutableStateOf(false) }
    var busy by remember(baseUrl) { mutableStateOf(false) }
    var loaded by remember(baseUrl) { mutableStateOf(false) }

    LaunchedEffect(baseUrl) {
        if (baseUrl.isBlank()) {
            message = "Save a Pi server URL first"
            messageIsError = true
            loaded = true
            return@LaunchedEffect
        }
        try {
            val saved = client.status(baseUrl)
            startText = saved.startHour.toString()
            endText = saved.endHour.toString()
            windowLabel = saved.window
            message = null
            messageIsError = false
        } catch (error: CancellationException) {
            throw error
        } catch (error: Exception) {
            message = error.message ?: "Could not load the scale window"
            messageIsError = true
        }
        loaded = true
    }

    Column(
        modifier = Modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Text("Scale listen window", style = MaterialTheme.typography.titleMedium)
        Text(
            if (windowLabel.isNullOrBlank()) {
                "Whole hours on the Pi. Listening starts at the start hour and stops before the end hour, same day. Today's reading still ends the scan."
            } else {
                "Pi window $windowLabel. Whole hours, same day. Today's reading still ends the scan."
            },
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        OutlinedTextField(
            value = startText,
            onValueChange = { startText = it },
            modifier = Modifier.fillMaxWidth(),
            label = { Text("Start hour") },
            singleLine = true,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
        )
        OutlinedTextField(
            value = endText,
            onValueChange = { endText = it },
            modifier = Modifier.fillMaxWidth(),
            label = { Text("End hour") },
            singleLine = true,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
        )
        Button(
            onClick = {
                val start = startText.trim().toIntOrNull()
                val end = endText.trim().toIntOrNull()
                if (start == null || end == null || start !in 0..23 || end !in 0..23) {
                    message = "Use whole hours from 0 to 23"
                    messageIsError = true
                    return@Button
                }
                if (end <= start) {
                    message = "End hour must be later than the start hour"
                    messageIsError = true
                    return@Button
                }
                if (baseUrl.isBlank()) {
                    message = "Save a Pi server URL first"
                    messageIsError = true
                    return@Button
                }
                busy = true
                message = null
                scope.launch {
                    try {
                        val saved = client.save(baseUrl, start, end)
                        startText = saved.startHour.toString()
                        endText = saved.endHour.toString()
                        windowLabel = saved.window
                        message = "Saved ${saved.window}"
                        messageIsError = false
                    } catch (error: CancellationException) {
                        throw error
                    } catch (error: Exception) {
                        message = error.message ?: "Could not save the scale window"
                        messageIsError = true
                    } finally {
                        busy = false
                    }
                }
            },
            enabled = loaded && !busy,
        ) { Text(if (busy) "Saving…" else "Save window") }
        if (!message.isNullOrBlank()) {
            Text(
                message!!,
                color = if (messageIsError) {
                    MaterialTheme.colorScheme.error
                } else {
                    MaterialTheme.colorScheme.onSurface
                },
            )
        }
    }
}

private fun connectionFailure(error: Throwable): String {
    val text = error.message.orEmpty()
    if (text.contains("401") || text.contains("API key rejected", ignoreCase = true)) {
        return "Auth failed: API key rejected"
    }
    return text.ifBlank { "Connection failed" }
}

private fun enqueueBackup(context: Context, baseUrl: String): String {
    val root = baseUrl.trim().trimEnd('/')
    require(root.isNotBlank()) { "Enter a Pi server URL" }
    val stamp = DateTimeFormatter.ofPattern("yyyyMMdd-HHmmss").format(LocalDateTime.now())
    val fileName = "aissistant-backup-$stamp.zip"
    val request = DownloadManager.Request(Uri.parse("$root/backup/export"))
        .setTitle("Aissistant backup")
        .setDescription(fileName)
        .setMimeType("application/zip")
        .setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
        .setAllowedOverMetered(true)
        .setDestinationInExternalFilesDir(context, Environment.DIRECTORY_DOWNLOADS, fileName)
    val key = ApiKeyStore.apiKey.trim()
    if (key.isNotEmpty() && '\n' !in key && '\r' !in key) {
        request.addRequestHeader("X-API-Token", key)
    }
    val manager = context.getSystemService(DownloadManager::class.java)
        ?: error("Download manager is unavailable")
    manager.enqueue(request)
    return fileName
}
