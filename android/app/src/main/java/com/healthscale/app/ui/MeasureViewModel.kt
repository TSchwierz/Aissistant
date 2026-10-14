package com.healthscale.app.ui

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.content.ContextCompat
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.healthscale.app.HealthScaleApp
import com.healthscale.app.ble.ScaleBleScanner
import com.healthscale.app.data.PendingMeasurement
import com.healthscale.app.okok.ScaleReading
import com.healthscale.app.sync.SyncClient
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.util.UUID
import kotlin.math.abs

data class UiState(
    val scanning: Boolean = false,
    val bluetoothReady: Boolean = false,
    val permissionsGranted: Boolean = false,
    val liveWeightKg: Double? = null,
    val liveStable: Boolean = false,
    val liveMac: String? = null,
    val liveImpedance: Double? = null,
    val lastCommittedWeight: Double? = null,
    val lastStatus: String = "Step on the scale to begin",
    val pendingCount: Int = 0,
    val serverUrl: String = "http://192.168.1.100:8741",
    val syncMessage: String = "",
    val error: String? = null,
)

class MeasureViewModel(private val app: HealthScaleApp) : ViewModel() {
    private val scanner = ScaleBleScanner(app)
    private val dao = app.database.pendingDao()
    private val sync: SyncClient = app.syncClient

    private val _state = MutableStateFlow(UiState())
    val state: StateFlow<UiState> = _state.asStateFlow()

    private var scanJob: Job? = null
    private var lastCommitMac: String? = null
    private var lastCommitWeight: Double? = null
    private var lastCommitAt: Long = 0L

    init {
        viewModelScope.launch {
            app.settings.serverUrl.collect { url ->
                _state.update { it.copy(serverUrl = url) }
            }
        }
        refreshPending()
        refreshBluetooth()
    }

    fun refreshBluetooth() {
        _state.update {
            it.copy(
                bluetoothReady = scanner.isBluetoothEnabled,
                permissionsGranted = hasBlePermissions(),
            )
        }
    }

    fun hasBlePermissions(): Boolean {
        val needed = requiredPermissions()
        return needed.all {
            ContextCompat.checkSelfPermission(app, it) == PackageManager.PERMISSION_GRANTED
        }
    }

    fun requiredPermissions(): Array<String> {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            arrayOf(
                Manifest.permission.BLUETOOTH_SCAN,
                Manifest.permission.BLUETOOTH_CONNECT,
            )
        } else {
            arrayOf(Manifest.permission.ACCESS_FINE_LOCATION)
        }
    }

    fun startScan() {
        if (!hasBlePermissions()) {
            _state.update { it.copy(error = "Bluetooth permissions required", permissionsGranted = false) }
            return
        }
        if (!scanner.isBluetoothEnabled) {
            _state.update { it.copy(error = "Enable Bluetooth", bluetoothReady = false) }
            return
        }
        scanJob?.cancel()
        _state.update {
            it.copy(scanning = true, error = null, lastStatus = "Stand on the scale until the display locks")
        }
        scanJob = viewModelScope.launch {
            try {
                scanner.readings().collect { reading -> onReading(reading) }
            } catch (e: Exception) {
                _state.update {
                    it.copy(scanning = false, error = e.message ?: "Scan failed")
                }
            }
        }
    }

    fun stopScan() {
        scanJob?.cancel()
        scanJob = null
        _state.update { it.copy(scanning = false, lastStatus = "Scan stopped") }
    }

    private suspend fun onReading(reading: ScaleReading) {
        _state.update {
            it.copy(
                liveWeightKg = reading.weightKg,
                liveStable = reading.stable,
                liveMac = reading.scaleMac,
                liveImpedance = reading.impedanceOhm,
                lastStatus = if (reading.stable) "Stable (${reading.protocol})" else "Measuring… (${reading.protocol})",
            )
        }
        if (!reading.stable) return

        val now = System.currentTimeMillis()
        val same =
            reading.scaleMac == lastCommitMac &&
                lastCommitWeight != null &&
                abs(reading.weightKg - lastCommitWeight!!) < 0.05 &&
                now - lastCommitAt < 30_000

        if (same) return

        lastCommitMac = reading.scaleMac
        lastCommitWeight = reading.weightKg
        lastCommitAt = now

        val pending = PendingMeasurement(
            clientId = UUID.randomUUID().toString(),
            measuredAtEpochMs = now,
            weightKg = reading.weightKg,
            impedanceOhm = reading.impedanceOhm,
            unit = reading.unit,
            scaleMac = reading.scaleMac,
            rawHex = reading.rawHex,
        )
        dao.insert(pending)
        refreshPending()
        _state.update {
            it.copy(
                lastCommittedWeight = reading.weightKg,
                lastStatus = "Saved ${"%.2f".format(reading.weightKg)} kg — syncing…",
            )
        }
        autoSync()
    }

    private fun refreshPending() {
        viewModelScope.launch {
            val count = dao.countUnsynced()
            _state.update { it.copy(pendingCount = count) }
        }
    }

    fun saveServerUrl(url: String) {
        viewModelScope.launch {
            app.settings.setServerUrl(url)
            _state.update { it.copy(syncMessage = "Server URL saved") }
        }
    }

    fun testConnection() {
        viewModelScope.launch {
            _state.update { it.copy(syncMessage = "Testing…") }
            val result = sync.testConnection(_state.value.serverUrl)
            _state.update {
                it.copy(
                    syncMessage = result.fold(
                        onSuccess = { "Connected: $it" },
                        onFailure = { e -> "Failed: ${e.message}" },
                    ),
                )
            }
        }
    }

    fun syncNow() {
        viewModelScope.launch { autoSync(manual = true) }
    }

    private suspend fun autoSync(manual: Boolean = false) {
        val url = _state.value.serverUrl
        val result = sync.syncPending(url)
        refreshPending()
        result.fold(
            onSuccess = { r ->
                _state.update {
                    it.copy(
                        syncMessage = if (r.synced == 0 && !manual) it.syncMessage
                        else "Synced ${r.synced} measurement(s)",
                        lastStatus = if (r.synced > 0) "Synced to PC" else it.lastStatus,
                    )
                }
            },
            onFailure = { e ->
                _state.update {
                    it.copy(
                        syncMessage = "Sync pending (${it.pendingCount}): ${e.message}",
                        lastStatus = "Saved locally — PC unreachable",
                    )
                }
            },
        )
    }
}

class MeasureViewModelFactory(private val app: HealthScaleApp) : ViewModelProvider.Factory {
    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>): T {
        return MeasureViewModel(app) as T
    }
}
