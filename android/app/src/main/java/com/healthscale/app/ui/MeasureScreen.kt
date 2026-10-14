package com.healthscale.app.ui

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle

@Composable
fun MeasureScreen(vm: MeasureViewModel) {
    val state by vm.state.collectAsStateWithLifecycle()

    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions(),
    ) {
        vm.refreshBluetooth()
        if (vm.hasBlePermissions()) vm.startScan()
    }

    LaunchedEffect(Unit) {
        vm.refreshBluetooth()
        if (vm.hasBlePermissions() && state.bluetoothReady && !state.scanning) {
            vm.startScan()
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(20.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Text(
            text = "Health Scale",
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.SemiBold,
        )
        Text(
            text = state.lastStatus,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f),
            textAlign = TextAlign.Center,
        )

        Card(
            modifier = Modifier.fillMaxWidth(),
            colors = CardDefaults.cardColors(
                containerColor = MaterialTheme.colorScheme.surface,
            ),
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(24.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Text(
                    text = state.liveWeightKg?.let { "%.2f".format(it) } ?: "—.—",
                    fontSize = 64.sp,
                    fontWeight = FontWeight.Bold,
                    fontFamily = FontFamily.Monospace,
                )
                Text(
                    text = "kg" + if (state.liveStable) "  ·  stable" else if (state.liveWeightKg != null) "  ·  live" else "",
                    style = MaterialTheme.typography.titleMedium,
                    color = MaterialTheme.colorScheme.primary,
                )
                Spacer(modifier = Modifier.height(8.dp))
                if (state.liveImpedance != null) {
                    Text("Impedance: ${"%.1f".format(state.liveImpedance)} Ω")
                }
                if (state.liveMac != null) {
                    Text(
                        text = state.liveMac!!,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f),
                    )
                }
            }
        }

        if (state.lastCommittedWeight != null) {
            Text(
                text = "Last saved: ${"%.2f".format(state.lastCommittedWeight)} kg",
                style = MaterialTheme.typography.bodyLarge,
            )
        }

        Text(
            text = "Pending sync: ${state.pendingCount}",
            style = MaterialTheme.typography.bodyMedium,
        )

        state.error?.let {
            Text(text = it, color = MaterialTheme.colorScheme.error)
        }

        if (!state.permissionsGranted) {
            Button(
                onClick = { permissionLauncher.launch(vm.requiredPermissions()) },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("Grant Bluetooth permission")
            }
        } else if (!state.scanning) {
            Button(
                onClick = { vm.startScan() },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("Start scanning")
            }
        } else {
            OutlinedButton(
                onClick = { vm.stopScan() },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("Stop scanning")
            }
        }

        if (state.pendingCount > 0) {
            Button(
                onClick = { vm.syncNow() },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("Sync now")
            }
        }
    }
}
