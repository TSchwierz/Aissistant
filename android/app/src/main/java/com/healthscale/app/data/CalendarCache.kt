package com.healthscale.app.data

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "calendar_cache")
data class CalendarCache(
    @PrimaryKey val id: Int = 1,
    val payloadJson: String,
    val savedAtEpochMs: Long,
)
