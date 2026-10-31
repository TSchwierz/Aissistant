package com.healthscale.app.ui

import android.content.Intent
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.healthscale.app.HealthScaleApp
import com.healthscale.app.MorningBriefActivity

@Composable
fun SettingsScreen(vm: MeasureViewModel) {
    val state by vm.state.collectAsStateWithLifecycle()
    var url by remember(state.serverUrl) { mutableStateOf(state.serverUrl) }
    val context = LocalContext.current
    val app = context.applicationContext as HealthScaleApp
    val savedKey by app.settings.apiKey.collectAsStateWithLifecycle(initialValue = "")
    var apiKey by remember(savedKey) { mutableStateOf(savedKey) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Text(
            text = "Settings",
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.SemiBold,
        )
        Text(
            text = "Point the phone at your Pi Personal AIssistent on the home LAN. Example: http://192.168.178.23:8741 (Health + climate + brief).",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f),
        )

        OutlinedTextField(
            value = url,
            onValueChange = { url = it },
            label = { Text("Pi server URL") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )

        OutlinedTextField(
            value = apiKey,
            onValueChange = { apiKey = it },
            label = { Text("API key") },
            singleLine = true,
            visualTransformation = PasswordVisualTransformation(),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
            modifier = Modifier.fillMaxWidth(),
        )

        Button(
            onClick = {
                vm.saveServerUrl(url)
            },
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text("Save URL")
        }

        Button(
            onClick = { vm.saveApiKey(apiKey) },
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text("Save API key")
        }

        OutlinedButton(
            onClick = {
                vm.saveServerUrl(url)
                vm.testConnection(url, apiKey)
            },
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text("Test connection")
        }

        Button(
            onClick = {
                vm.saveServerUrl(url)
                vm.syncNow()
            },
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text("Sync pending (${state.pendingCount})")
        }

        if (state.syncMessage.isNotBlank()) {
            Text(
                text = state.syncMessage,
                style = MaterialTheme.typography.bodyMedium,
            )
        }

        ScaleListenWindowSettings(state.serverUrl.trim())

        OutlinedButton(
            onClick = {
                vm.saveServerUrl(url)
                context.startActivity(Intent(context, MorningBriefActivity::class.java))
            },
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text("Open morning brief")
        }
        Text(
            text = "Modes & Routines deep link: personaissistent://morning",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f),
        )
    }
}
