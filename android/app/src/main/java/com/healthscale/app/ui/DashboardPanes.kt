package com.healthscale.app.ui

import android.content.Intent
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
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
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.healthscale.app.MorningBriefActivity
import com.healthscale.app.api.ClimateSnapshot
import com.healthscale.app.api.HealthSnapshot
import com.healthscale.app.api.HubClient
import com.healthscale.app.api.MorningBrief
import com.healthscale.app.api.NewsDigestRow
import com.healthscale.app.api.NewsTopicRow
import kotlinx.coroutines.launch

@Composable
fun BriefPane(baseUrl: String) {
    val client = remember { HubClient() }
    val context = LocalContext.current
    var brief by remember { mutableStateOf<MorningBrief?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var loading by remember { mutableStateOf(true) }

    suspend fun load() {
        loading = true
        error = null
        try {
            brief = client.morningBrief(baseUrl)
        } catch (e: Exception) {
            error = e.message
        } finally {
            loading = false
        }
    }

    LaunchedEffect(baseUrl) { load() }

    Pane(title = "Morning brief", lede = "Pi-composed script. Speech stays on the phone.", onRefresh = { load() }, loading = loading, error = error) {
        Button(onClick = {
            context.startActivity(Intent(context, MorningBriefActivity::class.java))
        }) { Text("Read aloud") }
        brief?.let { item ->
            Text(item.date, style = MaterialTheme.typography.titleMedium)
            if (!item.emptyReason.isNullOrBlank()) {
                Text("Empty reason: ${item.emptyReason}", color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Card(Modifier.fillMaxWidth()) {
                Text(item.script.ifBlank { "—" }, Modifier.padding(12.dp))
            }
            item.sections.forEach { section ->
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text(section.title, style = MaterialTheme.typography.titleMedium)
                        Text(section.body)
                    }
                }
            }
        }
    }
}

@Composable
fun ClimatePane(baseUrl: String) {
    val client = remember { HubClient() }
    var snap by remember { mutableStateOf<ClimateSnapshot?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var loading by remember { mutableStateOf(true) }
    suspend fun load() {
        loading = true
        error = null
        try {
            snap = client.climate(baseUrl)
        } catch (e: Exception) {
            error = e.message
        } finally {
            loading = false
        }
    }
    LaunchedEffect(baseUrl) { load() }
    Pane(
        title = "Climate",
        lede = "Studio readings. Settings stay on the PC.",
        onRefresh = { load() },
        loading = loading,
        error = error,
    ) {
        snap?.let { item ->
            StatRow("Indoor", item.tempC?.let { "%.1f°C".format(it) } ?: "—", item.humidity?.let { "%.0f%%".format(it) } ?: "—")
            Text("Status: ${item.status ?: "—"}")
            Text("Outside: ${item.outside ?: "—"}")
        }
    }
}

@Composable
fun HealthPane(baseUrl: String) {
    val client = remember { HubClient() }
    var snap by remember { mutableStateOf<HealthSnapshot?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var loading by remember { mutableStateOf(true) }
    suspend fun load() {
        loading = true
        error = null
        try {
            snap = client.health(baseUrl)
        } catch (e: Exception) {
            error = e.message
        } finally {
            loading = false
        }
    }
    LaunchedEffect(baseUrl) { load() }
    Pane(
        title = "Health",
        lede = "The Pi records the scale from 06:00 to 12:00, then stops for the day.",
        onRefresh = { load() },
        loading = loading,
        error = error,
    ) {
        snap?.let { item ->
            StatRow("Latest", item.latestKg?.let { "%.1f kg".format(it) } ?: "—", "7d ${item.avg7?.let { "%.1f".format(it) } ?: "—"}")
            Text("Measurements: ${item.count}")
            Text("BMI: ${item.bmi?.let { "%.1f".format(it) } ?: "—"} · fat ${item.bodyFat?.let { "%.1f%".format(it) } ?: "—"}")
            Text("Profile: ${item.profileName.ifBlank { "—" }} · ${if (item.profileComplete) "complete" else "incomplete"}")
            if (!item.scalePhase.isNullOrBlank()) {
                Text("Scale: ${item.scalePhase}${item.scaleDetail?.let { " — $it" } ?: ""}")
            }
        }
    }
}

@Composable
fun NewsPane(baseUrl: String) {
    val client = remember { HubClient() }
    var topics by remember { mutableStateOf<List<NewsTopicRow>>(emptyList()) }
    var digests by remember { mutableStateOf<List<NewsDigestRow>>(emptyList()) }
    var error by remember { mutableStateOf<String?>(null) }
    var loading by remember { mutableStateOf(true) }
    suspend fun load() {
        loading = true
        error = null
        try {
            topics = client.newsTopics(baseUrl)
            digests = runCatching { client.newsDigests(baseUrl) }.getOrElse {
                error = it.message
                emptyList()
            }
        } catch (e: Exception) {
            error = e.message
        } finally {
            loading = false
        }
    }
    LaunchedEffect(baseUrl) { load() }
    Pane(
        title = "News",
        lede = "Digests from the Pi. Topics are edited on the PC.",
        onRefresh = { load() },
        loading = loading,
        error = error,
    ) {
        Text("Topics (${topics.size})", style = MaterialTheme.typography.titleMedium)
        if (topics.isEmpty()) Text("No topics yet.")
        topics.forEach { topic ->
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(12.dp)) {
                    Text("${topic.label} (${topic.id})", style = MaterialTheme.typography.titleMedium)
                    if (topic.goal.isNotBlank()) Text(topic.goal)
                    Text(
                        "${topic.schedule} · ${topic.feeds} feeds · last ${topic.lastRun ?: "—"}",
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }
        Text("Latest digests", style = MaterialTheme.typography.titleMedium)
        if (digests.isEmpty()) Text("No digests for today yet.")
        digests.forEach { digest ->
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text("${digest.label} · ${digest.status}", style = MaterialTheme.typography.titleMedium)
                    Text(digest.digest)
                    Text("${digest.itemCount} items", color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
    }
}

@Composable
fun ConnectionPane(url: String, onSave: (String) -> Unit) {
    val client = remember { HubClient() }
    val scope = rememberCoroutineScope()
    var draft by remember(url) { mutableStateOf(url) }
    var message by remember { mutableStateOf<String?>(null) }
    Column(
        Modifier
            .fillMaxWidth()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("Pi server", style = MaterialTheme.typography.headlineSmall)
        Text(
            "Only the server address lives on the phone. Topic, climate, and profile settings are edited on the PC.",
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        OutlinedTextField(
            value = draft,
            onValueChange = { draft = it },
            modifier = Modifier.fillMaxWidth(),
            label = { Text("Pi server URL") },
            singleLine = true,
        )
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = { onSave(draft.trim()) }) { Text("Save URL") }
            OutlinedButton(onClick = {
                scope.launch {
                    message = runCatching { "Connected: ${client.ping(draft.trim())}" }
                        .getOrElse { it.message ?: "Offline" }
                }
            }) { Text("Test") }
        }
        if (!message.isNullOrBlank()) Text(message!!)
    }
}

@Composable
private fun Pane(
    title: String,
    lede: String,
    onRefresh: suspend () -> Unit,
    loading: Boolean,
    error: String?,
    content: @Composable () -> Unit,
) {
    val scope = rememberCoroutineScope()
    Column(
        Modifier
            .fillMaxWidth()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Text(title, style = MaterialTheme.typography.headlineSmall)
        Text(lede, color = MaterialTheme.colorScheme.onSurfaceVariant)
        OutlinedButton(onClick = { scope.launch { onRefresh() } }) { Text("Refresh") }
        if (loading) Text("Loading…")
        if (!error.isNullOrBlank()) Text(error, color = MaterialTheme.colorScheme.error)
        content()
    }
}

@Composable
private fun StatRow(label: String, primary: String, secondary: String) {
    Column {
        Text(label, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(primary, style = MaterialTheme.typography.headlineSmall)
        Text(secondary, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}
