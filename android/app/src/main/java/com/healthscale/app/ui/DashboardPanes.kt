package com.healthscale.app.ui

import android.content.Intent
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
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
import com.healthscale.app.MorningBriefActivity
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
