package com.healthscale.app.data

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query

@Dao
interface PendingMeasurementDao {
    @Insert(onConflict = OnConflictStrategy.IGNORE)
    suspend fun insert(item: PendingMeasurement)

    @Query("SELECT * FROM pending_measurements WHERE synced = 0 ORDER BY measuredAtEpochMs ASC")
    suspend fun getUnsynced(): List<PendingMeasurement>

    @Query("SELECT COUNT(*) FROM pending_measurements WHERE synced = 0")
    suspend fun countUnsynced(): Int

    @Query("UPDATE pending_measurements SET synced = 1 WHERE clientId = :clientId")
    suspend fun markSynced(clientId: String)

    @Query("DELETE FROM pending_measurements WHERE synced = 1")
    suspend fun deleteSynced()

    @Query("SELECT * FROM pending_measurements ORDER BY measuredAtEpochMs DESC LIMIT 1")
    suspend fun latest(): PendingMeasurement?
}
