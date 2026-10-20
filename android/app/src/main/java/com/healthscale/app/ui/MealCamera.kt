package com.healthscale.app.ui

import android.graphics.Bitmap
import android.util.Log
import androidx.camera.core.CameraSelector
import androidx.camera.core.ExperimentalGetImage
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageCapture
import androidx.camera.core.ImageCaptureException
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.LocalLifecycleOwner
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.common.InputImage
import java.io.ByteArrayOutputStream
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicReference

internal enum class MealCameraMode { Barcode, Photo }

@Composable
internal fun MealCamera(
    mode: MealCameraMode,
    onBarcode: (String) -> Unit,
    onPhoto: (ByteArray) -> Unit,
    onError: (String) -> Unit,
    onClose: () -> Unit,
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val previewView = remember {
        PreviewView(context).apply {
            implementationMode = PreviewView.ImplementationMode.COMPATIBLE
            scaleType = PreviewView.ScaleType.FILL_CENTER
        }
    }
    val imageCapture = remember {
        ImageCapture.Builder()
            .setCaptureMode(ImageCapture.CAPTURE_MODE_MAXIMIZE_QUALITY)
            .build()
    }
    val onBarcodeState = rememberUpdatedState(onBarcode)
    val onPhotoState = rememberUpdatedState(onPhoto)
    val onErrorState = rememberUpdatedState(onError)
    var ready by remember { mutableStateOf(false) }
    var capturing by remember { mutableStateOf(false) }
    val disposed = remember { AtomicBoolean(false) }
    val captureExecutor = remember { Executors.newSingleThreadExecutor() }

    DisposableEffect(mode, lifecycleOwner) {
        disposed.set(false)
        val executor = Executors.newSingleThreadExecutor()
        val mainExecutor = ContextCompat.getMainExecutor(context)
        val providerFuture = ProcessCameraProvider.getInstance(context)
        val providerRef = AtomicReference<ProcessCameraProvider?>(null)
        val delivered = AtomicBoolean(false)
        val scanner = if (mode == MealCameraMode.Barcode) BarcodeScanning.getClient() else null
        providerFuture.addListener({
            if (disposed.get()) return@addListener
            try {
                val provider = providerFuture.get()
                providerRef.set(provider)
                if (disposed.get()) {
                    provider.unbindAll()
                    return@addListener
                }
                previewView.display?.rotation?.let { rotation ->
                    imageCapture.targetRotation = rotation
                }
                val preview = Preview.Builder().build().also {
                    it.setSurfaceProvider(previewView.surfaceProvider)
                }
                provider.unbindAll()
                if (mode == MealCameraMode.Photo) {
                    provider.bindToLifecycle(
                        lifecycleOwner,
                        CameraSelector.DEFAULT_BACK_CAMERA,
                        preview,
                        imageCapture,
                    )
                } else {
                    val analysis = ImageAnalysis.Builder()
                        .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                        .build()
                    previewView.display?.rotation?.let { analysis.targetRotation = it }
                    val reader = scanner ?: return@addListener
                    analysis.setAnalyzer(executor) { proxy ->
                        if (delivered.get() || disposed.get()) {
                            proxy.close()
                        } else {
                            proxy.readBarcode(reader) { value ->
                                if (delivered.compareAndSet(false, true)) {
                                    mainExecutor.execute {
                                        if (!disposed.get()) onBarcodeState.value(value)
                                    }
                                }
                            }
                        }
                    }
                    provider.bindToLifecycle(
                        lifecycleOwner,
                        CameraSelector.DEFAULT_BACK_CAMERA,
                        preview,
                        analysis,
                    )
                }
                if (disposed.get()) provider.unbindAll() else ready = true
            } catch (e: Exception) {
                Log.w("MealCamera", "Camera bind failed", e)
                if (!disposed.get()) {
                    mainExecutor.execute {
                        onErrorState.value(e.message ?: "Camera unavailable")
                    }
                }
            }
        }, mainExecutor)
        onDispose {
            disposed.set(true)
            providerRef.get()?.unbindAll()
            scanner?.close()
            executor.shutdown()
        }
    }

    DisposableEffect(captureExecutor) {
        onDispose { captureExecutor.shutdown() }
    }

    Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
        Column(Modifier.fillMaxSize()) {
            Box(Modifier.weight(1f).fillMaxWidth()) {
                AndroidView(factory = { previewView }, modifier = Modifier.fillMaxSize())
                TextButton(
                    onClick = onClose,
                    modifier = Modifier.align(Alignment.TopStart).padding(8.dp),
                ) { Text("Close") }
            }
            if (mode == MealCameraMode.Photo) {
                Button(
                    onClick = {
                        if (!ready || capturing) return@Button
                        capturing = true
                        val mainExecutor = ContextCompat.getMainExecutor(context)
                        imageCapture.takePicture(
                            captureExecutor,
                            object : ImageCapture.OnImageCapturedCallback() {
                                override fun onCaptureSuccess(image: ImageProxy) {
                                    val bytes = try {
                                        val bitmap = image.toBitmap()
                                        try {
                                            jpegBytes(bitmap)
                                        } finally {
                                            bitmap.recycle()
                                        }
                                    } catch (e: Exception) {
                                        mainExecutor.execute {
                                            capturing = false
                                            if (!disposed.get()) {
                                                onErrorState.value(e.message ?: "Could not read the photo")
                                            }
                                        }
                                        null
                                    } finally {
                                        image.close()
                                    }
                                    if (bytes != null) {
                                        mainExecutor.execute {
                                            capturing = false
                                            if (!disposed.get()) onPhotoState.value(bytes) else bytes.fill(0)
                                        }
                                    }
                                }

                                override fun onError(exception: ImageCaptureException) {
                                    mainExecutor.execute {
                                        capturing = false
                                        if (!disposed.get()) {
                                            onErrorState.value(exception.message ?: "Camera failed")
                                        }
                                    }
                                }
                            },
                        )
                    },
                    enabled = ready && !capturing,
                    modifier = Modifier.fillMaxWidth().padding(16.dp),
                ) { Text(if (capturing) "Working…" else "Take photo") }
            } else {
                Text(
                    "Point the camera at a barcode",
                    modifier = Modifier.padding(16.dp),
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

@OptIn(ExperimentalGetImage::class)
private fun ImageProxy.readBarcode(
    scanner: com.google.mlkit.vision.barcode.BarcodeScanner,
    onCode: (String) -> Unit,
) {
    try {
        val media = image
        if (media == null) {
            close()
            return
        }
        val input = InputImage.fromMediaImage(media, imageInfo.rotationDegrees)
        scanner.process(input)
            .addOnSuccessListener { codes ->
                val value = codes.firstNotNullOfOrNull { it.rawValue?.takeIf(String::isNotBlank) }
                if (value != null) onCode(value)
            }
            .addOnCompleteListener { close() }
    } catch (e: Exception) {
        Log.w("MealCamera", "Barcode read failed", e)
        close()
    }
}

private fun jpegBytes(source: Bitmap): ByteArray {
    val maxEdge = 1600
    val longest = maxOf(source.width, source.height).coerceAtLeast(1)
    val scaled = if (longest <= maxEdge) {
        null
    } else {
        val scale = maxEdge.toFloat() / longest
        Bitmap.createScaledBitmap(
            source,
            (source.width * scale).toInt().coerceAtLeast(1),
            (source.height * scale).toInt().coerceAtLeast(1),
            true,
        )
    }
    val bitmap = scaled ?: source
    try {
        return ByteArrayOutputStream().use { out ->
            if (!bitmap.compress(Bitmap.CompressFormat.JPEG, 82, out)) {
                error("Could not compress the photo")
            }
            out.toByteArray()
        }
    } finally {
        scaled?.recycle()
    }
}
