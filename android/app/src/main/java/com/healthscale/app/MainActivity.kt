package com.healthscale.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.MonitorWeight
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.healthscale.app.ui.MeasureScreen
import com.healthscale.app.ui.MeasureViewModel
import com.healthscale.app.ui.MeasureViewModelFactory
import com.healthscale.app.ui.SettingsScreen
import com.healthscale.app.ui.theme.HealthScaleTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val app = application as HealthScaleApp
        setContent {
            HealthScaleTheme {
                val navController = rememberNavController()
                val backStack by navController.currentBackStackEntryAsState()
                val current = backStack?.destination?.route ?: "measure"
                val vm: MeasureViewModel = viewModel(
                    factory = MeasureViewModelFactory(app),
                )

                Scaffold(
                    modifier = Modifier.fillMaxSize(),
                    bottomBar = {
                        NavigationBar {
                            NavigationBarItem(
                                selected = current == "measure",
                                onClick = { navController.navigate("measure") { launchSingleTop = true } },
                                icon = { Icon(Icons.Default.MonitorWeight, contentDescription = null) },
                                label = { Text("Measure") },
                            )
                            NavigationBarItem(
                                selected = current == "settings",
                                onClick = { navController.navigate("settings") { launchSingleTop = true } },
                                icon = { Icon(Icons.Default.Settings, contentDescription = null) },
                                label = { Text("Settings") },
                            )
                        }
                    },
                ) { padding ->
                    NavHost(
                        navController = navController,
                        startDestination = "measure",
                        modifier = Modifier.padding(padding),
                    ) {
                        composable("measure") { MeasureScreen(vm) }
                        composable("settings") { SettingsScreen(vm) }
                    }
                }
            }
        }
    }
}
