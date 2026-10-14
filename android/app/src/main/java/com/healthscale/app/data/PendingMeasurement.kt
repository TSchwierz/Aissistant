package com.healthscale.app.data

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "pending_measurements")
data class PendingMeasurement(
    @PrimaryKey val clientId: String,
    val measuredAtEpochMs: Long,
    val weightKg: Double,
    val impedanceOhm: Double?,
    val unit: String,
    val scaleMac: String?,
    val rawHex: String,
    val synced: Boolean = false,
)
