package com.healthscale.app.data

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase

@Database(
    entities = [PendingMeasurement::class, CalendarCache::class],
    version = 2,
    exportSchema = false,
)
abstract class AppDatabase : RoomDatabase() {
    abstract fun pendingDao(): PendingMeasurementDao
    abstract fun calendarCacheDao(): CalendarCacheDao

    companion object {
        @Volatile private var instance: AppDatabase? = null

        private val MIGRATION_1_2 = object : Migration(1, 2) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL(
                    "CREATE TABLE IF NOT EXISTS `calendar_cache` (`id` INTEGER NOT NULL, `payloadJson` TEXT NOT NULL, `savedAtEpochMs` INTEGER NOT NULL, PRIMARY KEY(`id`))",
                )
            }
        }

        fun get(context: Context): AppDatabase =
            instance ?: synchronized(this) {
                instance ?: Room.databaseBuilder(
                    context.applicationContext,
                    AppDatabase::class.java,
                    "health_scale.db",
                ).addMigrations(MIGRATION_1_2).build().also { instance = it }
            }
    }
}
