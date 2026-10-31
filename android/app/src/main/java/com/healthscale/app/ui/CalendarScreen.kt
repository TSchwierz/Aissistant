@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.healthscale.app.ui

import android.Manifest
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.provider.OpenableColumns
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import com.healthscale.app.api.CalDraft
import com.healthscale.app.api.CalEvent
import com.healthscale.app.api.CalImport
import com.healthscale.app.api.CalList
import com.healthscale.app.api.HubClient
import com.healthscale.app.api.parseCalendarList
import com.healthscale.app.calendar.CalendarReminderScheduler
import com.healthscale.app.data.AppDatabase
import com.healthscale.app.data.CalendarCache
import org.json.JSONObject
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter

private enum class CalMode { Weeks, Month }

private data class EventDraft(
    val id: String?,
    val title: String,
    val allDay: Boolean,
    val startDate: String,
    val startTime: String,
    val endDate: String,
    val endTime: String,
    val location: String,
    val notes: String,
    val tags: String,
    val remindAmount: String,
    val remindUnit: String,
)

@Composable
fun CalendarPane(baseUrl: String) {
    val context = LocalContext.current
    val client = remember { HubClient() }
    val database = remember { AppDatabase.get(context) }
    var mode by remember { mutableStateOf(CalMode.Weeks) }
    var cursor by remember { mutableStateOf(LocalDate.now()) }
    var tag by remember { mutableStateOf("") }
    var tags by remember { mutableStateOf<List<String>>(emptyList()) }
    var list by remember { mutableStateOf<CalList?>(null) }
    var cached by remember { mutableStateOf<CalList?>(null) }
    var offline by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var loading by remember { mutableStateOf(true) }
    var draft by remember { mutableStateOf<EventDraft?>(null) }
    var formError by remember { mutableStateOf<String?>(null) }
    var saving by remember { mutableStateOf(false) }
    var confirmDelete by remember { mutableStateOf(false) }
    var importing by remember { mutableStateOf(false) }
    var importNote by remember { mutableStateOf<String?>(null) }
    var notifyDenied by remember { mutableStateOf(false) }
    var askedNotify by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    val notificationPermission = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { granted -> notifyDenied = !granted }

    fun askNotify(events: List<CalEvent>, fromUser: Boolean) {
        if (events.none { (it.remindBeforeMinutes ?: 0) > 0 } && !fromUser) return
        if (Build.VERSION.SDK_INT < 33) return
        val granted = ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.POST_NOTIFICATIONS,
        ) == PackageManager.PERMISSION_GRANTED
        if (granted) {
            notifyDenied = false
            return
        }
        if (!fromUser && askedNotify) return
        askedNotify = true
        notificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
    }

    suspend fun load() {
        loading = true
        error = null
        try {
            val selected = tag.ifBlank { null }
            runCatching { tags = client.calendarTags(baseUrl) }
            list = if (mode == CalMode.Month) {
                client.calendarMonth(baseUrl, cursor.format(DateTimeFormatter.ofPattern("yyyy-MM")), selected)
            } else {
                client.calendarWeeks(baseUrl, cursor.toString(), selected)
            }
            offline = false
            try {
                val payload = client.calendarWindow(baseUrl)
                cached = payload.list
                database.calendarCacheDao().upsert(
                    CalendarCache(
                        payloadJson = payload.rawJson,
                        savedAtEpochMs = System.currentTimeMillis(),
                    ),
                )
                CalendarReminderScheduler.reschedule(context, payload.list)
                askNotify(payload.list.events, fromUser = false)
            } catch (_: Exception) {
                /* the view is live; keep the previously saved window */
            }
        } catch (e: Exception) {
            offline = true
            error = e.message ?: "Could not reach the server"
            val stored = cached ?: database.calendarCacheDao().get()?.let { row ->
                runCatching { parseCalendarList(JSONObject(row.payloadJson)) }.getOrNull()
            }
            cached = stored
            list = stored?.let { filterOffline(it, mode, cursor, tag) }
        } finally {
            loading = false
        }
    }

    val importPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri == null) return@rememberLauncherForActivityResult
        scope.launch {
            importing = true
            importNote = null
            try {
                val result = withContext(Dispatchers.IO) {
                    val name = displayName(context, uri)
                    val bytes = context.contentResolver.openInputStream(uri)?.use { it.readBytes() }
                        ?: kotlin.error("Could not read the file")
                    client.importCalendar(baseUrl, name, bytes)
                }
                importNote = importSummary(result)
                load()
            } catch (e: Exception) {
                importNote = e.message ?: "Import failed"
            } finally {
                importing = false
            }
        }
    }

    LaunchedEffect(baseUrl, mode, cursor, tag) { load() }

    if (confirmDelete && draft?.id != null) {
        AlertDialog(
            onDismissRequest = { confirmDelete = false },
            title = { Text("Delete event") },
            text = { Text("Delete “${draft?.title}”?") },
            confirmButton = {
                TextButton(onClick = {
                    val id = draft?.id
                    confirmDelete = false
                    if (id != null) scope.launch {
                        saving = true
                        formError = null
                        try {
                            client.deleteEvent(baseUrl, id)
                            draft = null
                            load()
                        } catch (e: Exception) {
                            formError = e.message
                        } finally {
                            saving = false
                        }
                    }
                }) { Text("Delete") }
            },
            dismissButton = {
                TextButton(onClick = { confirmDelete = false }) { Text("Cancel") }
            },
        )
    }

    Column(
        Modifier
            .fillMaxWidth()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Text("Calendar", style = MaterialTheme.typography.headlineSmall)
        Text(
            "Same views as the PC: month, two weeks, tags, and event editing.",
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = {
                draft = blankDraft()
                formError = null
            }) { Text("New event") }
            OutlinedButton(
                onClick = {
                    importPicker.launch(
                        arrayOf(
                            "text/calendar",
                            "application/zip",
                            "text/csv",
                            "text/comma-separated-values",
                            "application/octet-stream",
                            "*/*",
                        ),
                    )
                },
                enabled = !importing,
            ) { Text(if (importing) "Importing…" else "Import") }
            OutlinedButton(onClick = { mode = CalMode.Weeks }) { Text("2 weeks") }
            OutlinedButton(onClick = { mode = CalMode.Month }) { Text("Month") }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(onClick = {
                cursor = if (mode == CalMode.Month) cursor.minusMonths(1) else cursor.minusDays(14)
            }) { Text("←") }
            OutlinedButton(onClick = { cursor = LocalDate.now() }) { Text("Today") }
            OutlinedButton(onClick = {
                cursor = if (mode == CalMode.Month) cursor.plusMonths(1) else cursor.plusDays(14)
            }) { Text("→") }
        }
        draft?.let { current ->
            EventEditor(
                draft = current,
                saving = saving,
                error = formError,
                onChange = { draft = it },
                onCancel = { draft = null },
                onDelete = { confirmDelete = true },
                onAskNotify = { askNotify(emptyList(), fromUser = true) },
                onSave = { updated ->
                    scope.launch {
                        saving = true
                        formError = null
                        try {
                            client.saveEvent(baseUrl, updated.id, updated.toApi())
                            draft = null
                            load()
                        } catch (e: Exception) {
                            formError = e.message
                            draft = updated
                        } finally {
                            saving = false
                        }
                    }
                },
            )
        }
        Row(
            Modifier.horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            FilterChip(selected = tag.isEmpty(), onClick = { tag = "" }, label = { Text("All tags") })
            tags.forEach { item ->
                FilterChip(selected = tag == item, onClick = { tag = item }, label = { Text(item) })
            }
        }
        if (notifyDenied) {
            Text(
                "Notifications are blocked. Events still save.",
                color = MaterialTheme.colorScheme.error,
            )
        }
        if (!importNote.isNullOrBlank()) Text(importNote!!)
        if (offline && list != null) {
            Text(
                "Offline — showing saved events for the next 7 days. Other days are empty.",
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        if (loading) Text("Loading…")
        if (!error.isNullOrBlank()) Text(error!!, color = MaterialTheme.colorScheme.error)
        val events = list?.events.orEmpty()
        Text(
            "${list?.count ?: 0} event(s) · ${list?.rangeStart?.take(10) ?: ""} → ${list?.rangeEnd?.take(10) ?: ""}",
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        if (!loading && events.isEmpty()) Text("No events in this window.")
        if (mode == CalMode.Month) {
            MonthGrid(cursor, events) { draft = draftFrom(it); formError = null }
        } else {
            events.forEach { event ->
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text(if (event.allDay) "${event.start.take(10)} · all day" else event.start)
                        Text(event.title, style = MaterialTheme.typography.titleMedium)
                        event.remindBeforeMinutes?.let { minutes ->
                            val label = if (minutes % 60 == 0) "${minutes / 60} h before" else "$minutes min before"
                            Text(label, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        val extra = listOfNotNull(event.location, event.tags.takeIf { it.isNotEmpty() }?.joinToString(", "))
                        Text(extra.joinToString(" · ").ifBlank { "—" }, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        OutlinedButton(onClick = { draft = draftFrom(event); formError = null }) { Text("Edit") }
                    }
                }
            }
        }
    }

}

@Composable
private fun EventEditor(
    draft: EventDraft,
    saving: Boolean,
    error: String?,
    onChange: (EventDraft) -> Unit,
    onCancel: () -> Unit,
    onDelete: () -> Unit,
    onAskNotify: () -> Unit,
    onSave: (EventDraft) -> Unit,
) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(if (draft.id == null) "New event" else "Edit event", style = MaterialTheme.typography.titleMedium)
            OutlinedTextField(
                value = draft.title,
                onValueChange = { onChange(draft.copy(title = it)) },
                label = { Text("Title") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
            )
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                FilterChip(
                    selected = draft.allDay,
                    onClick = { onChange(draft.copy(allDay = !draft.allDay)) },
                    label = { Text("All day") },
                )
            }
            OutlinedTextField(
                value = draft.startDate,
                onValueChange = { onChange(draft.copy(startDate = it)) },
                label = { Text("Start date") },
                placeholder = { Text("YYYY-MM-DD") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
            )
            if (!draft.allDay) {
                OutlinedTextField(
                    value = draft.startTime,
                    onValueChange = { onChange(draft.copy(startTime = it)) },
                    label = { Text("Start time") },
                    placeholder = { Text("HH:mm") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                )
            }
            OutlinedTextField(
                value = draft.endDate,
                onValueChange = { onChange(draft.copy(endDate = it)) },
                label = { Text("End date") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
            )
            if (!draft.allDay) {
                OutlinedTextField(
                    value = draft.endTime,
                    onValueChange = { onChange(draft.copy(endTime = it)) },
                    label = { Text("End time") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                )
            }
            Text("Reminder", color = MaterialTheme.colorScheme.onSurfaceVariant)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                FilterChip(
                    selected = draft.remindUnit == "none",
                    onClick = { onChange(draft.copy(remindUnit = "none", remindAmount = "")) },
                    label = { Text("None") },
                )
                FilterChip(
                    selected = draft.remindUnit == "minutes",
                    onClick = {
                        onChange(
                            draft.copy(
                                remindUnit = "minutes",
                                remindAmount = if (draft.remindUnit == "minutes") draft.remindAmount.ifBlank { "15" } else "15",
                            ),
                        )
                        onAskNotify()
                    },
                    label = { Text("Minutes") },
                )
                FilterChip(
                    selected = draft.remindUnit == "hours",
                    onClick = {
                        onChange(
                            draft.copy(
                                remindUnit = "hours",
                                remindAmount = if (draft.remindUnit == "hours") draft.remindAmount.ifBlank { "1" } else "1",
                            ),
                        )
                        onAskNotify()
                    },
                    label = { Text("Hours") },
                )
            }
            if (draft.remindUnit != "none") {
                OutlinedTextField(
                    value = draft.remindAmount,
                    onValueChange = { onChange(draft.copy(remindAmount = it)) },
                    label = { Text(if (draft.remindUnit == "hours") "Hours before" else "Minutes before") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                )
            }
            OutlinedTextField(
                value = draft.location,
                onValueChange = { onChange(draft.copy(location = it)) },
                label = { Text("Location") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
            )
            OutlinedTextField(
                value = draft.notes,
                onValueChange = { onChange(draft.copy(notes = it)) },
                label = { Text("Notes") },
                modifier = Modifier.fillMaxWidth(),
            )
            OutlinedTextField(
                value = draft.tags,
                onValueChange = { onChange(draft.copy(tags = it)) },
                label = { Text("Tags") },
                placeholder = { Text("health, work") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
            )
            Text("Times are stored in the Pi timezone.", color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (!error.isNullOrBlank()) Text(error, color = MaterialTheme.colorScheme.error)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = { onSave(draft) }, enabled = !saving) {
                    Text(if (saving) "Saving…" else if (draft.id == null) "Create event" else "Save changes")
                }
                if (draft.id != null) {
                    OutlinedButton(onClick = onDelete, enabled = !saving) { Text("Delete") }
                }
                TextButton(onClick = onCancel, enabled = !saving) { Text("Cancel") }
            }
        }
    }
}

@Composable
private fun MonthGrid(cursor: LocalDate, events: List<CalEvent>, onOpen: (CalEvent) -> Unit) {
    val byDay = events.groupBy { it.start.take(10) }
    val cells = monthCells(cursor)
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Row(Modifier.fillMaxWidth()) {
            listOf("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun").forEach { label ->
                Text(label, Modifier.weight(1f), style = MaterialTheme.typography.labelSmall)
            }
        }
        cells.chunked(7).forEach { week ->
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(2.dp)) {
                week.forEach { day ->
                    Column(Modifier.weight(1f)) {
                        Text(day.dayOfMonth.toString(), style = MaterialTheme.typography.labelSmall)
                        byDay[day.toString()].orEmpty().take(2).forEach { event ->
                            TextButton(onClick = { onOpen(event) }, contentPadding = androidx.compose.foundation.layout.PaddingValues(0.dp)) {
                                Text(event.title, maxLines = 1, overflow = TextOverflow.Ellipsis, style = MaterialTheme.typography.labelSmall)
                            }
                        }
                    }
                }
            }
        }
    }
}

private fun monthCells(cursor: LocalDate): List<LocalDate> {
    val first = cursor.withDayOfMonth(1)
    var day = first.minusDays((first.dayOfWeek.value - 1).toLong())
    val last = cursor.withDayOfMonth(cursor.lengthOfMonth())
    val endPad = (7 - last.dayOfWeek.value) % 7
    val end = last.plusDays(endPad.toLong())
    val days = mutableListOf<LocalDate>()
    while (!day.isAfter(end)) {
        days += day
        day = day.plusDays(1)
    }
    return days
}

private fun blankDraft(): EventDraft {
    val start = LocalDate.now()
    return EventDraft(
        id = null,
        title = "",
        allDay = false,
        startDate = start.toString(),
        startTime = "09:00",
        endDate = "",
        endTime = "",
        location = "",
        notes = "",
        tags = "",
        remindAmount = "",
        remindUnit = "none",
    )
}

private fun draftFrom(event: CalEvent) = EventDraft(
    id = event.id,
    title = event.title,
    allDay = event.allDay,
    startDate = event.start.take(10),
    startTime = event.start.drop(11).take(5).ifBlank { "09:00" },
    endDate = event.end?.take(10).orEmpty(),
    endTime = event.end?.drop(11)?.take(5).orEmpty(),
    location = event.location.orEmpty(),
    notes = event.notes.orEmpty(),
    tags = event.tags.joinToString(", "),
    remindAmount = remindFields(event.remindBeforeMinutes).first,
    remindUnit = remindFields(event.remindBeforeMinutes).second,
)

private fun EventDraft.toApi(): CalDraft {
    val titleText = title.trim()
    if (titleText.isEmpty()) error("Title is required")
    if (startDate.length < 10) error("Start date must be YYYY-MM-DD")
    val start = if (allDay) "${startDate.take(10)}T00:00:00" else "${startDate.take(10)}T${startTime.ifBlank { "09:00" }}:00"
    val end = if (endDate.isBlank()) {
        null
    } else if (allDay) {
        "${endDate.take(10)}T00:00:00"
    } else {
        "${endDate.take(10)}T${endTime.ifBlank { "10:00" }}:00"
    }
    val parsedTags = tags.split(",").map { it.trim() }.filter { it.isNotEmpty() }.distinctBy { it.lowercase() }
    val minutes = when (remindUnit) {
        "none" -> null
        "hours" -> {
            val hours = remindAmount.toIntOrNull() ?: error("Reminder must be a whole number of hours")
            hours * 60
        }
        else -> remindAmount.toIntOrNull() ?: error("Reminder must be a whole number of minutes")
    }
    if (minutes != null && (minutes < 1 || minutes > 10080)) {
        error("Reminder must be between 1 minute and 7 days")
    }
    return CalDraft(
        title = titleText,
        start = start,
        end = end,
        allDay = allDay,
        location = location.trim().ifBlank { null },
        notes = notes.trim().ifBlank { null },
        tags = parsedTags,
        editing = id != null,
        remindBeforeMinutes = minutes,
    )
}

private fun remindFields(minutes: Int?): Pair<String, String> {
    if (minutes == null || minutes <= 0) return "" to "none"
    if (minutes % 60 == 0) return (minutes / 60).toString() to "hours"
    return minutes.toString() to "minutes"
}

private fun displayName(context: android.content.Context, uri: Uri): String {
    return runCatching {
        context.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
            if (cursor.moveToFirst()) cursor.getString(0) else null
        }
    }.getOrNull().orEmpty().ifBlank { "calendar.ics" }
}

private fun importSummary(result: CalImport): String {
    val parts = mutableListOf(
        "Imported ${result.created} created, ${result.updated} updated, ${result.skipped} skipped.",
    )
    if (result.repeatDropped.isNotEmpty()) {
        parts += "Repeat not kept: " + result.repeatDropped.joinToString { "${it.title} (${it.detail})" }
    }
    if (result.alarmDropped.isNotEmpty()) {
        parts += "Alarm not kept: " + result.alarmDropped.joinToString { "${it.title} (${it.detail})" }
    }
    return parts.joinToString(" ")
}

private fun filterOffline(cache: CalList, mode: CalMode, cursor: LocalDate, tag: String): CalList {
    val (winStart, winEnd) = offlineWindow(cache.timezone)
    val (viewStart, viewEnd) = viewBounds(mode, cursor)
    val events = cache.events.filter { event ->
        overlaps(event, winStart, winEnd) &&
            overlaps(event, viewStart, viewEnd) &&
            (tag.isBlank() || event.tags.any { it.equals(tag, ignoreCase = true) })
    }
    return cache.copy(count = events.size, events = events)
}

private fun offlineWindow(timezone: String): Pair<LocalDate, LocalDate> {
    val zone = runCatching { ZoneId.of(timezone.ifBlank { "Europe/Berlin" }) }
        .getOrDefault(ZoneId.of("Europe/Berlin"))
    val today = LocalDate.now(zone)
    return today to today.plusDays(7)
}

private fun viewBounds(mode: CalMode, cursor: LocalDate): Pair<LocalDate, LocalDate> {
    if (mode == CalMode.Month) {
        val cells = monthCells(cursor)
        return cells.first() to cells.last().plusDays(1)
    }
    return cursor to cursor.plusDays(14)
}

private fun overlaps(event: CalEvent, start: LocalDate, endExclusive: LocalDate): Boolean {
    val eventStart = runCatching { LocalDate.parse(event.start.take(10)) }.getOrNull() ?: return false
    val endText = event.end?.take(10)?.ifBlank { null } ?: event.start.take(10)
    val eventEnd = runCatching { LocalDate.parse(endText) }.getOrNull() ?: eventStart
    return eventStart < endExclusive && eventEnd.plusDays(1) > start
}
