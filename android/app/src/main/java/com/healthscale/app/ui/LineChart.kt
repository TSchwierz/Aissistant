package com.healthscale.app.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp

@Composable
internal fun LineChart(
    values: List<Double>,
    modifier: Modifier = Modifier,
    label: String,
) {
    val line = MaterialTheme.colorScheme.primary
    Canvas(
        modifier
            .fillMaxWidth()
            .height(200.dp)
            .semantics { contentDescription = label },
    ) {
        if (values.isEmpty()) return@Canvas
        val min = values.min()
        val max = values.max()
        val span = (max - min).let { if (it < 0.0001) 1.0 else it }
        val padX = 12.dp.toPx()
        val padY = 16.dp.toPx()
        val width = (size.width - padX * 2).coerceAtLeast(1f)
        val height = (size.height - padY * 2).coerceAtLeast(1f)
        fun xAt(index: Int): Float = padX + if (values.size == 1) {
            width / 2f
        } else {
            width * index / (values.size - 1)
        }
        fun yAt(value: Double): Float = padY + height * (1.0 - (value - min) / span).toFloat()
        drawLine(
            color = line.copy(alpha = 0.25f),
            start = Offset(padX, padY + height / 2f),
            end = Offset(padX + width, padY + height / 2f),
            strokeWidth = 1.dp.toPx(),
        )
        if (values.size == 1) {
            drawCircle(line, radius = 5.dp.toPx(), center = Offset(xAt(0), yAt(values[0])))
            return@Canvas
        }
        val path = Path()
        values.forEachIndexed { index, value ->
            val x = xAt(index)
            val y = yAt(value)
            if (index == 0) path.moveTo(x, y) else path.lineTo(x, y)
        }
        drawPath(
            path,
            line,
            style = Stroke(
                width = 2.5.dp.toPx(),
                cap = StrokeCap.Round,
                join = StrokeJoin.Round,
            ),
        )
        val last = values.lastIndex
        drawCircle(line, radius = 4.dp.toPx(), center = Offset(xAt(last), yAt(values[last])))
    }
}
