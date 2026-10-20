package com.healthscale.app.ui

import java.time.LocalDateTime
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter
import java.util.Locale
import kotlin.math.round

internal fun formatAmount(value: Double?, suffix: String = ""): String {
    if (value == null || value.isNaN()) return "—"
    val text = trimNumber(value, 1)
    return if (suffix.isEmpty()) text else "$text$suffix"
}

internal fun formatEditable(value: Double): String = trimNumber(value, 3)

internal fun parseEditable(text: String): Double? {
    val cleaned = text.trim().replace(',', '.')
    if (cleaned.isEmpty()) return null
    return cleaned.toDoubleOrNull()?.takeUnless { it.isNaN() }
}

internal fun round2(value: Double): Double {
    if (value.isNaN() || value.isInfinite()) return 0.0
    return round(value * 100.0) / 100.0
}

internal fun epochMillis(iso: String): Long {
    runCatching { OffsetDateTime.parse(iso).toInstant().toEpochMilli() }.getOrNull()?.let { return it }
    runCatching {
        LocalDateTime.parse(iso).atZone(ZoneOffset.UTC).toInstant().toEpochMilli()
    }.getOrNull()?.let { return it }
    return 0L
}

internal fun formatWhen(iso: String): String {
    val zone = ZoneId.systemDefault()
    val formatter = DateTimeFormatter.ofPattern("d MMM yyyy, HH:mm")
    runCatching { OffsetDateTime.parse(iso) }.getOrNull()?.let {
        return formatter.format(it.atZoneSameInstant(zone))
    }
    runCatching { LocalDateTime.parse(iso) }.getOrNull()?.let {
        return formatter.format(it.atZone(zone))
    }
    return iso.replace('T', ' ')
}

private fun trimNumber(value: Double, places: Int): String {
    val factor = when (places) {
        1 -> 10.0
        2 -> 100.0
        else -> 1000.0
    }
    val rounded = round(value * factor) / factor
    val asLong = rounded.toLong()
    if (rounded == asLong.toDouble()) return asLong.toString()
    return "%.${places}f".format(Locale.US, rounded).trimEnd('0').trimEnd('.')
}
