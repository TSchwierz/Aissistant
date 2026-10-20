@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.healthscale.app.ui

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.DatePicker
import androidx.compose.material3.DatePickerDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberDatePickerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.runtime.snapshots.SnapshotStateList
import androidx.compose.runtime.toMutableStateList
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.core.content.ContextCompat
import com.healthscale.app.api.FoodHit
import com.healthscale.app.api.HubClient
import com.healthscale.app.api.MealDay
import com.healthscale.app.api.MealEntry
import com.healthscale.app.api.MealItem
import kotlinx.coroutines.launch
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneOffset

private data class DraftFood(
    val key: Long,
    val name: String,
    val baseGrams: Double,
    val baseKcal: Double,
    val baseProtein: Double,
    val baseCarbs: Double,
    val baseFat: Double,
    val baseFiber: Double,
    val gramsText: String,
    val source: String,
    val sourceId: String?,
)

@Composable
fun CaloriesPane(baseUrl: String) {
    val context = LocalContext.current
    val client = remember { HubClient() }
    val scope = rememberCoroutineScope()
    var day by remember { mutableStateOf(LocalDate.now()) }
    var showPicker by remember { mutableStateOf(false) }
    var summary by remember { mutableStateOf<MealDay?>(null) }
    var loading by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf<String?>(null) }
    var note by remember { mutableStateOf("") }
    val drafts = remember { mutableListOf<DraftFood>().toMutableStateList() }
    var nextKey by remember { mutableLongStateOf(1L) }
    var mealSource by remember { mutableStateOf("text") }
    var proposed by remember { mutableStateOf(false) }
    var query by remember { mutableStateOf("") }
    var hits by remember { mutableStateOf<List<FoodHit>>(emptyList()) }
    var searched by remember { mutableStateOf(false) }
    var busy by remember { mutableStateOf<String?>(null) }
    var pendingDelete by remember { mutableStateOf<MealEntry?>(null) }
    var cameraMode by remember { mutableStateOf<MealCameraMode?>(null) }
    var pendingCamera by remember { mutableStateOf<MealCameraMode?>(null) }

    val cameraPermission = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { granted ->
        val pending = pendingCamera
        pendingCamera = null
        if (granted && pending != null) cameraMode = pending
        else if (!granted) error = "Camera permission is required"
    }

    fun append(items: List<MealItem>) {
        items.forEach { item ->
            val key = nextKey
            nextKey += 1
            drafts.add(
                DraftFood(
                    key = key,
                    name = item.name,
                    baseGrams = item.grams,
                    baseKcal = item.kcal,
                    baseProtein = item.proteinG,
                    baseCarbs = item.carbsG,
                    baseFat = item.fatG,
                    baseFiber = item.fiberG,
                    gramsText = if (item.grams > 0.0) formatEditable(item.grams) else "",
                    source = item.source,
                    sourceId = item.sourceId,
                ),
            )
        }
    }

    suspend fun load() {
        loading = true
        try {
            summary = client.mealSummary(baseUrl, day.toString())
        } catch (e: Exception) {
            error = e.message ?: "Could not load meals"
        } finally {
            loading = false
        }
    }

    LaunchedEffect(baseUrl, day) {
        error = null
        load()
    }

    fun openCamera(mode: MealCameraMode) {
        if (busy != null) return
        val granted = ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) ==
            PackageManager.PERMISSION_GRANTED
        if (granted) cameraMode = mode
        else {
            pendingCamera = mode
            cameraPermission.launch(Manifest.permission.CAMERA)
        }
    }

    SectionColumn {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            OutlinedButton(onClick = { day = day.minusDays(1) }) { Text("Prev") }
            TextButton(onClick = { showPicker = true }, modifier = Modifier.weight(1f)) {
                Text(day.toString(), textAlign = TextAlign.Center, modifier = Modifier.fillMaxWidth())
            }
            OutlinedButton(onClick = { day = day.plusDays(1) }) { Text("Next") }
        }
        TextButton(onClick = { day = LocalDate.now() }) { Text("Today") }
        if (loading) Text("Loading…")
        if (busy != null) Text(busy!!)
        if (!error.isNullOrBlank()) Text(error!!, color = MaterialTheme.colorScheme.error)
        summary?.let { daySummary ->
            val targets = daySummary.targets
            MacroStat("Calories", daySummary.totals.kcal, targets?.targetCalories, "kcal")
            MacroStat("Protein", daySummary.totals.proteinG, targets?.proteinG, "g")
            MacroStat("Fiber", daySummary.totals.fiberG, targets?.fiberG, "g")
            MacroStat("Carbs", daySummary.totals.carbsG, null, "g")
            MacroStat("Fat", daySummary.totals.fatG, null, "g")
            Text("Meals", style = MaterialTheme.typography.titleMedium)
            if (daySummary.meals.isEmpty()) Text("No meals logged for this day.")
            daySummary.meals.forEach { meal ->
                MealCard(meal) { pendingDelete = meal }
            }
        }
        Text("Log a meal", style = MaterialTheme.typography.titleMedium)
        OutlinedTextField(
            value = note,
            onValueChange = { note = it },
            modifier = Modifier.fillMaxWidth(),
            label = { Text("Describe the meal") },
            minLines = 3,
        )
        Button(
            onClick = {
                if (note.isBlank()) {
                    error = "Describe a meal first."
                    return@Button
                }
                scope.launch {
                    busy = "Proposing foods…"
                    error = null
                    try {
                        val items = client.parseFoods(baseUrl, note.trim())
                        drafts.clear()
                        mealSource = "text"
                        append(items)
                        proposed = true
                    } catch (e: Exception) {
                        error = e.message
                    } finally {
                        busy = null
                    }
                }
            },
            enabled = busy == null,
        ) { Text("Propose foods") }
        if (proposed && drafts.isEmpty() && busy == null) Text("No foods proposed.")
        drafts.forEach { row ->
            DraftCard(
                row = row,
                onName = { name -> replaceDraft(drafts, row.key) { it.copy(name = name) } },
                onGrams = { grams -> replaceDraft(drafts, row.key) { it.copy(gramsText = grams) } },
                onRemove = { drafts.removeAll { it.key == row.key } },
            )
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(
                value = query,
                onValueChange = { query = it },
                modifier = Modifier.weight(1f),
                label = { Text("Search foods") },
                singleLine = true,
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                keyboardActions = KeyboardActions(onSearch = {
                    scope.launch { searchFoods(client, baseUrl, query, { hits = it }, { searched = it }, { error = it }, { busy = it }) }
                }),
            )
        }
        Button(
            onClick = {
                scope.launch {
                    searchFoods(client, baseUrl, query, { hits = it }, { searched = it }, { error = it }, { busy = it })
                }
            },
            enabled = busy == null,
        ) { Text("Search") }
        if (searched && hits.isEmpty() && busy == null) Text("No matching foods.")
        hits.forEach { hit ->
            OutlinedButton(
                onClick = {
                    append(listOf(hit.toMealItem()))
                    proposed = true
                },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("${hit.name} · ${formatAmount(hit.kcal100g)} kcal/100 g · add 100 g")
            }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(onClick = { openCamera(MealCameraMode.Barcode) }, enabled = busy == null) {
                Text("Scan barcode")
            }
            OutlinedButton(onClick = { openCamera(MealCameraMode.Photo) }, enabled = busy == null) {
                Text("Take photo")
            }
        }
        Button(
            onClick = {
                if (drafts.isEmpty()) {
                    error = "Add at least one food."
                    return@Button
                }
                val items = mutableListOf<MealItem>()
                for (row in drafts) {
                    val item = row.toMealItem()
                    if (item == null) {
                        error = "Each food needs a name and grams greater than 0."
                        return@Button
                    }
                    items += item
                }
                scope.launch {
                    busy = "Saving…"
                    error = null
                    try {
                        client.saveMeal(
                            baseUrl,
                            eatenAt = "${day}T12:00:00",
                            note = note.trim(),
                            source = mealSource,
                            items = items,
                        )
                        drafts.clear()
                        note = ""
                        proposed = false
                        mealSource = "text"
                        load()
                    } catch (e: Exception) {
                        error = e.message
                    } finally {
                        busy = null
                    }
                }
            },
            enabled = busy == null && drafts.isNotEmpty(),
        ) { Text("Save meal") }
    }

    if (showPicker) {
        val state = rememberDatePickerState(
            initialSelectedDateMillis = day.atStartOfDay(ZoneOffset.UTC).toInstant().toEpochMilli(),
        )
        DatePickerDialog(
            onDismissRequest = { showPicker = false },
            confirmButton = {
                TextButton(onClick = {
                    state.selectedDateMillis?.let { millis ->
                        day = Instant.ofEpochMilli(millis).atZone(ZoneOffset.UTC).toLocalDate()
                    }
                    showPicker = false
                }) { Text("OK") }
            },
            dismissButton = {
                TextButton(onClick = { showPicker = false }) { Text("Cancel") }
            },
        ) {
            DatePicker(state = state)
        }
    }

    pendingDelete?.let { meal ->
        AlertDialog(
            onDismissRequest = { pendingDelete = null },
            title = { Text("Delete meal?") },
            text = { Text(meal.note.ifBlank { formatWhen(meal.eatenAt) }) },
            confirmButton = {
                TextButton(onClick = {
                    pendingDelete = null
                    scope.launch {
                        busy = "Deleting…"
                        error = null
                        try {
                            client.deleteMeal(baseUrl, meal.id)
                            load()
                        } catch (e: Exception) {
                            error = e.message
                        } finally {
                            busy = null
                        }
                    }
                }) { Text("Delete") }
            },
            dismissButton = {
                TextButton(onClick = { pendingDelete = null }) { Text("Cancel") }
            },
        )
    }

    cameraMode?.let { mode ->
        Dialog(
            onDismissRequest = { cameraMode = null },
            properties = DialogProperties(usePlatformDefaultWidth = false),
        ) {
            MealCamera(
                mode = mode,
                onBarcode = { code ->
                    cameraMode = null
                    scope.launch {
                        busy = "Looking up barcode…"
                        error = null
                        try {
                            val food = client.foodByBarcode(baseUrl, code)
                            append(listOf(food.toMealItem()))
                            mealSource = "barcode"
                            proposed = true
                        } catch (e: Exception) {
                            error = e.message ?: "Barcode lookup failed"
                        } finally {
                            busy = null
                        }
                    }
                },
                onPhoto = { bytes ->
                    cameraMode = null
                    scope.launch {
                        busy = "Reading the photo…"
                        error = null
                        try {
                            val items = try {
                                client.parseFoodImage(baseUrl, bytes)
                            } finally {
                                bytes.fill(0)
                            }
                            append(items)
                            mealSource = "photo"
                            proposed = true
                            if (items.isEmpty()) error = "No foods found in the photo."
                        } catch (e: Exception) {
                            error = e.message ?: "Could not read the photo"
                        } finally {
                            busy = null
                        }
                    }
                },
                onError = { message ->
                    cameraMode = null
                    error = message
                },
                onClose = { cameraMode = null },
            )
        }
    }
}

@Composable
private fun MacroStat(label: String, value: Double, target: Double?, unit: String) {
    Column {
        Text(label, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(
            if (target != null) {
                "${formatAmount(value)} / ${formatAmount(target)} $unit"
            } else {
                "${formatAmount(value)} $unit"
            },
            style = MaterialTheme.typography.titleMedium,
        )
    }
}

@Composable
private fun MealCard(meal: MealEntry, onDelete: () -> Unit) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(
                buildString {
                    append(formatWhen(meal.eatenAt))
                    if (meal.note.isNotBlank()) append(" · ").append(meal.note)
                },
                style = MaterialTheme.typography.titleMedium,
            )
            if (meal.source.isNotBlank()) {
                Text(meal.source, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            if (meal.items.isEmpty()) {
                Text("No items.")
            } else {
                meal.items.forEach { item ->
                    Text(
                        "${item.name} · ${formatAmount(item.grams)} g · ${formatAmount(item.kcal)} kcal · " +
                            "${formatAmount(item.proteinG)} g protein · ${formatAmount(item.carbsG)} g carbs · " +
                            "${formatAmount(item.fatG)} g fat · ${formatAmount(item.fiberG)} g fiber",
                    )
                }
            }
            TextButton(onClick = onDelete, enabled = meal.id != 0L) { Text("Delete meal") }
        }
    }
}

@Composable
private fun DraftCard(
    row: DraftFood,
    onName: (String) -> Unit,
    onGrams: (String) -> Unit,
    onRemove: () -> Unit,
) {
    val preview = row.preview()
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(
                value = row.name,
                onValueChange = onName,
                modifier = Modifier.fillMaxWidth(),
                label = { Text("Name") },
                singleLine = true,
            )
            OutlinedTextField(
                value = row.gramsText,
                onValueChange = onGrams,
                modifier = Modifier.fillMaxWidth(),
                label = { Text("Grams") },
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
            )
            Text(
                "${formatAmount(preview.kcal)} kcal · ${formatAmount(preview.proteinG)} g protein · " +
                    "${formatAmount(preview.carbsG)} g carbs · ${formatAmount(preview.fatG)} g fat · " +
                    "${formatAmount(preview.fiberG)} g fiber",
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            TextButton(onClick = onRemove) { Text("Remove") }
        }
    }
}

private fun replaceDraft(
    drafts: SnapshotStateList<DraftFood>,
    key: Long,
    update: (DraftFood) -> DraftFood,
) {
    val index = drafts.indexOfFirst { it.key == key }
    if (index >= 0) drafts[index] = update(drafts[index])
}

private fun DraftFood.preview(): MealItem {
    val grams = parseEditable(gramsText)
    val ratio = if (grams != null && grams > 0.0 && baseGrams > 0.0) grams / baseGrams else 1.0
    return MealItem(
        name = name,
        grams = grams ?: baseGrams,
        kcal = baseKcal * ratio,
        proteinG = baseProtein * ratio,
        carbsG = baseCarbs * ratio,
        fatG = baseFat * ratio,
        fiberG = baseFiber * ratio,
        source = source,
        sourceId = sourceId,
    )
}

private fun DraftFood.toMealItem(): MealItem? {
    val trimmed = name.trim()
    if (trimmed.isEmpty()) return null
    val grams = parseEditable(gramsText)
    if (grams == null || grams <= 0.0) return null
    val ratio = if (baseGrams > 0.0) grams / baseGrams else 1.0
    return MealItem(
        name = trimmed,
        grams = round2(grams),
        kcal = round2((baseKcal * ratio).coerceAtLeast(0.0)),
        proteinG = round2((baseProtein * ratio).coerceAtLeast(0.0)),
        carbsG = round2((baseCarbs * ratio).coerceAtLeast(0.0)),
        fatG = round2((baseFat * ratio).coerceAtLeast(0.0)),
        fiberG = round2((baseFiber * ratio).coerceAtLeast(0.0)),
        source = source,
        sourceId = sourceId,
    )
}

private fun FoodHit.toMealItem() = MealItem(
    name = name,
    grams = 100.0,
    kcal = kcal100g,
    proteinG = protein100g,
    carbsG = carbs100g,
    fatG = fat100g,
    fiberG = fiber100g,
    source = source,
    sourceId = sourceId,
)

private suspend fun searchFoods(
    client: HubClient,
    baseUrl: String,
    query: String,
    onHits: (List<FoodHit>) -> Unit,
    onSearched: (Boolean) -> Unit,
    onError: (String?) -> Unit,
    onBusy: (String?) -> Unit,
) {
    val q = query.trim()
    if (q.isEmpty()) {
        onHits(emptyList())
        onSearched(false)
        return
    }
    onBusy("Searching…")
    onError(null)
    try {
        onHits(client.searchFoods(baseUrl, q))
        onSearched(true)
    } catch (e: Exception) {
        onError(e.message)
    } finally {
        onBusy(null)
    }
}
