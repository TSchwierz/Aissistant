package com.healthscale.app.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.healthscale.app.brief.MorningBrief

@Composable
fun MorningBriefScreen(
    loading: Boolean,
    error: String?,
    brief: MorningBrief?,
    speaking: Boolean,
    serverUrl: String,
    onRetry: () -> Unit,
    onSpeak: () -> Unit,
    onStopSpeak: () -> Unit,
    onOpenDashboard: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text(
            text = "Morning brief",
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.SemiBold,
        )
        Text(
            text = "From $serverUrl — no music; TTS speaks the Pi script only.",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f),
        )

        when {
            loading -> {
                Spacer(Modifier.height(24.dp))
                CircularProgressIndicator(modifier = Modifier.align(Alignment.CenterHorizontally))
                Text("Fetching brief…", modifier = Modifier.align(Alignment.CenterHorizontally))
            }
            error != null -> {
                Text(
                    text = error,
                    color = MaterialTheme.colorScheme.error,
                )
                Button(onClick = onRetry, modifier = Modifier.fillMaxWidth()) {
                    Text("Retry")
                }
            }
            brief != null -> {
                Text(
                    text = "${brief.date} · ${brief.timezone}",
                    style = MaterialTheme.typography.labelLarge,
                )
                if (brief.emptyReason != null && brief.sections.isEmpty()) {
                    Text(
                        text = "Nothing useful yet (${brief.emptyReason}). Calm empty morning.",
                        style = MaterialTheme.typography.bodyLarge,
                    )
                }
                brief.sections.forEach { section ->
                    Text(
                        text = section.title,
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold,
                    )
                    Text(
                        text = section.body,
                        style = MaterialTheme.typography.bodyLarge,
                    )
                    Spacer(Modifier.height(4.dp))
                }
                if (brief.script.isNotBlank()) {
                    Text(
                        text = "Script",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold,
                    )
                    Text(
                        text = brief.script,
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.85f),
                    )
                }
                Spacer(Modifier.height(8.dp))
                if (speaking) {
                    OutlinedButton(onClick = onStopSpeak, modifier = Modifier.fillMaxWidth()) {
                        Text("Stop speaking")
                    }
                } else {
                    Button(
                        onClick = onSpeak,
                        enabled = brief.script.isNotBlank(),
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text("Speak brief")
                    }
                }
                OutlinedButton(onClick = onRetry, modifier = Modifier.fillMaxWidth()) {
                    Text("Refresh")
                }
                Button(onClick = onOpenDashboard, modifier = Modifier.fillMaxWidth()) {
                    Text("Open dashboard")
                }
            }
        }
    }
}
