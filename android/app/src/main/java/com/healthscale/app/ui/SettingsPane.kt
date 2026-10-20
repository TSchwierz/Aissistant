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
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.Button
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.healthscale.app.HealthScaleApp
import com.healthscale.app.api.HubClient
import com.healthscale.app.ui.theme.accentColor
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
    val mode by app.settings.themeMode.collectAsStateWithLifecycle(initialValue = "dark")
    val accent by app.settings.themeAccent.collectAsStateWithLifecycle(initialValue = "teal")

    fun startBackup(notificationsOn: Boolean) {
        val base = draft.trim()
        if (base.isBlank()) {
            message = "Enter a Pi server URL"
            return
        }
        message = runCatching {
            val name = enqueueBackup(context, base)
            if (notificationsOn) {
                "Backup download started ($name)"
            } else {
                "Backup download started ($name). Notifications are off, so progress may stay hidden."
            }
        }.getOrElse { it.message ?: "Could not start the download" }
    }

    val notificationPermission = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { granted ->
        startBackup(granted)
    }

    SectionColumn {
        Text("Settings", style = MaterialTheme.typography.headlineSmall)
        Text(
            "Pi server, backup, and appearance for this phone.",
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        OutlinedTextField(
            value = draft,
            onValueChange = { draft = it },
            modifier = Modifier.fillMaxWidth(),
            label = { Text("Pi server URL") },
            singleLine = true,
        )
        Button(onClick = { onSaveUrl(draft.trim()) }) { Text("Save URL") }
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
                    message = runCatching { "Connected: ${client.ping(base)}" }
                        .getOrElse { it.message ?: "Connection failed" }
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
    val manager = context.getSystemService(DownloadManager::class.java)
        ?: error("Download manager is unavailable")
    manager.enqueue(request)
    return fileName
}
