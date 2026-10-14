package com.healthscale.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.healthscale.app.ui.BriefPane
import com.healthscale.app.ui.CalendarPane
import com.healthscale.app.ui.ClimatePane
import com.healthscale.app.ui.ConnectionPane
import com.healthscale.app.ui.HealthPane
import com.healthscale.app.ui.NewsPane
import com.healthscale.app.ui.theme.HealthScaleTheme
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val app = application as HealthScaleApp
        setContent {
            HealthScaleTheme {
                val url by app.settings.serverUrl.collectAsStateWithLifecycle(
                    initialValue = "http://192.168.1.100:8741",
                )
                var tab by remember { mutableStateOf("brief") }
                val scope = rememberCoroutineScope()
                val tabs = listOf(
                    "brief" to "Brief",
                    "calendar" to "Calendar",
                    "climate" to "Climate",
                    "health" to "Health",
                    "news" to "News",
                    "link" to "Pi URL",
                )
                Scaffold(modifier = Modifier.fillMaxSize()) { padding ->
                    Column(Modifier.padding(padding).fillMaxSize()) {
                        Row(Modifier.horizontalScroll(rememberScrollState())) {
                            tabs.forEach { (id, label) ->
                                TextButton(onClick = { tab = id }) {
                                    Text(if (tab == id) "● $label" else label)
                                }
                            }
                        }
                        when (tab) {
                            "brief" -> BriefPane(url)
                            "calendar" -> CalendarPane(url)
                            "climate" -> ClimatePane(url)
                            "health" -> HealthPane(url)
                            "news" -> NewsPane(url)
                            else -> ConnectionPane(url) { next ->
                                scope.launch { app.settings.setServerUrl(next) }
                            }
                        }
                    }
                }
            }
        }
    }
}
