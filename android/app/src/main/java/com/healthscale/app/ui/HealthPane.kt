@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.healthscale.app.ui

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.ScrollableTabRow
import androidx.compose.material3.Slider
import androidx.compose.material3.Tab
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
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
import com.healthscale.app.api.BodyMeasurement
import com.healthscale.app.api.HealthProfile
import com.healthscale.app.api.HealthSnapshot
import com.healthscale.app.api.HubClient
import com.healthscale.app.api.ScaleListener
import kotlinx.coroutines.launch
import kotlin.math.roundToInt

private val activityLevels = listOf(
    "sedentary" to "Sedentary",
    "light" to "Light",
    "moderate" to "Moderate",
    "active" to "Active",
    "very_active" to "Very active",
)

@Composable
fun HealthPane(baseUrl: String) {
    var tab by remember { mutableIntStateOf(0) }
    val tabs = listOf("Dashboard", "Charts", "Measurements", "Calories", "Profile")
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
                0 -> HealthDashboard(baseUrl)
                1 -> HealthCharts(baseUrl)
                2 -> HealthMeasurements(baseUrl)
                3 -> CaloriesPane(baseUrl)
                else -> HealthProfilePane(baseUrl)
            }
        }
    }
}

@Composable
private fun HealthDashboard(baseUrl: String) {
    val client = remember { HubClient() }
    val scope = rememberCoroutineScope()
    var snap by remember { mutableStateOf<HealthSnapshot?>(null) }
    var listener by remember { mutableStateOf<ScaleListener?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var loading by remember { mutableStateOf(true) }
    var busy by remember { mutableStateOf(false) }

    suspend fun load() {
        loading = true
        val problems = mutableListOf<String>()
        snap = runCatching { client.health(baseUrl) }.getOrElse {
            problems += it.message ?: "Could not load health"
            null
        }
        listener = runCatching { client.scaleListener(baseUrl) }.getOrElse {
            problems += it.message ?: "Could not load the scale"
            listener
        }
        error = problems.joinToString("\n").ifBlank { null }
        loading = false
    }

    LaunchedEffect(baseUrl) { load() }

    fun setMode(action: String) {
        scope.launch {
            busy = true
            error = null
            try {
                listener = client.setScaleMode(baseUrl, action)
                snap = runCatching { client.health(baseUrl) }.getOrElse { error = it.message; snap }
            } catch (e: Exception) {
                error = e.message
            } finally {
                busy = false
            }
        }
    }

    val mode = listener?.mode ?: "auto"
    SectionColumn {
        Text(
            "The Pi records the scale from 06:00 to 12:00, then stops for the day.",
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.horizontalScroll(rememberScrollState())) {
            OutlinedButton(onClick = { scope.launch { load() } }) { Text("Refresh") }
            Button(onClick = { setMode("start") }, enabled = !busy && mode != "on") { Text("Start scan") }
            Button(onClick = { setMode("stop") }, enabled = !busy && mode != "off") { Text("Stop scan") }
            Button(onClick = { setMode("auto") }, enabled = !busy && mode != "auto") { Text("Use schedule") }
        }
        if (loading) Text("Loading…")
        if (!error.isNullOrBlank()) Text(error!!, color = MaterialTheme.colorScheme.error)
        Text("Scale listener: ${listener?.line ?: "—"}")
        snap?.let { item ->
            Stat("Latest", item.latestKg?.let { "%.1f kg".format(it) } ?: "—")
            Text("7-day average: ${item.avg7?.let { "%.1f kg".format(it) } ?: "—"}")
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
private fun HealthCharts(baseUrl: String) {
    val client = remember { HubClient() }
    val scope = rememberCoroutineScope()
    var rows by remember { mutableStateOf<List<BodyMeasurement>>(emptyList()) }
    var error by remember { mutableStateOf<String?>(null) }
    var loading by remember { mutableStateOf(true) }

    suspend fun load() {
        loading = true
        error = null
        try {
            rows = client.bodyMeasurements(baseUrl, 500)
        } catch (e: Exception) {
            error = e.message
        } finally {
            loading = false
        }
    }

    LaunchedEffect(baseUrl) { load() }
    val weights = rows
        .sortedBy { epochMillis(it.measuredAt) }
        .map { it.weightKg }
    SectionColumn {
        OutlinedButton(onClick = { scope.launch { load() } }) { Text("Refresh") }
        if (loading) Text("Loading…")
        if (!error.isNullOrBlank()) Text(error!!, color = MaterialTheme.colorScheme.error)
        if (!loading && weights.isEmpty()) Text("No measurements yet.")
        if (weights.isNotEmpty()) {
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(12.dp)) {
                    Text("Weight", style = MaterialTheme.typography.titleMedium)
                    LineChart(weights, label = "Weight history")
                    Text(
                        "${formatAmount(weights.min(), " kg")} to ${formatAmount(weights.max(), " kg")} · ${weights.size} points",
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }
    }
}

@Composable
private fun HealthMeasurements(baseUrl: String) {
    val client = remember { HubClient() }
    val scope = rememberCoroutineScope()
    var rows by remember { mutableStateOf<List<BodyMeasurement>>(emptyList()) }
    var error by remember { mutableStateOf<String?>(null) }
    var loading by remember { mutableStateOf(true) }
    var pendingDelete by remember { mutableStateOf<BodyMeasurement?>(null) }

    suspend fun load() {
        loading = true
        error = null
        try {
            rows = client.bodyMeasurements(baseUrl, 500)
        } catch (e: Exception) {
            error = e.message
        } finally {
            loading = false
        }
    }

    LaunchedEffect(baseUrl) { load() }
    val sorted = rows.sortedByDescending { epochMillis(it.measuredAt) }
    SectionColumn {
        OutlinedButton(onClick = { scope.launch { load() } }) { Text("Refresh") }
        if (loading) Text("Loading…")
        if (!error.isNullOrBlank()) Text(error!!, color = MaterialTheme.colorScheme.error)
        if (!loading && sorted.isEmpty()) Text("No measurements yet.")
        sorted.forEach { row ->
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text(formatWhen(row.measuredAt), style = MaterialTheme.typography.titleMedium)
                    Text("Weight ${formatAmount(row.weightKg, " kg")}")
                    Text("Body fat ${formatAmount(row.bodyFatPct, "%")}")
                    Text("Muscle ${formatAmount(row.muscleMassKg, " kg")}")
                    if (row.id != 0L) {
                        TextButton(onClick = { pendingDelete = row }) { Text("Delete") }
                    }
                }
            }
        }
    }
    pendingDelete?.let { row ->
        AlertDialog(
            onDismissRequest = { pendingDelete = null },
            title = { Text("Delete measurement?") },
            text = { Text("${formatWhen(row.measuredAt)} · ${formatAmount(row.weightKg, " kg")}") },
            confirmButton = {
                TextButton(onClick = {
                    pendingDelete = null
                    scope.launch {
                        try {
                            client.deleteBodyMeasurement(baseUrl, row.id)
                            load()
                        } catch (e: Exception) {
                            error = e.message
                        }
                    }
                }) { Text("Delete") }
            },
            dismissButton = {
                TextButton(onClick = { pendingDelete = null }) { Text("Cancel") }
            },
        )
    }
}

@Composable
private fun HealthProfilePane(baseUrl: String) {
    val client = remember { HubClient() }
    val scope = rememberCoroutineScope()
    var profile by remember { mutableStateOf<HealthProfile?>(null) }
    var name by remember { mutableStateOf("") }
    var height by remember { mutableStateOf("") }
    var age by remember { mutableStateOf("") }
    var sex by remember { mutableStateOf<String?>(null) }
    var activity by remember { mutableStateOf("moderate") }
    var targetFat by remember { mutableStateOf("") }
    var meals by remember { mutableIntStateOf(3) }
    var error by remember { mutableStateOf<String?>(null) }
    var status by remember { mutableStateOf<String?>(null) }
    var loading by remember { mutableStateOf(true) }
    var saving by remember { mutableStateOf(false) }

    fun fill(next: HealthProfile) {
        profile = next
        name = next.name
        height = next.heightCm?.let(::formatEditable).orEmpty()
        age = next.age?.toString().orEmpty()
        sex = next.sex
        activity = activityLevels.firstOrNull { it.first == next.activityLevel }?.first ?: "moderate"
        targetFat = next.targetFatPct?.let(::formatEditable).orEmpty()
        meals = next.mealsPerDay.coerceIn(1, 8)
    }

    suspend fun load() {
        loading = true
        error = null
        try {
            fill(client.healthProfile(baseUrl))
        } catch (e: Exception) {
            error = e.message
        } finally {
            loading = false
        }
    }

    LaunchedEffect(baseUrl) { load() }

    SectionColumn {
        Text("Profile", style = MaterialTheme.typography.titleMedium)
        if (loading) Text("Loading…")
        if (!error.isNullOrBlank()) Text(error!!, color = MaterialTheme.colorScheme.error)
        if (!status.isNullOrBlank()) Text(status!!)
        profile?.let { item ->
            if (item.targetCalories != null || item.proteinG != null || item.fiberG != null) {
                if (item.targetCalories != null) Text("Target calories ${formatAmount(item.targetCalories, " kcal")}")
                if (item.proteinG != null) Text("Protein ${formatAmount(item.proteinG, " g")}")
                if (item.fiberG != null) Text("Fiber ${formatAmount(item.fiberG, " g")}")
            }
        }
        OutlinedTextField(
            value = name,
            onValueChange = { name = it },
            modifier = Modifier.fillMaxWidth(),
            label = { Text("Name") },
            singleLine = true,
        )
        OutlinedTextField(
            value = height,
            onValueChange = { height = it },
            modifier = Modifier.fillMaxWidth(),
            label = { Text("Height cm") },
            singleLine = true,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
        )
        OutlinedTextField(
            value = age,
            onValueChange = { age = it },
            modifier = Modifier.fillMaxWidth(),
            label = { Text("Age") },
            singleLine = true,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
        )
        Text("Sex", color = MaterialTheme.colorScheme.onSurfaceVariant)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            FilterChip(selected = sex == null, onClick = { sex = null }, label = { Text("Not set") })
            FilterChip(selected = sex == "male", onClick = { sex = "male" }, label = { Text("Male") })
            FilterChip(selected = sex == "female", onClick = { sex = "female" }, label = { Text("Female") })
        }
        Text("Activity", color = MaterialTheme.colorScheme.onSurfaceVariant)
        Row(
            Modifier.horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            activityLevels.forEach { (id, label) ->
                FilterChip(selected = activity == id, onClick = { activity = id }, label = { Text(label) })
            }
        }
        OutlinedTextField(
            value = targetFat,
            onValueChange = { targetFat = it },
            modifier = Modifier.fillMaxWidth(),
            label = { Text("Target fat %") },
            singleLine = true,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
        )
        Text("Meals per day: $meals")
        Slider(
            value = meals.toFloat(),
            onValueChange = { meals = it.roundToInt().coerceIn(1, 8) },
            valueRange = 1f..8f,
            steps = 6,
        )
        Button(
            onClick = {
                val heightValue = if (height.isBlank()) null else parseEditable(height)
                if (height.isNotBlank() && heightValue == null) {
                    error = "Height must be a number"
                    return@Button
                }
                val ageValue = if (age.isBlank()) {
                    null
                } else {
                    val parsed = parseEditable(age)
                    if (parsed == null || parsed % 1.0 != 0.0) {
                        error = "Age must be a whole number"
                        return@Button
                    }
                    parsed.toInt()
                }
                val fatValue = if (targetFat.isBlank()) null else parseEditable(targetFat)
                if (targetFat.isNotBlank() && fatValue == null) {
                    error = "Target fat must be a number"
                    return@Button
                }
                scope.launch {
                    saving = true
                    error = null
                    status = null
                    try {
                        val saved = client.saveHealthProfile(
                            baseUrl,
                            HealthProfile(
                                name = name.trim(),
                                heightCm = heightValue,
                                age = ageValue,
                                sex = sex,
                                activityLevel = activity,
                                targetFatPct = fatValue,
                                mealsPerDay = meals.coerceIn(1, 8),
                                targetCalories = null,
                                proteinG = null,
                                fiberG = null,
                            ),
                        )
                        fill(saved)
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
    }
}

@Composable
private fun Stat(label: String, value: String) {
    Column {
        Text(label, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, style = MaterialTheme.typography.headlineSmall)
    }
}
