package com.healthscale.app.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val Teal = Color(0xFF3D9B8F)
private val Blue = Color(0xFF7AA2D6)
private val Amber = Color(0xFFE0A45A)
private val Rose = Color(0xFFE07A9A)
private val Bg = Color(0xFF0F1419)
private val Surface = Color(0xFF1A222C)

internal fun accentColor(accent: String): Color = when (accent) {
    "blue" -> Blue
    "amber" -> Amber
    "rose" -> Rose
    else -> Teal
}

private fun Color.deepen(): Color = Color(
    red = red * 0.72f,
    green = green * 0.72f,
    blue = blue * 0.72f,
    alpha = alpha,
)

private fun contentOn(color: Color): Color {
    val luminance = 0.2126f * color.red + 0.7152f * color.green + 0.0722f * color.blue
    return if (luminance > 0.55f) Color(0xFF0B1210) else Color.White
}

@Composable
fun HealthScaleTheme(
    mode: String = "dark",
    accent: String = "teal",
    content: @Composable () -> Unit,
) {
    val dark = when (mode) {
        "light" -> false
        "system" -> isSystemInDarkTheme()
        else -> true
    }
    val primary = accentColor(accent)
    val secondary = primary.deepen()
    val colors = if (dark) {
        darkColorScheme(
            primary = primary,
            onPrimary = contentOn(primary),
            secondary = secondary,
            onSecondary = contentOn(secondary),
            background = Bg,
            surface = Surface,
            onBackground = Color(0xFFE8EEF4),
            onSurface = Color(0xFFE8EEF4),
        )
    } else {
        lightColorScheme(
            primary = primary,
            onPrimary = contentOn(primary),
            secondary = secondary,
            onSecondary = contentOn(secondary),
            background = Color(0xFFF4F7F6),
            surface = Color.White,
        )
    }
    MaterialTheme(
        colorScheme = colors,
        content = content,
    )
}
