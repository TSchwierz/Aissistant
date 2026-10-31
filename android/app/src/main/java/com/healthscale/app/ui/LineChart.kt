package com.healthscale.app.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp

private val ForecastSecondary = Color(0xFF7AA2D6)

@Composable
internal fun LineChart(
    values: List<Double?>,
    modifier: Modifier = Modifier,
    label: String,
    secondary: List<Double?>? = null,
) {
    val primary = MaterialTheme.colorScheme.primary
    val secondaryColor = ForecastSecondary
    Canvas(
        modifier
            .fillMaxWidth()
            .height(200.dp)
            .semantics { contentDescription = label },
    ) {
        if (values.isEmpty() && secondary.isNullOrEmpty()) return@Canvas
        val padX = 12.dp.toPx()
        val padY = 16.dp.toPx()
        val width = (size.width - padX * 2).coerceAtLeast(1f)
        val height = (size.height - padY * 2).coerceAtLeast(1f)
        drawLine(
            color = primary.copy(alpha = 0.25f),
            start = Offset(padX, padY + height / 2f),
            end = Offset(padX + width, padY + height / 2f),
            strokeWidth = 1.dp.toPx(),
        )
        val markEveryPoint = secondary != null || values.any { it == null }
        drawSeries(
            series = values,
            color = primary,
            padX = padX,
            padY = padY,
            width = width,
            height = height,
            markEveryPoint = markEveryPoint,
        )
        if (secondary != null) {
            drawSeries(
                series = secondary,
                color = secondaryColor,
                padX = padX,
                padY = padY,
                width = width,
                height = height,
                markEveryPoint = true,
            )
        }
    }
}

private fun DrawScope.drawSeries(
    series: List<Double?>,
    color: Color,
    padX: Float,
    padY: Float,
    width: Float,
    height: Float,
    markEveryPoint: Boolean,
) {
    val finite = series.mapIndexedNotNull { index, value ->
        if (value == null || value.isNaN()) null else index to value
    }
    if (finite.isEmpty()) return
    val min = finite.minOf { it.second }
    val max = finite.maxOf { it.second }
    val span = (max - min).let { if (it < 0.0001) 1.0 else it }
    val count = series.size.coerceAtLeast(1)

    fun xAt(index: Int): Float = padX + if (count <= 1) {
        width / 2f
    } else {
        width * index / (count - 1)
    }

    fun yAt(value: Double): Float = padY + height * (1.0 - (value - min) / span).toFloat()

    if (finite.size == 1 && !markEveryPoint) {
        val (index, value) = finite[0]
        drawCircle(color, radius = 5.dp.toPx(), center = Offset(xAt(index), yAt(value)))
        return
    }
    val path = Path()
    var drawing = false
    series.forEachIndexed { index, value ->
        if (value == null || value.isNaN()) {
            drawing = false
            return@forEachIndexed
        }
        val x = xAt(index)
        val y = yAt(value)
        if (!drawing) {
            path.moveTo(x, y)
            drawing = true
        } else {
            path.lineTo(x, y)
        }
    }
    drawPath(
        path,
        color,
        style = Stroke(
            width = 2.5.dp.toPx(),
            cap = StrokeCap.Round,
            join = StrokeJoin.Round,
        ),
    )
    if (markEveryPoint) {
        finite.forEach { (index, value) ->
            drawCircle(color, radius = 3.dp.toPx(), center = Offset(xAt(index), yAt(value)))
        }
    } else {
        val (index, value) = finite.last()
        drawCircle(color, radius = 4.dp.toPx(), center = Offset(xAt(index), yAt(value)))
    }
}
