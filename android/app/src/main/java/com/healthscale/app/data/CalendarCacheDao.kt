package com.healthscale.app.data

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query

@Dao
interface CalendarCacheDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(row: CalendarCache)

    @Query("SELECT * FROM calendar_cache WHERE id = 1")
    suspend fun get(): CalendarCache?
}
