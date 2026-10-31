package com.healthscale.app.api

import com.healthscale.app.data.ApiKeyStore
import okhttp3.Interceptor
import okhttp3.OkHttpClient
import okhttp3.Response
import java.util.concurrent.TimeUnit

/** Sends the device API key. Does not log the key or the header value. */
class ApiKeyInterceptor : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val key = ApiKeyStore.apiKey.trim()
        val request = if (key.isEmpty() || key.any { it == '\r' || it == '\n' }) {
            chain.request()
        } else {
            chain.request().newBuilder()
                .header("Authorization", "Bearer $key")
                .build()
        }
        return chain.proceed(request)
    }
}

fun OkHttpClient.withApiKey(): OkHttpClient =
    if (interceptors.any { it is ApiKeyInterceptor }) this
    else newBuilder().addInterceptor(ApiKeyInterceptor()).build()

fun apiHttpClient(connectSeconds: Long = 5, readSeconds: Long = 20): OkHttpClient =
    OkHttpClient.Builder()
        .connectTimeout(connectSeconds, TimeUnit.SECONDS)
        .readTimeout(readSeconds, TimeUnit.SECONDS)
        .build()
        .withApiKey()
