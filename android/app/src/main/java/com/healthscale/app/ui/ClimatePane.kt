@file:OptIn(
    androidx.compose.material3.ExperimentalMaterial3Api::class,
    androidx.compose.foundation.layout.ExperimentalLayoutApi::class,
)

package com.healthscale.app.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.FilterChip
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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import com.healthscale.app.api.ClimateOutside
import com.healthscale.app.api.ClimatePoint
import com.healthscale.app.api.ClimateReading
import com.healthscale.app.api.ForecastClient
import com.healthscale.app.api.HourlyForecast
import com.healthscale.app.api.HourlyForecastPoint
import com.healthscale.app.api.HubClient
import kotlinx.coroutines.launch
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.time.temporal.ChronoUnit
import kotlin.math.roundToInt

private val historyRanges = listOf(
    12 to "12 hours",
    24 to "24 hours",
    24 * 7 to "7 days",
    24 * 30 to "30 days",
)

@Composable
fun ClimatePane(baseUrl: String) {
    var tab by remember { mutableIntStateOf(0) }
    val tabs = listOf("Now", "History", "Outside", "Forecast", "Settings")
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
                3 -> ClimateForecastTab(baseUrl)
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
    var hours by remember { mutableIntStateOf(24) }
    var error by remember { mutableStateOf<String?>(null) }
    var loading by remember { mutableStateOf(true) }

    suspend fun load() {
        loading = true
        error = null
        try {
            val from = Instant.now().minusSeconds(hours.toLong() * 3600L).toString()
            points = client.climateHistory(baseUrl, from)
        } catch (e: Exception) {
            error = e.message
        } finally {
            loading = false
        }
    }

    LaunchedEffect(baseUrl, hours) { load() }
    val temps = decimate(points.mapNotNull { it.temperatureC }, 400)
    SectionColumn {
        FlowRow(
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            historyRanges.forEach { (value, label) ->
                FilterChip(
                    selected = hours == value,
                    onClick = { hours = value },
                    label = { Text(label) },
                )
            }
        }
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
private fun ClimateForecastTab(baseUrl: String) {
    val client = remember { ForecastClient() }
    val scope = rememberCoroutineScope()
    var forecast by remember { mutableStateOf<HourlyForecast?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var loading by remember { mutableStateOf(true) }

    suspend fun load() {
        loading = true
        error = null
        try {
            forecast = client.hourly(baseUrl)
        } catch (e: Exception) {
            forecast = null
            error = e.message
        } finally {
            loading = false
        }
    }

    LaunchedEffect(baseUrl) { load() }
    val slots = forecast?.let(::forecastSlots)
    SectionColumn {
        OutlinedButton(onClick = { scope.launch { load() } }) { Text("Refresh") }
        if (loading) Text("Loading…")
        if (!error.isNullOrBlank()) Text(error!!, color = MaterialTheme.colorScheme.error)
        val shown = forecast
        if (shown != null && slots == null) {
            Text("Forecast window is missing a start time.", color = MaterialTheme.colorScheme.error)
        }
        if (shown != null && slots != null) {
            Text(forecastCaption(shown), color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (shown.points.isEmpty()) {
                Text("No hourly forecast stored for the next 24 hours.")
            } else {
                ForecastChart(
                    title = "Temperature and humidity",
                    primaryName = "Temperature °C",
                    secondaryName = "Humidity %",
                    primary = seriesOf(slots) { it.temperatureC },
                    secondary = seriesOf(slots) { it.humidityPct },
                    labels = slots.map { it.label },
                    chartLabel = "Temperature and humidity for the next 24 hours",
                )
                ForecastChart(
                    title = "Precipitation and wind",
                    primaryName = "Precipitation %",
                    secondaryName = "Wind km/h",
                    primary = seriesOf(slots) { it.precipitationProbability },
                    secondary = seriesOf(slots) { it.windKph },
                    labels = slots.map { it.label },
                    chartLabel = "Precipitation probability and wind for the next 24 hours",
                )
                Text("Condition", style = MaterialTheme.typography.titleMedium)
                FlowRow(
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalArrangement = Arrangement.spacedBy(4.dp),
                ) {
                    slots.forEach { slot ->
                        val condition = slot.point?.conditionLabel?.takeIf { it.isNotBlank() } ?: "—"
                        Text("${slot.label} $condition", style = MaterialTheme.typography.labelMedium)
                    }
                }
            }
        }
    }
}

@Composable
private fun ForecastChart(
    title: String,
    primaryName: String,
    secondaryName: String,
    primary: List<Double?>,
    secondary: List<Double?>,
    labels: List<String>,
    chartLabel: String,
) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(title, style = MaterialTheme.typography.titleMedium)
            RowLegend(primaryName, secondaryName)
            LineChart(primary, secondary = secondary, label = chartLabel)
            if (labels.isNotEmpty()) {
                FlowRow(
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalArrangement = Arrangement.spacedBy(2.dp),
                ) {
                    labels.forEach { label ->
                        Text(
                            label,
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun RowLegend(primaryName: String, secondaryName: String) {
    FlowRow(
        horizontalArrangement = Arrangement.spacedBy(12.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        Text(primaryName, color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.labelMedium)
        Text(secondaryName, color = ForecastLine, style = MaterialTheme.typography.labelMedium)
    }
}

private val ForecastLine = Color(0xFF7AA2D6)

private data class ForecastSlot(val label: String, val point: HourlyForecastPoint?)

private fun forecastSlots(forecast: HourlyForecast): List<ForecastSlot>? {
    val start = runCatching { Instant.parse(forecast.from) }.getOrNull() ?: return null
    val zone = runCatching { ZoneId.of(forecast.timezone) }.getOrElse { ZoneId.of("Europe/Berlin") }
    val hours = forecast.windowHours.coerceAtLeast(1)
    val formatter = DateTimeFormatter.ofPattern("HH:mm").withZone(zone)
    val slots = MutableList(hours) { index ->
        ForecastSlot(formatter.format(start.plus(index.toLong(), ChronoUnit.HOURS)), null)
    }
    for (point in forecast.points) {
        val at = runCatching { Instant.parse(point.ts) }.getOrNull() ?: continue
        val index = ChronoUnit.HOURS.between(start, at).toInt()
        if (index in slots.indices) slots[index] = slots[index].copy(point = point)
    }
    return slots
}

private fun seriesOf(
    slots: List<ForecastSlot>,
    pick: (HourlyForecastPoint) -> Double?,
): List<Double?> = slots.map { slot -> slot.point?.let(pick) }

private fun forecastCaption(forecast: HourlyForecast): String {
    val zoneName = forecast.timezone.ifBlank { "Europe/Berlin" }
    val zone = runCatching { ZoneId.of(zoneName) }.getOrElse { ZoneId.of("Europe/Berlin") }
    val points = forecast.points
    if (points.isEmpty()) return "No stored hours in the next 24 hours ($zoneName)."
    val counts = points.map { it.providerCount }
    val low = counts.min()
    val high = counts.max()
    val providers = if (low == high) {
        if (low == 1) "1 provider" else "$low providers"
    } else {
        "$low–$high providers"
    }
    val fetched = points.mapNotNull { it.fetchedAt }.maxOrNull()
    val whenText = if (fetched == null) {
        "unknown time"
    } else {
        runCatching {
            DateTimeFormatter.ofPattern("d MMM, HH:mm").withZone(zone).format(Instant.parse(fetched))
        }.getOrDefault(fetched)
    }
    return "$providers · fetched $whenText · $zoneName"
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

private fun decimate(values: List<Double>, maxPoints: Int): List<Double> {
    if (values.size <= maxPoints) return values
    val step = (values.size - 1).toDouble() / (maxPoints - 1)
    return List(maxPoints) { index -> values[(index * step).roundToInt()] }
}
