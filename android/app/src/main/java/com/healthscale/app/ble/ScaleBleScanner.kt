package com.healthscale.app.ble

import android.annotation.SuppressLint
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothManager
import android.bluetooth.le.ScanCallback
import android.bluetooth.le.ScanFilter
import android.bluetooth.le.ScanResult
import android.bluetooth.le.ScanSettings
import android.os.Build
import android.content.Context
import android.os.ParcelUuid
import com.healthscale.app.okok.OkOkParser
import com.healthscale.app.okok.ScaleReading
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow

class ScaleBleScanner(private val context: Context) {

    private val adapter: BluetoothAdapter? =
        (context.getSystemService(Context.BLUETOOTH_SERVICE) as BluetoothManager).adapter

    val isBluetoothEnabled: Boolean
        get() = adapter?.isEnabled == true

    @SuppressLint("MissingPermission")
    fun readings(): Flow<ScaleReading> = callbackFlow {
        val scanner = adapter?.bluetoothLeScanner
        if (scanner == null) {
            close(IllegalStateException("Bluetooth LE scanner unavailable"))
            return@callbackFlow
        }

        val callback = object : ScanCallback() {
            override fun onScanResult(callbackType: Int, result: ScanResult?) {
                result ?: return
                val reading = parseScanResult(result) ?: return
                trySend(reading)
            }

            override fun onBatchScanResults(results: MutableList<ScanResult>?) {
                results?.forEach { result ->
                    parseScanResult(result)?.let { trySend(it) }
                }
            }

            override fun onScanFailed(errorCode: Int) {
                close(IllegalStateException("BLE scan failed: $errorCode"))
            }
        }

        val settingsBuilder = ScanSettings.Builder()
            .setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY)
            .setReportDelay(0)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            settingsBuilder
                .setMatchMode(ScanSettings.MATCH_MODE_AGGRESSIVE)
                .setNumOfMatches(ScanSettings.MATCH_NUM_MAX_ADVERTISEMENT)
        }
        // An empty filter is required on some phones. A null filter list
        // delivers no advertisements at all.
        val filters = listOf(ScanFilter.Builder().build())
        scanner.startScan(filters, settingsBuilder.build(), callback)
        awaitClose {
            try {
                scanner.stopScan(callback)
            } catch (_: SecurityException) {
            }
        }
    }

    private fun parseScanResult(result: ScanResult): ScaleReading? {
        val record = result.scanRecord ?: return null
        val mfg = record.manufacturerSpecificData ?: return null
        for (i in 0 until mfg.size()) {
            val companyId = mfg.keyAt(i)
            val payload = mfg.valueAt(i) ?: continue
            OkOkParser.parseManufacturerData(companyId, payload)?.let { reading ->
                val address = try {
                    result.device?.address
                } catch (_: SecurityException) {
                    null
                }
                return if (address.isNullOrBlank()) reading else reading.copy(scaleMac = address)
            }
        }
        // Some scales put data in service data
        val serviceData = record.serviceData
        if (serviceData != null) {
            for ((_, bytes) in serviceData) {
                if (bytes == null || bytes.isEmpty()) continue
                val magic = bytes[0].toInt() and 0xFF
                if (magic == 0xC0 || magic == 0xCA) {
                    OkOkParser.parseManufacturerData(magic, bytes)?.let { return it }
                }
            }
        }
        @Suppress("UNUSED_VARIABLE")
        val uuids: List<ParcelUuid>? = record.serviceUuids
        return null
    }
}
