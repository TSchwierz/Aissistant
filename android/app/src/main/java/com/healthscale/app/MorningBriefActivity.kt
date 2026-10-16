package com.healthscale.app

import android.content.Intent
import android.os.Bundle
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Scaffold
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import com.healthscale.app.brief.BriefClient
import com.healthscale.app.brief.MorningBrief
import com.healthscale.app.ui.MorningBriefScreen
import com.healthscale.app.ui.theme.HealthScaleTheme
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import java.util.Locale

/**
 * Modes & Routines entry: deep link `personaissistent://morning`.
 * Fetches Pi `/briefing/morning`, shows sections, TTS on `script`. No in-app music.
 */
class MorningBriefActivity : ComponentActivity(), TextToSpeech.OnInitListener {
    private val briefClient = BriefClient()
    private var tts: TextToSpeech? = null
    private var ttsReady = false
    private var pendingAutoSpeak: String? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        tts = TextToSpeech(this, this)

        val app = application as HealthScaleApp
        setContent {
            HealthScaleTheme {
                var loading by remember { mutableStateOf(true) }
                var error by remember { mutableStateOf<String?>(null) }
                var brief by remember { mutableStateOf<MorningBrief?>(null) }
                var speaking by remember { mutableStateOf(false) }
                var serverUrl by remember { mutableStateOf("http://192.168.178.23:8741") }
                val scope = rememberCoroutineScope()

                fun load(refresh: Boolean = false) {
                    scope.launch {
                        loading = true
                        error = null
                        val url = app.settings.serverUrl.first()
                        serverUrl = url
                        val result = briefClient.fetchMorningBrief(url, refresh = refresh)
                        loading = false
                        result.onSuccess { payload ->
                            brief = payload
                            if (payload.script.isNotBlank()) {
                                if (ttsReady) {
                                    speak(payload.script) { active -> speaking = active }
                                } else {
                                    pendingAutoSpeak = payload.script
                                }
                            }
                        }.onFailure { err ->
                            error = err.message ?: "Failed to fetch brief"
                        }
                    }
                }

                LaunchedEffect(Unit) { load(refresh = false) }

                Scaffold(modifier = Modifier.fillMaxSize()) { padding ->
                    MorningBriefScreen(
                        loading = loading,
                        error = error,
                        brief = brief,
                        speaking = speaking,
                        serverUrl = serverUrl,
                        onRetry = { load(refresh = true) },
                        onSpeak = {
                            val script = brief?.script.orEmpty()
                            if (script.isNotBlank()) {
                                speak(script) { active -> speaking = active }
                            }
                        },
                        onStopSpeak = {
                            tts?.stop()
                            speaking = false
                        },
                        onOpenDashboard = {
                            startActivity(
                                Intent(this@MorningBriefActivity, MainActivity::class.java)
                                    .addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP),
                            )
                        },
                        modifier = Modifier.padding(padding),
                    )
                }
            }
        }
    }

    private fun speak(script: String, onSpeaking: (Boolean) -> Unit) {
        val engine = tts ?: return
        if (!ttsReady) {
            pendingAutoSpeak = script
            return
        }
        engine.language = Locale.US
        engine.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
            override fun onStart(utteranceId: String?) {
                runOnUiThread { onSpeaking(true) }
            }

            override fun onDone(utteranceId: String?) {
                runOnUiThread { onSpeaking(false) }
            }

            @Deprecated("Deprecated in Java")
            override fun onError(utteranceId: String?) {
                runOnUiThread { onSpeaking(false) }
            }
        })
        engine.speak(script, TextToSpeech.QUEUE_FLUSH, null, "morning-brief")
    }

    override fun onInit(status: Int) {
        ttsReady = status == TextToSpeech.SUCCESS
        if (ttsReady) {
            tts?.language = Locale.US
            pendingAutoSpeak?.let { script ->
                pendingAutoSpeak = null
                speak(script) { /* Activity Compose state may have moved on; best-effort */ }
            }
        }
    }

    override fun onDestroy() {
        tts?.stop()
        tts?.shutdown()
        tts = null
        super.onDestroy()
    }
}
