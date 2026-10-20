@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.healthscale.app.ui

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.ScrollableTabRow
import androidx.compose.material3.Tab
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import com.healthscale.app.api.ClimateOutside
import com.healthscale.app.api.ClimatePoint
import com.healthscale.app.api.ClimateReading
import com.healthscale.app.api.HubClient
import kotlinx.coroutines.launch

@Composable
fun ClimatePane(baseUrl: String) {
    var tab by remember { mutableIntStateOf(0) }
    val tabs = listOf("Now", "History", "Outside", "Settings")
    Column(Modifier.fillMaxSize()) {
        ScrollableTabRow(selectedTabIndex = tab) {
            tabs.forEachIndexed { index, label ->
                Tab(
                    selected = tab == index,
                    onClick = { tab = index },
                    text = { Text(label) },
                )
            }
        }
        Box(Modifier.weight(1f).fillMaxWidth()) {
            when (tab) {
                0 -> ClimateNow(baseUrl)
                1 -> ClimateHistory(baseUrl)
                2 -> ClimateOutsideTab(baseUrl)
                else -> ClimateSettingsTab(baseUrl)
            }
        }
    }
}

@Composable
private fun ClimateNow(baseUrl: String) {
    val client = remember { HubClient() }
    val scope = rememberCoroutineScope()
    var reading by remember { mutableStateOf<ClimateReading?>(null) }
    var reason by remember { mutableStateOf<String?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var loading by remember { mutableStateOf(true) }

    suspend fun load() {
        loading = true
        error = null
        val problems = mutableListOf<String>()
        reading = runCatching { client.climateCurrent(baseUrl) }.getOrElse {
            problems += it.message ?: "Could not load indoor climate"
            null
        }
        reason = runCatching { client.climateOutside(baseUrl).ventilationReason }.getOrElse {
            problems += it.message ?: "Could not load ventilation"
            null
        }
        error = problems.joinToString("\n").ifBlank { null }
        loading = false
    }

    LaunchedEffect(baseUrl) { load() }
    SectionColumn {
        OutlinedButton(onClick = { scope.launch { load() } }) { Text("Refresh") }
        if (loading) Text("Loading…")
        if (!error.isNullOrBlank()) Text(error!!, color = MaterialTheme.colorScheme.error)
        reading?.let { item ->
            Stat("Indoor temperature", formatAmount(item.tempC, "°C"))
            Stat("Humidity", formatAmount(item.humidity, "%"))
            Stat("Status", item.status ?: "—")
        }
        Text("Ventilation", color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(reason ?: "—")
    }
}

@Composable
private fun ClimateHistory(baseUrl: String) {
    val client = remember { HubClient() }
    val scope = rememberCoroutineScope()
    var points by remember { mutableStateOf<List<ClimatePoint>>(emptyList()) }
    var error by remember { mutableStateOf<String?>(null) }
    var loading by remember { mutableStateOf(true) }

    suspend fun load() {
        loading = true
        error = null
        try {
            points = client.climateHistory(baseUrl)
        } catch (e: Exception) {
            error = e.message
        } finally {
            loading = false
        }
    }

    LaunchedEffect(baseUrl) { load() }
    val temps = points.mapNotNull { it.temperatureC }
    SectionColumn {
        OutlinedButton(onClick = { scope.launch { load() } }) { Text("Refresh") }
        if (loading) Text("Loading…")
        if (!error.isNullOrBlank()) Text(error!!, color = MaterialTheme.colorScheme.error)
        if (!loading && temps.isEmpty()) {
            Text("No temperature readings yet.")
        }
        if (temps.isNotEmpty()) {
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(12.dp)) {
                    Text("Temperature", style = MaterialTheme.typography.titleMedium)
                    LineChart(temps, label = "Indoor temperature history")
                    Text(
                        "${formatAmount(temps.min(), "°C")} to ${formatAmount(temps.max(), "°C")} · ${temps.size} points",
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }
    }
}

@Composable
private fun ClimateOutsideTab(baseUrl: String) {
    val client = remember { HubClient() }
    val scope = rememberCoroutineScope()
    var outside by remember { mutableStateOf<ClimateOutside?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var loading by remember { mutableStateOf(true) }
    var refreshing by remember { mutableStateOf(false) }

    suspend fun load() {
        loading = true
        error = null
        try {
            outside = client.climateOutside(baseUrl)
        } catch (e: Exception) {
            error = e.message
        } finally {
            loading = false
        }
    }

    LaunchedEffect(baseUrl) { load() }
    SectionColumn {
        OutlinedButton(
            onClick = {
                scope.launch {
                    refreshing = true
                    error = null
                    try {
                        outside = client.refreshClimateOutside(baseUrl)
                    } catch (e: Exception) {
                        error = e.message
                    } finally {
                        refreshing = false
                    }
                }
            },
            enabled = !refreshing,
        ) { Text(if (refreshing) "Refreshing…" else "Refresh") }
        if (loading) Text("Loading…")
        if (!error.isNullOrBlank()) Text(error!!, color = MaterialTheme.colorScheme.error)
        val reports = outside?.reports.orEmpty()
        if (!loading && reports.isEmpty()) Text("No provider readings yet.")
        reports.forEach { report ->
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(12.dp)) {
                    Text(report.name.ifBlank { "Provider" }, style = MaterialTheme.typography.titleMedium)
                    if (report.ok) {
                        Text(
                            "${formatAmount(report.temperatureC, "°C")} · ${formatAmount(report.humidityPct, "%")} · ${report.condition ?: "—"}",
                        )
                    } else {
                        Text(report.error ?: "unavailable", color = MaterialTheme.colorScheme.error)
                    }
                }
            }
        }
    }
}

@Composable
private fun ClimateSettingsTab(baseUrl: String) {
    val client = remember { HubClient() }
    val scope = rememberCoroutineScope()
    var humidityMin by remember { mutableStateOf("") }
    var humidityMax by remember { mutableStateOf("") }
    var tempMin by remember { mutableStateOf("") }
    var tempMax by remember { mutableStateOf("") }
    var interval by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }
    var status by remember { mutableStateOf<String?>(null) }
    var loading by remember { mutableStateOf(true) }
    var saving by remember { mutableStateOf(false) }

    suspend fun load() {
        loading = true
        error = null
        try {
            val settings = client.climateSettings(baseUrl)
            humidityMin = settings.humidityMin?.let(::formatEditable).orEmpty()
            humidityMax = settings.humidityMax?.let(::formatEditable).orEmpty()
            tempMin = settings.tempMin?.let(::formatEditable).orEmpty()
            tempMax = settings.tempMax?.let(::formatEditable).orEmpty()
            interval = settings.sampleIntervalSeconds?.toString().orEmpty()
        } catch (e: Exception) {
            error = e.message
        } finally {
            loading = false
        }
    }

    LaunchedEffect(baseUrl) { load() }

    fun number(text: String, label: String): Double? {
        val value = parseEditable(text)
        if (value == null) error = "$label must be a number"
        return value
    }

    SectionColumn {
        Text("Bands and sample interval are saved on the Pi.", color = MaterialTheme.colorScheme.onSurfaceVariant)
        if (loading) Text("Loading…")
        if (!error.isNullOrBlank()) Text(error!!, color = MaterialTheme.colorScheme.error)
        if (!status.isNullOrBlank()) Text(status!!)
        NumberField("Humidity min", humidityMin) { humidityMin = it }
        NumberField("Humidity max", humidityMax) { humidityMax = it }
        NumberField("Temp min", tempMin) { tempMin = it }
        NumberField("Temp max", tempMax) { tempMax = it }
        NumberField("Sample interval seconds", interval, KeyboardType.Number) { interval = it }
        Button(
            onClick = {
                scope.launch {
                    error = null
                    status = null
                    val hMin = number(humidityMin, "Humidity min") ?: return@launch
                    val hMax = number(humidityMax, "Humidity max") ?: return@launch
                    val tMin = number(tempMin, "Temp min") ?: return@launch
                    val tMax = number(tempMax, "Temp max") ?: return@launch
                    val seconds = parseEditable(interval)
                    if (seconds == null || seconds < 2 || seconds % 1.0 != 0.0) {
                        error = "Sample interval must be a whole number of seconds, at least 2"
                        return@launch
                    }
                    if (hMin >= hMax) {
                        error = "Humidity min must be less than humidity max"
                        return@launch
                    }
                    if (tMin >= tMax) {
                        error = "Temp min must be less than temp max"
                        return@launch
                    }
                    saving = true
                    try {
                        val saved = client.updateClimateSettings(
                            baseUrl,
                            hMin,
                            hMax,
                            tMin,
                            tMax,
                            seconds.toInt(),
                        )
                        humidityMin = saved.humidityMin?.let(::formatEditable).orEmpty()
                        humidityMax = saved.humidityMax?.let(::formatEditable).orEmpty()
                        tempMin = saved.tempMin?.let(::formatEditable).orEmpty()
                        tempMax = saved.tempMax?.let(::formatEditable).orEmpty()
                        interval = saved.sampleIntervalSeconds?.toString().orEmpty()
                        status = "Saved"
                    } catch (e: Exception) {
                        error = e.message
                    } finally {
                        saving = false
                    }
                }
            },
            enabled = !saving,
        ) { Text(if (saving) "Saving…" else "Save") }
        OutlinedButton(onClick = { scope.launch { load() } }) { Text("Reload") }
    }
}

@Composable
private fun Stat(label: String, value: String) {
    Column {
        Text(label, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, style = MaterialTheme.typography.headlineSmall)
    }
}

@Composable
private fun NumberField(
    label: String,
    value: String,
    keyboard: KeyboardType = KeyboardType.Decimal,
    onValue: (String) -> Unit,
) {
    OutlinedTextField(
        value = value,
        onValueChange = onValue,
        modifier = Modifier.fillMaxWidth(),
        label = { Text(label) },
        singleLine = true,
        keyboardOptions = KeyboardOptions(keyboardType = keyboard),
    )
}
