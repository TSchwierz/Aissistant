package com.healthscale.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Menu
import androidx.compose.material3.DrawerValue
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalDrawerSheet
import androidx.compose.material3.ModalNavigationDrawer
import androidx.compose.material3.NavigationDrawerItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.material3.rememberDrawerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.healthscale.app.ui.BriefPane
import com.healthscale.app.ui.CalendarPane
import com.healthscale.app.ui.ClimatePane
import com.healthscale.app.ui.HealthPane
import com.healthscale.app.ui.NewsPane
import com.healthscale.app.ui.SettingsPane
import com.healthscale.app.ui.theme.HealthScaleTheme
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val app = application as HealthScaleApp
        setContent {
            val themeMode by app.settings.themeMode.collectAsStateWithLifecycle(initialValue = "dark")
            val themeAccent by app.settings.themeAccent.collectAsStateWithLifecycle(initialValue = "teal")
            HealthScaleTheme(mode = themeMode, accent = themeAccent) {
                PhoneScaffold(app)
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun PhoneScaffold(app: HealthScaleApp) {
    val url by app.settings.serverUrl.collectAsStateWithLifecycle(
        initialValue = "http://192.168.178.23:8741",
    )
    var tab by remember { mutableStateOf("brief") }
    val drawerState = rememberDrawerState(DrawerValue.Closed)
    val scope = rememberCoroutineScope()
    val tabs = listOf(
        "brief" to "Brief",
        "calendar" to "Calendar",
        "climate" to "Climate",
        "health" to "Health",
        "news" to "News",
        "settings" to "Settings",
    )
    val title = tabs.firstOrNull { it.first == tab }?.second ?: "Brief"
    ModalNavigationDrawer(
        drawerState = drawerState,
        drawerContent = {
            ModalDrawerSheet(drawerContainerColor = MaterialTheme.colorScheme.surface) {
                Spacer(Modifier.height(12.dp))
                Text(
                    "Personal AIssistent",
                    modifier = Modifier.padding(horizontal = 28.dp, vertical = 16.dp),
                    style = MaterialTheme.typography.titleMedium,
                )
                tabs.forEach { (id, label) ->
                    NavigationDrawerItem(
                        label = { Text(label) },
                        selected = tab == id,
                        onClick = {
                            tab = id
                            scope.launch { drawerState.close() }
                        },
                        modifier = Modifier.padding(horizontal = 12.dp),
                    )
                }
                Spacer(Modifier.height(12.dp))
            }
        },
    ) {
        Scaffold(
            modifier = Modifier.fillMaxSize(),
            topBar = {
                TopAppBar(
                    title = { Text(title) },
                    navigationIcon = {
                        IconButton(onClick = { scope.launch { drawerState.open() } }) {
                            Icon(Icons.Filled.Menu, contentDescription = "Open navigation")
                        }
                    },
                    colors = TopAppBarDefaults.topAppBarColors(
                        containerColor = MaterialTheme.colorScheme.surface,
                        titleContentColor = MaterialTheme.colorScheme.onSurface,
                        navigationIconContentColor = MaterialTheme.colorScheme.onSurface,
                    ),
                )
            },
        ) { padding ->
            Box(Modifier.padding(padding).fillMaxSize()) {
                when (tab) {
                    "brief" -> BriefPane(url)
                    "calendar" -> CalendarPane(url)
                    "climate" -> ClimatePane(url)
                    "health" -> HealthPane(url)
                    "news" -> NewsPane(url)
                    else -> SettingsPane(url) { next ->
                        scope.launch { app.settings.setServerUrl(next) }
                    }
                }
            }
        }
    }
}
