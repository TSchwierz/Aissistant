package com.healthscale.app.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val Teal = Color(0xFF3D9B8F)
private val TealDark = Color(0xFF2A6F67)
private val Bg = Color(0xFF0F1419)
private val Surface = Color(0xFF1A222C)

private val DarkColors = darkColorScheme(
    primary = Teal,
    onPrimary = Color(0xFF0B1210),
    secondary = TealDark,
    background = Bg,
    surface = Surface,
    onBackground = Color(0xFFE8EEF4),
    onSurface = Color(0xFFE8EEF4),
)

private val LightColors = lightColorScheme(
    primary = TealDark,
    onPrimary = Color.White,
    background = Color(0xFFF4F7F6),
    surface = Color.White,
)

@Composable
fun HealthScaleTheme(content: @Composable () -> Unit) {
    val dark = isSystemInDarkTheme()
    MaterialTheme(
        colorScheme = if (dark) DarkColors else LightColors,
        content = content,
    )
}
